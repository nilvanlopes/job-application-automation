from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from .ai_email import (
    AIEmailReviewAttempt,
    AIEmailReviewError,
    ReviewedAIEmailContent,
    generate_reviewed_ai_email,
)
from .ai_job import extract_job_with_ai
from .ai_profile import generate_candidate_profile
from .models import JobPosting
from .ollama_service import managed_ollama_service
from .optimizer import OptimizedResume, copy_optimizer_outputs, run_curriculum_optimizer
from .paths import CANDIDATE_PROFILE_PATH, DEFAULT_RESUME_PATH
from .outlook_com_mailer import OutlookComConfig, OutlookComSendResult, send_outlook_com_email
from .pipeline import build_application_draft
from .resume_reader import read_resume_text


DEFAULT_OPTIMIZER_ROOT = Path("/home/pyu/docker/curriculum-optimizer")
DEFAULT_REVIEW_RECIPIENT_EMAIL = "pyuloko7@gmail.com"
APPLICATION_MANIFEST_VERSION = 2


@dataclass(frozen=True, slots=True)
class ApplicationRequest:
    job_text: str
    recipient_email: str = ""
    review_recipient_email: str = ""
    resume_file: Path | None = None
    output_dir: Path | None = None
    send: bool = False
    sender_email: str = "nilvanlopes@outlook.com"
    optimizer_output_name: str = ""
    optimizer_provider: str = ""


@dataclass(frozen=True, slots=True)
class ApplicationResult:
    job: JobPosting
    recipient_email: str
    final_recipient_email: str
    review_recipient_email: str
    output_dir: Path
    subject: str
    optimized_resume: OptimizedResume
    send_result: OutlookComSendResult | None
    email_review: ReviewedAIEmailContent


def run_application(
    request: ApplicationRequest,
    *,
    now: Callable[[], datetime] = datetime.now,
) -> ApplicationResult:
    with managed_ollama_service(on_event=_log_step):
        _log_step("Iniciando fluxo de candidatura")
        candidate_resume_path = Path(
            os.getenv("JOB_APPLICATION_DEFAULT_RESUME", str(DEFAULT_RESUME_PATH))
        )
        resume_path = request.resume_file or candidate_resume_path
        if not resume_path.exists():
            raise FileNotFoundError(f"Arquivo de currículo não encontrado: {resume_path}")
        _log_step(f"Carregando currículo base: {resume_path}")
        resume_text = read_resume_text(resume_path)

        _log_step("Gerando profile do candidato com IA")
        candidate = generate_candidate_profile(
            resume_path,
            profile_path=CANDIDATE_PROFILE_PATH,
        )
        _log_step("Estruturando vaga com IA")
        job = extract_job_with_ai(request.job_text)
        _log_step(f"Vaga estruturada: {job.title}")
        final_recipient = request.recipient_email.strip() or job.contact_email.strip()
        review_recipient = _resolve_review_recipient(request.review_recipient_email)
        output_dir = resolve_output_dir(job, request.output_dir, now=now)

        _log_step("Mapeando aderências e gerando o e-mail completo com IA")
        try:
            reviewed_email = generate_reviewed_ai_email(
                candidate,
                job,
                resume_markdown=resume_text,
            )
        except AIEmailReviewError as exc:
            output_dir.mkdir(parents=True, exist_ok=False)
            _write_failed_email_review_artifacts(output_dir, exc.attempts)
            _write_job_debug_artifacts(output_dir, job)
            _log_step(f"Revisão automática reprovou o e-mail; detalhes salvos em {output_dir}")
            raise
        _log_step("Montando rascunho da candidatura")
        draft = build_application_draft(
            candidate,
            job,
            final_recipient or None,
            actual_job_recipient=job.contact_email or final_recipient or None,
            base_resume_markdown=resume_text,
            ai_email_content=reviewed_email.email,
        )

        _log_step("Executando optimizer de currículo")
        optimizer_root = Path(
            os.getenv("JOB_APPLICATION_OPTIMIZER_ROOT", str(DEFAULT_OPTIMIZER_ROOT))
        )
        optimized = run_curriculum_optimizer(
            optimizer_root=optimizer_root,
            curriculum_file=resume_path,
            job=job,
            output_name=request.optimizer_output_name or None,
            provider=request.optimizer_provider or None,
        )
        _log_step(
            f"Currículo original do optimizer: {optimized.source_input_path} "
            f"sha256={optimized.source_sha256}"
        )
        _log_step(f"Currículo base gerado: {optimized.base_path} sha256={optimized.base_sha256}")
        _log_step("Copiando artefatos finais")
        copied_resume = copy_optimizer_outputs(
            optimized,
            output_dir=output_dir,
            attachment_name=resume_attachment_name(job),
        )
        _write_artifacts(output_dir, draft)
        _write_email_review_artifacts(output_dir, reviewed_email)
        _write_manifest(
            output_dir,
            subject=draft.email_subject,
            review_recipient_email=review_recipient,
            final_recipient_email=final_recipient,
            job=job,
            html_path=output_dir / "cover_email.html",
            pdf_path=copied_resume.pdf_path,
            optimized_resume=copied_resume,
            reviewed_email=reviewed_email,
        )

        send_result = None
        if request.send:
            _log_step(f"Enviando e-mail de revisão para {review_recipient}")
            send_result = send_outlook_com_email(
                recipient_email=review_recipient,
                subject=draft.email_subject,
                html_path=output_dir / "cover_email.html",
                attachment_paths=[copied_resume.pdf_path],
                config=OutlookComConfig(sender_email=request.sender_email),
            )
        else:
            _log_step("Envio desativado; fluxo encerrado sem Outlook")

        _log_step(f"Fluxo concluído em {output_dir}")

        return ApplicationResult(
            job=job,
            recipient_email=review_recipient if send_result else final_recipient,
            final_recipient_email=final_recipient,
            review_recipient_email=review_recipient,
            output_dir=output_dir,
            subject=draft.email_subject,
            optimized_resume=copied_resume,
            send_result=send_result,
            email_review=reviewed_email,
        )


