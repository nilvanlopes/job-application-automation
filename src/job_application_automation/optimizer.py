from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable

from .models import JobPosting
from .resume_reader import SUPPORTED_RESUME_EXTENSIONS, read_resume_text


class CurriculumOptimizerError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OptimizedResume:
    pdf_path: Path
    source_path: Path
    source_input_path: Path
    source_sha256: str
    base_path: Path
    base_sha256: str
    base_metadata_path: Path
    base_metadata_sha256: str
    base_metadata: dict[str, Any]


def optimizer_output_name(job: JobPosting) -> str:
    value = "-".join(part for part in (job.company, job.title) if part)
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "curriculo-otimizado"


def run_curriculum_optimizer(
    *,
    optimizer_root: Path,
    curriculum_file: Path,
    job: JobPosting,
    output_name: str | None = None,
    provider: str | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> OptimizedResume:
    optimizer_root = Path(optimizer_root)
    source_path = Path(curriculum_file)
    if not optimizer_root.exists():
        raise CurriculumOptimizerError(f"Curriculum optimizer não encontrado: {optimizer_root}")
    try:
        read_resume_text(source_path)
    except (FileNotFoundError, ValueError) as exc:
        raise CurriculumOptimizerError(str(exc)) from exc

    resolved_name = output_name or optimizer_output_name(job)
    input_dir = optimizer_root / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "job.txt").write_text(job.raw_text, encoding="utf-8")

    extension = source_path.suffix.lower()
    source_input_path = input_dir / f"original-curriculum{extension}"
    _remove_other_discovered_sources(input_dir, source_input_path)
    if source_path.resolve() != source_input_path.resolve():
        shutil.copy2(source_path, source_input_path)
    source_hash = _verified_copy_hash(source_path, source_input_path)

    output_dir = optimizer_root / "output"
    expected_pdf = output_dir / f"{resolved_name}.pdf"
    expected_pdf.unlink(missing_ok=True)

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
        "--curriculum-file",
        f"/app/input/{source_input_path.name}",
        "--role",
        job.title,
        "--output-name",
        resolved_name,
    ]
    if provider and provider.strip():
        command.extend(["--provider", provider.strip()])

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

    base_path = input_dir / "base-curriculum.html"
    base_metadata_path = input_dir / "base-curriculum.meta.json"
    missing = [path for path in (expected_pdf, base_path, base_metadata_path) if not path.exists()]
    if missing:
        paths = ", ".join(str(path) for path in missing)
        raise CurriculumOptimizerError(f"Artefatos esperados não foram gerados: {paths}")

    base_metadata = _load_base_metadata(base_metadata_path)
    base_hash = _sha256(base_path)
    if base_metadata.get("baseSha256") != base_hash:
        raise CurriculumOptimizerError("Hash do base gerado diverge de base-curriculum.meta.json.")
    metadata_source_hash = base_metadata.get("source", {}).get("sha256")
    if metadata_source_hash != source_hash:
        raise CurriculumOptimizerError("Metadados do base não correspondem ao currículo original copiado.")

    return OptimizedResume(
        pdf_path=expected_pdf,
        source_path=source_path.resolve(),
        source_input_path=source_input_path,
        source_sha256=source_hash,
        base_path=base_path,
        base_sha256=base_hash,
        base_metadata_path=base_metadata_path,
        base_metadata_sha256=_sha256(base_metadata_path),
        base_metadata=base_metadata,
    )


def copy_optimizer_outputs(
    optimized: OptimizedResume,
    *,
    output_dir: Path,
    attachment_name: str,
) -> OptimizedResume:
    output_dir.mkdir(parents=True, exist_ok=True)
    copied_pdf = output_dir / attachment_name
    shutil.copy2(optimized.pdf_path, copied_pdf)
    return replace(optimized, pdf_path=copied_pdf)


def _remove_other_discovered_sources(input_dir: Path, selected: Path) -> None:
    for extension in SUPPORTED_RESUME_EXTENSIONS:
        candidate = input_dir / f"original-curriculum{extension}"
        if candidate != selected:
            candidate.unlink(missing_ok=True)


def _verified_copy_hash(source: Path, copied: Path) -> str:
    source_hash = _sha256(source)
    copied_hash = _sha256(copied)
    if source_hash != copied_hash:
        raise CurriculumOptimizerError(f"Currículo copiado diverge da fonte: {source} -> {copied}")
    return source_hash


def _load_base_metadata(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CurriculumOptimizerError(f"Metadados inválidos do currículo base: {path}") from exc
    if not isinstance(data, dict):
        raise CurriculumOptimizerError(f"Metadados inválidos do currículo base: {path}")
    return data


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
