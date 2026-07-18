from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from types import SimpleNamespace
from hashlib import sha256

import pytest

from job_application_automation.ai_email import (
    AIEmailContent,
    AIEmailReview,
    AIEmailReviewAttempt,
    AIEmailReviewError,
    ReviewedAIEmailContent,
)
from job_application_automation.models import CandidateProfile, EducationEntry, JobPosting
from job_application_automation.optimizer import OptimizedResume
from job_application_automation import workflow


JOB_TEXT = """VAGA DE EMPREGO: PROGRAMADOR
PHP / LARAVEL

Local: Palmas
Modelo de trabalho: Presencial e Semi-presencial

DESCRIÇÃO DA VAGA:
Desenvolvimento e manutenção de aplicações web.

REQUISITOS
- Experiência com PHP
- Experiência com APIs REST

Enviar currículo para vagas@opecsis.com.br
Empresa: OPECsis - Escritório Contábil Inteligente
"""


def _candidate_profile() -> CandidateProfile:
    return CandidateProfile(
        name="Nilvan Lopes",
        title="Desenvolvedor Web Full Stack",
        skills=["React", "JavaScript", "HTML", "CSS", "PHP", "Python", "SQL", "Git"],
        education=[
            EducationEntry(
                name="Curso Superior em Análise e Desenvolvimento de Sistemas",
                institution="Unitins",
                status="interrompido",
                level="Curso Superior",
                notes="5º período",
            )
        ],
        summary="Desenvolvedor Web Full Stack.",
        email="nilvanlopes@outlook.com",
        phone="+55 (63) 99223-0471",
        website="https://nilvanlopes.com",
        github="https://github.com/nilvanlopes",
        linkedin="https://www.linkedin.com/in/nilvanlopes",
        whatsapp="https://wa.me/5563992230471",
        highlights=["Destaque 1"],
    )


def _optimizer_result(tmp_path: Path, template_path: Path | None = None) -> OptimizedResume:
    source = tmp_path / "optimizer-result"
    source.mkdir()
    markdown = source / "resume.md"
    html = source / "resume.html"
    pdf = source / "resume.pdf"
    markdown.write_text("# Currículo otimizado", encoding="utf-8")
    html.write_text("<html>Currículo otimizado</html>", encoding="utf-8")
    pdf.write_bytes(b"%PDF optimizer output")
    template_hash = sha256(template_path.read_bytes()).hexdigest() if template_path else ""
    template_mtime = template_path.stat().st_mtime_ns if template_path else 0
    return OptimizedResume(
        markdown,
        html,
        pdf,
        template_source_path=template_path,
        template_input_path=tmp_path / "optimizer" / "input" / "base-curriculum.html" if template_path else None,
        template_sha256=template_hash,
        template_mtime_ns=template_mtime,
    )


def _reviewed_email(subject: str, body: str) -> ReviewedAIEmailContent:
    email = AIEmailContent(subject=subject, body=body)
    review = AIEmailReview(approved=True, score=9, issues=(), feedback="")
    return ReviewedAIEmailContent(
        email=email,
        attempts=(AIEmailReviewAttempt(number=1, email=email, review=review),),
    )


def _prepare(monkeypatch, tmp_path):
    resume = tmp_path / "base.md"
    resume.write_text("# Currículo base\n\nExperiência real.", encoding="utf-8")
    captured = {}

    @contextmanager
    def fake_ollama_manager(**kwargs):
        yield

    monkeypatch.setattr(workflow, "managed_ollama_service", fake_ollama_manager)
    monkeypatch.setattr(
        workflow,
        "generate_candidate_profile",
        lambda resume_path, profile_path=None: captured.setdefault(
            "candidate_profile_call",
            {"resume_path": resume_path, "profile_path": profile_path, "candidate": _candidate_profile()},
        )["candidate"],
    )
    monkeypatch.setattr(
        workflow,
        "extract_job_with_ai",
        lambda text: JobPosting.from_text(text),
    )

    def fake_email(candidate, job, *, resume_markdown):
        captured["email_resume"] = resume_markdown
        return _reviewed_email(
            subject="Interesse na vaga de Programador PHP / Laravel",
            body="Olá.\n\nTenho interesse na vaga.\n\nAtenciosamente,",
        )

    def fake_optimizer(**kwargs):
        captured["optimizer"] = kwargs
        return _optimizer_result(tmp_path, kwargs["optimizer_template"])

    monkeypatch.setattr(workflow, "generate_reviewed_ai_email", fake_email)
    monkeypatch.setattr(workflow, "run_curriculum_optimizer", fake_optimizer)
    monkeypatch.setenv("JOB_APPLICATION_OPTIMIZER_ROOT", str(tmp_path / "optimizer"))
    template = tmp_path / "base-curriculum.html"
    template.write_text("<html>base</html>", encoding="utf-8")
    monkeypatch.setenv("JOB_APPLICATION_OPTIMIZER_TEMPLATE", str(template))
    return resume, captured


def test_job_posting_preserves_title_and_company():
    job = JobPosting.from_text(JOB_TEXT)

    assert job.title == "Programador PHP / Laravel"
    assert job.company == "OPECsis - Escritório Contábil Inteligente"
    assert job.contact_email == "vagas@opecsis.com.br"


def test_run_application_sends_review_email_and_saves_final_recipient(monkeypatch, tmp_path, capsys):
    resume, captured = _prepare(monkeypatch, tmp_path)
    output = tmp_path / "application"
    sent = {}

    def fake_send(**kwargs):
        sent.update(kwargs)
        return SimpleNamespace(sent_matches=1, outbox_matches=0)

    monkeypatch.setattr(workflow, "send_outlook_com_email", fake_send)
    result = workflow.run_application(
        workflow.ApplicationRequest(
            job_text=JOB_TEXT,
            recipient_email="teste@example.com",
            resume_file=resume,
            output_dir=output,
            send=True,
        )
    )

    assert result.recipient_email == "pyuloko7@gmail.com"
    assert result.final_recipient_email == "teste@example.com"
    assert result.review_recipient_email == "pyuloko7@gmail.com"
    assert result.subject == "Candidatura - Interesse na vaga de Programador PHP / Laravel"
    assert captured["candidate_profile_call"]["resume_path"] == Path(
        resume
    )
    assert captured["candidate_profile_call"]["profile_path"].name == "candidate.json"
    assert captured["email_resume"].startswith("# Currículo base")
    assert captured["optimizer"]["optimizer_template"].name == "base-curriculum.html"
    assert captured["optimizer"]["job"].raw_text == result.job.raw_text
    expected_pdf = output / "Currículo_Nilvan_Lopes_Programador_PHP_Laravel.pdf"
    assert sent["recipient_email"] == "pyuloko7@gmail.com"
    assert sent["attachment_paths"] == [expected_pdf]
    assert expected_pdf.read_bytes() == b"%PDF optimizer output"
    manifest = json.loads((output / "application_manifest.json").read_text(encoding="utf-8"))
    assert manifest["review_recipient_email"] == "pyuloko7@gmail.com"
    assert manifest["final_recipient_email"] == "teste@example.com"
    assert manifest["resume_pdf"] == expected_pdf.name
    assert manifest["cover_email_html"] == "cover_email.html"
    assert manifest["optimizer_template_source"] == str(captured["optimizer"]["optimizer_template"])
    assert manifest["optimizer_template_sha256"] == sha256(b"<html>base</html>").hexdigest()
    assert manifest["optimizer_template_mtime_ns"] == captured["optimizer"]["optimizer_template"].stat().st_mtime_ns
    assert manifest["email_review_approved"] is True
    assert manifest["email_review_score"] == 9
    assert manifest["email_review_attempts"] == 1
    assert manifest["email_review_json"] == "email_review.json"
    assert manifest["email_review_markdown"] == "email_review.md"
    review_payload = json.loads((output / "email_review.json").read_text(encoding="utf-8"))
    assert review_payload["approved"] is True
    assert review_payload["attempts"] == 1
    assert (output / "email_review.md").exists()
    assert (output / "resume_optimized.md").exists()
    assert (output / "resume_optimized.html").exists()
    assert json.loads((output / "job_structured.json").read_text(encoding="utf-8"))["title"] == result.job.title
    logs = capsys.readouterr().out
    assert "[job-application] Iniciando fluxo de candidatura" in logs
    assert "[job-application] Mapeando aderências e gerando o e-mail completo com IA" in logs
    assert "[job-application] Fluxo concluído" in logs


