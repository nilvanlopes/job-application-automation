import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from job_application_automation.models import JobPosting
from job_application_automation.optimizer import (
    CurriculumOptimizerError,
    copy_optimizer_outputs,
    run_curriculum_optimizer,
)


def test_optimizer_requires_pdf_and_base_provenance(tmp_path):
    root = tmp_path / "optimizer"
    root.mkdir()
    resume = tmp_path / "resume.md"
    resume.write_text("# Ana\n\nReact", encoding="utf-8")

    def fake_runner(command, **kwargs):
        _write_base_artifacts(root, resume)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    with pytest.raises(CurriculumOptimizerError, match="vaga.pdf"):
        run_curriculum_optimizer(
            optimizer_root=root,
            curriculum_file=resume,
            job=JobPosting.from_text("Vaga Python"),
            output_name="vaga",
            runner=fake_runner,
        )


def test_optimizer_copies_original_bytes_and_invokes_new_cli_contract(tmp_path):
    root = tmp_path / "optimizer"
    (root / "input").mkdir(parents=True)
    (root / "input/original-curriculum.txt").write_text("stale", encoding="utf-8")
    resume = tmp_path / "resume.md"
    resume.write_bytes(b"# Ana\n\nReact e Python")
    captured = {}

    def fake_runner(command, **kwargs):
        captured["command"] = command
        captured["cwd"] = kwargs["cwd"]
        _write_base_artifacts(root, resume)
        output = root / "output"
        output.mkdir(parents=True)
        (output / "vaga.pdf").write_bytes(b"%PDF result")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    result = run_curriculum_optimizer(
        optimizer_root=root,
        curriculum_file=resume,
        job=JobPosting.from_text("Desenvolvedor Python"),
        output_name="vaga",
        provider="ollama",
        runner=fake_runner,
    )

    assert captured["command"][:9] == [
        "docker", "compose", "-f", "docker-compose.yml", "run", "--build", "--rm", "-T", "optimizer",
    ]
    assert captured["command"][9:] == [
        "generate",
        "--job-file", "/app/input/job.txt",
        "--curriculum-file", "/app/input/original-curriculum.md",
        "--role", "Desenvolvedor Python",
        "--output-name", "vaga",
        "--provider", "ollama",
    ]
    assert captured["cwd"] == root
    assert (root / "input/original-curriculum.md").read_bytes() == resume.read_bytes()
    assert not (root / "input/original-curriculum.txt").exists()
    assert result.pdf_path.name == "vaga.pdf"
    assert result.source_path == resume.resolve()
    assert result.source_sha256 == sha256(resume.read_bytes()).hexdigest()
    assert result.base_sha256 == sha256(result.base_path.read_bytes()).hexdigest()
    assert result.base_metadata["source"]["sha256"] == result.source_sha256


def test_optimizer_omits_provider_and_formats_to_use_optimizer_defaults(tmp_path):
    root = tmp_path / "optimizer"
    root.mkdir()
    resume = tmp_path / "resume.txt"
    resume.write_text("Ana\nReact", encoding="utf-8")
    captured = {}

    def fake_runner(command, **kwargs):
        captured["command"] = command
        _write_base_artifacts(root, resume)
        (root / "output").mkdir(parents=True)
        (root / "output/cv.pdf").write_bytes(b"%PDF")
        return SimpleNamespace(returncode=0)

    run_curriculum_optimizer(
        optimizer_root=root,
        curriculum_file=resume,
        job=JobPosting.from_text("Frontend"),
        output_name="cv",
        runner=fake_runner,
    )
    assert "--provider" not in captured["command"]
    assert "--formats" not in captured["command"]
    assert "--template" not in captured["command"]


def test_copy_optimizer_outputs_copies_only_pdf(tmp_path):
    root = tmp_path / "optimizer"
    root.mkdir()
    resume = tmp_path / "resume.md"
    resume.write_text("Ana\nReact", encoding="utf-8")

    def fake_runner(command, **kwargs):
        _write_base_artifacts(root, resume)
        (root / "output").mkdir(parents=True)
        (root / "output/cv.pdf").write_bytes(b"%PDF")
        return SimpleNamespace(returncode=0)

    optimized = run_curriculum_optimizer(
        optimizer_root=root,
        curriculum_file=resume,
        job=JobPosting.from_text("Frontend"),
        output_name="cv",
        runner=fake_runner,
    )
    output = tmp_path / "application"
    copied = copy_optimizer_outputs(optimized, output_dir=output, attachment_name="Curriculo.pdf")
    assert copied.pdf_path == output / "Curriculo.pdf"
    assert copied.pdf_path.read_bytes() == b"%PDF"
    assert sorted(path.name for path in output.iterdir()) == ["Curriculo.pdf"]


def test_optimizer_rejects_missing_or_unsupported_source(tmp_path):
    with pytest.raises(CurriculumOptimizerError, match="não encontrado"):
        run_curriculum_optimizer(
            optimizer_root=tmp_path,
            curriculum_file=tmp_path / "missing.md",
            job=JobPosting.from_text("Python"),
        )
    invalid = tmp_path / "resume.docx"
    invalid.write_bytes(b"doc")
    with pytest.raises(CurriculumOptimizerError, match="Extensão"):
        run_curriculum_optimizer(
            optimizer_root=tmp_path,
            curriculum_file=invalid,
            job=JobPosting.from_text("Python"),
        )


def _write_base_artifacts(root: Path, resume: Path) -> None:
    input_dir = root / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    base = input_dir / "base-curriculum.html"
    base.write_text("<!DOCTYPE html><html><body>base</body></html>", encoding="utf-8")
    source_hash = sha256(resume.read_bytes()).hexdigest()
    metadata = {
        "version": 1,
        "source": {"sha256": source_hash},
        "baseSha256": sha256(base.read_bytes()).hexdigest(),
        "provider": "ollama",
        "model": "test",
    }
    (input_dir / "base-curriculum.meta.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )
