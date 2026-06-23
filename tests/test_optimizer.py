from pathlib import Path
from types import SimpleNamespace
from hashlib import sha256

import pytest

from job_application_automation.models import JobPosting
from job_application_automation.optimizer import (
    CurriculumOptimizerError,
    run_curriculum_optimizer,
)


def test_optimizer_requires_pdf_html_and_markdown(tmp_path):
    root = tmp_path / "optimizer"
    root.mkdir()
    template = tmp_path / "base.html"
    template.write_text("<html>base</html>", encoding="utf-8")

    def fake_runner(command, **kwargs):
        output = root / "output"
        output.mkdir(parents=True)
        (output / "vaga-gupy.txt").write_text("resume", encoding="utf-8")
        (output / "vaga.html").write_text("resume", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    with pytest.raises(CurriculumOptimizerError, match="vaga.pdf"):
        run_curriculum_optimizer(
            optimizer_root=root,
            optimizer_template=template,
            job=JobPosting.from_text("Vaga Python"),
            output_name="vaga",
            runner=fake_runner,
        )


def test_optimizer_invokes_secure_docker_contract(tmp_path):
    root = tmp_path / "optimizer"
    root.mkdir()
    template = tmp_path / "base.html"
    template.write_text("<html>base</html>", encoding="utf-8")
    captured = {}

    def fake_runner(command, **kwargs):
        captured["command"] = command
        captured["cwd"] = kwargs["cwd"]
        output = root / "output"
        output.mkdir(parents=True)
        (output / "vaga-gupy.txt").write_bytes(b"result")
        for suffix in ("html", "pdf"):
            (output / f"vaga.{suffix}").write_bytes(b"result")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    result = run_curriculum_optimizer(
        optimizer_root=root,
        optimizer_template=template,
        job=JobPosting.from_text("Desenvolvedor Python"),
        output_name="vaga",
        runner=fake_runner,
    )

    assert captured["command"][:9] == [
        "docker",
        "compose",
        "-f",
        "docker-compose.yml",
        "run",
        "--build",
        "--rm",
        "-T",
        "optimizer",
    ]
    assert captured["cwd"] == root
    assert result.pdf_path.name == "vaga.pdf"
    assert captured["command"][9:] == [
        "generate",
        "--job-file", "/app/input/job.txt",
        "--role", "Desenvolvedor Python",
        "--output-name", "vaga",
        "--formats", "pdf,html,markdown",
        "--template", "/app/input/base-curriculum.html",
    ]
    assert (root / "input" / "base-curriculum.html").read_text(encoding="utf-8") == "<html>base</html>"
    assert result.template_source_path == template
    assert result.template_input_path == root / "input" / "base-curriculum.html"
    assert result.template_sha256 == sha256(b"<html>base</html>").hexdigest()
    assert result.template_mtime_ns == template.stat().st_mtime_ns


def test_optimizer_requires_template(tmp_path):
    with pytest.raises(CurriculumOptimizerError, match="Template"):
        run_curriculum_optimizer(
            optimizer_root=tmp_path,
            optimizer_template=tmp_path / "missing.html",
            job=JobPosting.from_text("Desenvolvedor Python"),
        )