def test_run_application_uses_managed_ollama_service(monkeypatch, tmp_path):
    resume, _ = _prepare(monkeypatch, tmp_path)
    lifecycle = {"entered": 0, "exited": 0}

    @contextmanager
    def fake_manager(*, on_event=None, **kwargs):
        lifecycle["entered"] += 1
        if on_event:
            on_event("ollama fake started")
        try:
            yield
        finally:
            lifecycle["exited"] += 1

    monkeypatch.setattr(workflow, "managed_ollama_service", fake_manager)
    result = workflow.run_application(
        workflow.ApplicationRequest(
            job_text=JOB_TEXT,
            recipient_email="teste@example.com",
            resume_file=resume,
            output_dir=tmp_path / "application-managed",
            send=False,
        )
    )

    assert lifecycle["entered"] == 1
    assert lifecycle["exited"] == 1
    assert result.recipient_email == "teste@example.com"
    assert result.final_recipient_email == "teste@example.com"


def test_run_application_without_send_uses_discovered_recipient_and_never_calls_outlook(monkeypatch, tmp_path):
    resume, _ = _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(
        workflow,
        "send_outlook_com_email",
        lambda **kwargs: pytest.fail("Outlook não deveria ser chamado"),
    )

    result = workflow.run_application(
        workflow.ApplicationRequest(
            job_text=JOB_TEXT,
            resume_file=resume,
            output_dir=tmp_path / "draft",
        )
    )

    assert result.recipient_email == "vagas@opecsis.com.br"
    assert result.send_result is None


def test_run_application_can_send_review_without_final_recipient(monkeypatch, tmp_path):
    resume, _ = _prepare(monkeypatch, tmp_path)
    sent = {}

    def fake_send(**kwargs):
        sent.update(kwargs)
        return SimpleNamespace(sent_matches=1, outbox_matches=0)

    monkeypatch.setattr(workflow, "send_outlook_com_email", fake_send)
    result = workflow.run_application(
        workflow.ApplicationRequest(
            job_text="Desenvolvedor Python sem contato",
            resume_file=resume,
            output_dir=tmp_path / "out",
            send=True,
        )
    )

    assert result.final_recipient_email == ""
    assert result.recipient_email == "pyuloko7@gmail.com"
    assert sent["recipient_email"] == "pyuloko7@gmail.com"


def test_run_application_aborts_when_email_review_never_approves(monkeypatch, tmp_path):
    resume, _ = _prepare(monkeypatch, tmp_path)
    output = tmp_path / "rejected"
    email = AIEmailContent(
        subject="Programador Junior",
        body="Olá,\n\nMe chamo e tenho interesse na vaga.",
    )
    review = AIEmailReview(
        approved=False,
        score=3,
        issues=("Frase quebrada: 'Me chamo e'.",),
        feedback="Reescreva a abertura sem autoapresentação.",
    )
    attempts = (AIEmailReviewAttempt(number=1, email=email, review=review),)

    def fake_reviewed_email(*args, **kwargs):
        raise AIEmailReviewError("reprovado", attempts)

    monkeypatch.setattr(workflow, "generate_reviewed_ai_email", fake_reviewed_email)
    monkeypatch.setattr(
        workflow,
        "run_curriculum_optimizer",
        lambda **kwargs: pytest.fail("Optimizer não deveria ser chamado"),
    )
    monkeypatch.setattr(
        workflow,
        "send_outlook_com_email",
        lambda **kwargs: pytest.fail("Outlook não deveria ser chamado"),
    )

    with pytest.raises(AIEmailReviewError):
        workflow.run_application(
            workflow.ApplicationRequest(
                job_text=JOB_TEXT,
                resume_file=resume,
                output_dir=output,
                send=True,
            )
        )

    review_payload = json.loads((output / "email_review.json").read_text(encoding="utf-8"))
    assert review_payload["approved"] is False
    assert review_payload["items"][0]["review"]["issues"] == ["Frase quebrada: 'Me chamo e'."]
    assert (output / "job_structured.json").exists()