def send_existing_application(
    output_dir: Path,
    *,
    recipient_email: str = "",
    sender_email: str = "nilvanlopes@outlook.com",
) -> OutlookComSendResult:
    output_dir = Path(output_dir)
    manifest = _load_manifest(output_dir)
    subject = _manifest_string(manifest, "subject")
    final_recipient = (
        recipient_email.strip()
        or _manifest_string(manifest, "final_recipient_email")
        or _load_job_contact_email(output_dir)
    )
    if not final_recipient:
        raise ValueError(
            "Destinatário final não encontrado nos artefatos. Informe --recipient-email para enviar."
        )
    if not subject:
        raise ValueError("Assunto não encontrado em application_manifest.json.")
    _ensure_manifest_email_review_approved(manifest)

    html_path = output_dir / (_manifest_string(manifest, "cover_email_html") or "cover_email.html")
    pdf_name = _manifest_string(manifest, "resume_pdf")
    if not pdf_name:
        raise ValueError("PDF final não encontrado em application_manifest.json.")
    pdf_path = output_dir / pdf_name

    _log_step(f"Enviando artefatos existentes para {final_recipient}")
    result = send_outlook_com_email(
        recipient_email=final_recipient,
        subject=subject,
        html_path=html_path,
        attachment_paths=[pdf_path],
        config=OutlookComConfig(sender_email=sender_email),
    )
    _write_send_result(output_dir / "final_send_result.json", result)
    return result


def resolve_output_dir(
    job: JobPosting,
    requested: Path | None,
    *,
    now: Callable[[], datetime] = datetime.now,
) -> Path:
    if requested is not None:
        if requested.exists():
            raise FileExistsError(f"Diretório de saída já existe: {requested}")
        return requested

    root = Path("output")
    base = root / application_slug(job)
    if not base.exists():
        return base
    return root / f"{application_slug(job)}-{now().strftime('%Y%m%d-%H%M%S')}"


def application_slug(job: JobPosting) -> str:
    value = "-".join(part for part in (job.company, job.title) if part)
    normalized = value.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-") or "candidatura"


def resume_attachment_name(job: JobPosting) -> str:
    title = re.sub(r"[^\wÀ-ÿ]+", "_", job.title, flags=re.UNICODE).strip("_")
    return f"Currículo_Nilvan_Lopes_{title or 'vaga'}.pdf"


