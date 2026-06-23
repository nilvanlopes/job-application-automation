from __future__ import annotations

import re
import shutil
import subprocess
from hashlib import sha256
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .models import JobPosting


class CurriculumOptimizerError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OptimizedResume:
    markdown_path: Path
    html_path: Path
    pdf_path: Path
    template_source_path: Path | None = None
    template_input_path: Path | None = None
    template_sha256: str = ""
    template_mtime_ns: int = 0


def optimizer_output_name(job: JobPosting) -> str:
    value = "-".join(part for part in (job.company, job.title) if part)
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "curriculo-otimizado"


def run_curriculum_optimizer(
    *,
    optimizer_root: Path,
    optimizer_template: Path,
    job: JobPosting,
    output_name: str | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> OptimizedResume:
    if not optimizer_root.exists():
        raise CurriculumOptimizerError(f"Curriculum optimizer não encontrado: {optimizer_root}")
    if not optimizer_template.exists():
        raise CurriculumOptimizerError(f"Template do curriculum optimizer não encontrado: {optimizer_template}")

    resolved_name = output_name or optimizer_output_name(job)
    input_dir = optimizer_root / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "job.txt").write_text(job.raw_text, encoding="utf-8")
    input_template = input_dir / "base-curriculum.html"
    shutil.copy2(optimizer_template, input_template)
    template_metadata = _template_metadata(optimizer_template, input_template)

    output_dir = optimizer_root / "output"
    expected_paths = (
        output_dir / f"{resolved_name}-gupy.txt",
        output_dir / f"{resolved_name}.html",
        output_dir / f"{resolved_name}.pdf",
    )
    for path in expected_paths:
        path.unlink(missing_ok=True)

    command = [
        "docker",
        "compose",
        "-f",
        "docker-compose.yml",
        "run",
        "--build",
        "--rm",
        "-T",
        "optimizer",
        "generate",
        "--job-file",
        "/app/input/job.txt",
        "--role",
        job.title,
        "--output-name",
        resolved_name,
        "--formats",
        "pdf,html,markdown",
        "--template",
        "/app/input/base-curriculum.html",
    ]
    completed = runner(
        command,
        cwd=optimizer_root,
        stdout=None,
        stderr=None,
        timeout=600,
    )
    if getattr(completed, "returncode", 0) != 0:
        stderr = (getattr(completed, "stderr", "") or "").strip()
        raise CurriculumOptimizerError(stderr or "Curriculum optimizer falhou sem mensagem de erro.")

    result = OptimizedResume(
        markdown_path=expected_paths[0],
        html_path=expected_paths[1],
        pdf_path=expected_paths[2],
        template_source_path=optimizer_template,
        template_input_path=input_template,
        template_sha256=template_metadata["sha256"],
        template_mtime_ns=int(template_metadata["mtime_ns"]),
    )
    missing = [path for path in (result.markdown_path, result.html_path, result.pdf_path) if not path.exists()]
    if missing:
        paths = ", ".join(str(path) for path in missing)
        raise CurriculumOptimizerError(f"Saídas esperadas não foram geradas: {paths}")
    return result


def copy_optimizer_outputs(
    optimized: OptimizedResume,
    *,
    output_dir: Path,
    attachment_name: str,
) -> OptimizedResume:
    output_dir.mkdir(parents=True, exist_ok=True)
    copied = OptimizedResume(
        markdown_path=output_dir / "resume_optimized.md",
        html_path=output_dir / "resume_optimized.html",
        pdf_path=output_dir / attachment_name,
        template_source_path=optimized.template_source_path,
        template_input_path=optimized.template_input_path,
        template_sha256=optimized.template_sha256,
        template_mtime_ns=optimized.template_mtime_ns,
    )
    shutil.copy2(optimized.markdown_path, copied.markdown_path)
    shutil.copy2(optimized.html_path, copied.html_path)
    shutil.copy2(optimized.pdf_path, copied.pdf_path)
    return copied


def _template_metadata(source: Path, copied: Path) -> dict[str, str | int]:
    source_hash = _sha256(source)
    copied_hash = _sha256(copied)
    if source_hash != copied_hash:
        raise CurriculumOptimizerError(
            f"Template copiado para o optimizer diverge da fonte: {source} -> {copied}"
        )
    return {
        "sha256": source_hash,
        "mtime_ns": source.stat().st_mtime_ns,
    }


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