def test_send_existing_application_uses_saved_final_recipient(monkeypatch, tmp_path):
    output = tmp_path / "application"
    output.mkdir()
    (output / "cover_email.html").write_text("<html>Email</html>", encoding="utf-8")
    (output / "Currículo_Nilvan_Lopes_Programador.pdf").write_bytes(b"%PDF")
    (output / "job_structured.json").write_text(
        json.dumps({"contact_email": "fallback@example.com"}),
        encoding="utf-8",
    )
    (output / "application_manifest.json").write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "subject": "Candidatura - Programador",
                "review_recipient_email": "pyuloko7@gmail.com",
                "final_recipient_email": "final@example.com",
                "cover_email_html": "cover_email.html",
                "resume_pdf": "Currículo_Nilvan_Lopes_Programador.pdf",
                "email_review_approved": True,
            }
        ),
        encoding="utf-8",
    )
    sent = {}

    def fake_send(**kwargs):
        sent.update(kwargs)
        return SimpleNamespace(
            recipient_email=kwargs["recipient_email"],
            subject=kwargs["subject"],
            status="sent",
            outbox_matches=0,
            sent_matches=1,
            raw_output="ok",
        )

    monkeypatch.setattr(workflow, "send_outlook_com_email", fake_send)

    result = workflow.send_existing_application(output)

    assert result.recipient_email == "final@example.com"
    assert sent["html_path"] == output / "cover_email.html"
    assert sent["attachment_paths"] == [output / "Currículo_Nilvan_Lopes_Programador.pdf"]
    assert json.loads((output / "final_send_result.json").read_text(encoding="utf-8"))[
        "recipient_email"
    ] == "final@example.com"


def test_send_existing_application_allows_recipient_override(monkeypatch, tmp_path):
    output = tmp_path / "application"
    output.mkdir()
    (output / "cover_email.html").write_text("<html>Email</html>", encoding="utf-8")
    (output / "resume.pdf").write_bytes(b"%PDF")
    (output / "application_manifest.json").write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "subject": "Candidatura - Programador",
                "final_recipient_email": "saved@example.com",
                "cover_email_html": "cover_email.html",
                "resume_pdf": "resume.pdf",
                "email_review_approved": True,
            }
        ),
        encoding="utf-8",
    )

    def fake_send(**kwargs):
        return SimpleNamespace(
            recipient_email=kwargs["recipient_email"],
            subject=kwargs["subject"],
            status="sent",
            outbox_matches=0,
            sent_matches=1,
            raw_output="ok",
        )

    monkeypatch.setattr(workflow, "send_outlook_com_email", fake_send)

    result = workflow.send_existing_application(output, recipient_email="override@example.com")

    assert result.recipient_email == "override@example.com"


def test_send_existing_application_blocks_unreviewed_artifacts(monkeypatch, tmp_path):
    output = tmp_path / "application"
    output.mkdir()
    (output / "cover_email.html").write_text("<html>Email</html>", encoding="utf-8")
    (output / "resume.pdf").write_bytes(b"%PDF")
    (output / "application_manifest.json").write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "subject": "Candidatura - Programador",
                "final_recipient_email": "saved@example.com",
                "cover_email_html": "cover_email.html",
                "resume_pdf": "resume.pdf",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        workflow,
        "send_outlook_com_email",
        lambda **kwargs: pytest.fail("Outlook não deveria ser chamado"),
    )

    with pytest.raises(ValueError, match="revisão automática"):
        workflow.send_existing_application(output)


def test_send_existing_application_requires_final_recipient(monkeypatch, tmp_path):
    output = tmp_path / "application"
    output.mkdir()
    (output / "cover_email.html").write_text("<html>Email</html>", encoding="utf-8")
    (output / "resume.pdf").write_bytes(b"%PDF")
    (output / "application_manifest.json").write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "subject": "Candidatura - Programador",
                "final_recipient_email": "",
                "cover_email_html": "cover_email.html",
                "resume_pdf": "resume.pdf",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        workflow,
        "send_outlook_com_email",
        lambda **kwargs: pytest.fail("Outlook não deveria ser chamado"),
    )

    with pytest.raises(ValueError, match="Destinatário final"):
        workflow.send_existing_application(output)


def test_default_output_directory_adds_timestamp_on_collision(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    job = JobPosting.from_text(JOB_TEXT)
    first = workflow.resolve_output_dir(job, None)
    first.mkdir(parents=True)

    second = workflow.resolve_output_dir(
        job,
        None,
        now=lambda: datetime(2026, 6, 10, 12, 30, 45),
    )

    assert second.name.endswith("-20260610-123045")