def _write_artifacts(output_dir: Path, draft) -> None:
    (output_dir / "cover_email.md").write_text(draft.email_markdown, encoding="utf-8")
    (output_dir / "cover_email.html").write_text(draft.email_html, encoding="utf-8")
    (output_dir / "job_summary.md").write_text(draft.summary_markdown, encoding="utf-8")
    (output_dir / "job_extracted.md").write_text(draft.job_extracted_markdown, encoding="utf-8")
    (output_dir / "job_structured.json").write_text(
        json.dumps(draft.job_structured, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "match_report.md").write_text(draft.match_report_markdown, encoding="utf-8")
    if draft.verification_markdown:
        (output_dir / "recipient_verification.md").write_text(
            draft.verification_markdown,
            encoding="utf-8",
        )


def _write_job_debug_artifacts(output_dir: Path, job: JobPosting) -> None:
    (output_dir / "job_extracted.md").write_text(_job_extracted_markdown(job), encoding="utf-8")
    (output_dir / "job_structured.json").write_text(
        json.dumps(job.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_email_review_artifacts(output_dir: Path, reviewed_email: ReviewedAIEmailContent) -> None:
    (output_dir / "email_review.json").write_text(
        json.dumps(_email_review_payload(reviewed_email.attempts), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "email_review.md").write_text(
        _email_review_markdown(reviewed_email.attempts),
        encoding="utf-8",
    )


def _write_failed_email_review_artifacts(
    output_dir: Path,
    attempts: tuple[AIEmailReviewAttempt, ...],
) -> None:
    (output_dir / "email_review.json").write_text(
        json.dumps(_email_review_payload(attempts), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "email_review.md").write_text(
        _email_review_markdown(attempts),
        encoding="utf-8",
    )


def _email_review_payload(attempts: tuple[AIEmailReviewAttempt, ...]) -> dict:
    final_review = attempts[-1].review if attempts else None
    return {
        "approved": bool(final_review and final_review.passed),
        "attempts": len(attempts),
        "final_score": final_review.score if final_review else 0,
        "items": [
            {
                "attempt": attempt.number,
                "subject": attempt.email.subject,
                "body": attempt.email.body,
                "review": {
                    "approved": attempt.review.approved,
                    "passed": attempt.review.passed,
                    "score": attempt.review.score,
                    "issues": list(attempt.review.issues),
                    "feedback": attempt.review.feedback,
                },
            }
            for attempt in attempts
        ],
    }


def _email_review_markdown(attempts: tuple[AIEmailReviewAttempt, ...]) -> str:
    payload = _email_review_payload(attempts)
    lines = [
        "# Revisão automática do e-mail",
        "",
        f"- Aprovado: {'sim' if payload['approved'] else 'não'}",
        f"- Tentativas: {payload['attempts']}",
        f"- Score final: {payload['final_score']}",
        "",
    ]
    for item in payload["items"]:
        review = item["review"]
        lines.extend(
            [
                f"## Tentativa {item['attempt']}",
                "",
                f"- Aprovado pela revisão: {'sim' if review['approved'] else 'não'}",
                f"- Passou no fluxo: {'sim' if review['passed'] else 'não'}",
                f"- Score: {review['score']}",
                "",
                "### Problemas bloqueantes",
                "",
            ]
        )
        issues = review["issues"]
        lines.extend([f"- {issue}" for issue in issues] or ["- Nenhum"])
        lines.extend(
            [
                "",
                "### Feedback",
                "",
                review["feedback"] or "Sem feedback.",
                "",
                "### Assunto",
                "",
                item["subject"],
                "",
                "### Corpo",
                "",
                item["body"],
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _write_manifest(
    output_dir: Path,
    *,
    subject: str,
    review_recipient_email: str,
    final_recipient_email: str,
    job: JobPosting,
    html_path: Path,
    pdf_path: Path,
    optimized_resume: OptimizedResume,
    reviewed_email: ReviewedAIEmailContent,
) -> None:
    manifest = {
        "manifest_version": APPLICATION_MANIFEST_VERSION,
        "subject": subject,
        "review_recipient_email": review_recipient_email,
        "final_recipient_email": final_recipient_email,
        "job_contact_email": job.contact_email,
        "cover_email_html": html_path.name,
        "resume_pdf": pdf_path.name,
        "optimizer_source_path": str(optimized_resume.source_path),
        "optimizer_source_input": str(optimized_resume.source_input_path),
        "optimizer_source_sha256": optimized_resume.source_sha256,
        "optimizer_base_path": str(optimized_resume.base_path),
        "optimizer_base_sha256": optimized_resume.base_sha256,
        "optimizer_base_metadata_path": str(optimized_resume.base_metadata_path),
        "optimizer_base_metadata_sha256": optimized_resume.base_metadata_sha256,
        "optimizer_base_metadata": optimized_resume.base_metadata,
        "email_review_approved": reviewed_email.final_review.passed,
        "email_review_score": reviewed_email.final_review.score,
        "email_review_attempts": len(reviewed_email.attempts),
        "email_review_json": "email_review.json",
        "email_review_markdown": "email_review.md",
    }
    (output_dir / "application_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_manifest(output_dir: Path) -> dict:
    path = output_dir / "application_manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"Manifesto da candidatura não encontrado: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_job_contact_email(output_dir: Path) -> str:
    path = output_dir / "job_structured.json"
    if not path.exists():
        return ""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("contact_email", "").strip() if isinstance(data, dict) else ""


def _ensure_manifest_email_review_approved(manifest: dict) -> None:
    if manifest.get("email_review_approved") is True:
        return
    raise ValueError(
        "Envio final bloqueado: os artefatos não têm revisão automática de e-mail aprovada. "
        "Regere a candidatura com o fluxo atual antes de enviar."
    )


def _manifest_string(manifest: dict, key: str) -> str:
    value = manifest.get(key)
    return value.strip() if isinstance(value, str) else ""


def _write_send_result(path: Path, result: OutlookComSendResult) -> None:
    path.write_text(
        json.dumps(
            {
                "recipient_email": result.recipient_email,
                "subject": result.subject,
                "status": result.status,
                "outbox_matches": result.outbox_matches,
                "sent_matches": result.sent_matches,
                "raw_output": result.raw_output,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _resolve_review_recipient(explicit: str) -> str:
    return (
        explicit.strip()
        or os.getenv("JOB_APPLICATION_REVIEW_EMAIL", "").strip()
        or DEFAULT_REVIEW_RECIPIENT_EMAIL
    )


def _log_step(message: str) -> None:
    print(f"[job-application] {message}", flush=True)


def _job_extracted_markdown(job: JobPosting) -> str:
    return f"# Texto extraído da vaga\n\n```text\n{job.raw_text}\n```\n"
