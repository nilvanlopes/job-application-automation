from __future__ import annotations

import json
import html
import os
import re
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from .application_instructions import (
    ApplicationInstructionError,
    ApplicationInstructionResult,
    instructions_markdown,
    load_application_answers,
    resolve_application_instructions,
)
from .ai_client import create_ai_client, providers_need_ollama
from .ai_email import (
    AIEmailBrief,
    AIEmailGenerationError,
    AIEmailReviewAttempt,
    AIEmailReviewError,
    ReviewedAIEmailContent,
    _email_body_metrics,
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
    provider: str = ""
    optimizer_output_name: str = ""
    optimizer_provider: str = ""
    application_answer_file: Path | None = None


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
    ai_client = create_ai_client(provider=request.provider, on_event=_log_step)
    ollama_context = (
        managed_ollama_service(on_event=_log_step)
        if providers_need_ollama(request.provider)
        else nullcontext()
    )
    with ollama_context:
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
            ai_client=ai_client,
        )
        _log_step("Estruturando vaga com IA")
        job = extract_job_with_ai(request.job_text, ai_client=ai_client)
        _log_step(f"Vaga estruturada: {job.title}")
        final_recipient = request.recipient_email.strip() or job.contact_email.strip()
        review_recipient = _resolve_review_recipient(request.review_recipient_email)
        output_dir = resolve_output_dir(job, request.output_dir, now=now)
        answers = load_application_answers(request.application_answer_file)
        instruction_result = resolve_application_instructions(candidate, job, answers=answers)
        if instruction_result.has_pending:
            output_dir.mkdir(parents=True, exist_ok=False)
            _write_job_debug_artifacts(output_dir, job)
            _write_application_instruction_artifacts(output_dir, instruction_result)
            _log_step(f"Instruções obrigatórias pendentes; detalhes salvos em {output_dir}")
            raise ApplicationInstructionError(
                "Candidatura bloqueada: a vaga exige informações que não existem no perfil "
                "nem no arquivo de respostas.",
                instruction_result,
            )

        _log_step("Mapeando aderências e gerando o e-mail completo com IA")
        try:
            reviewed_email = generate_reviewed_ai_email(
                candidate,
                job,
                resume_markdown=resume_text,
                application_facts=tuple(item.answer for item in instruction_result.fulfilled),
                ai_client=ai_client,
            )
        except AIEmailReviewError as exc:
            output_dir.mkdir(parents=True, exist_ok=False)
            _write_failed_email_review_artifacts(
                output_dir,
                exc.attempts,
                alignment_brief=exc.alignment_brief,
            )
            _write_job_debug_artifacts(output_dir, job)
            _log_step(f"Revisão automática reprovou o e-mail; detalhes salvos em {output_dir}")
            raise
        except AIEmailGenerationError as exc:
            output_dir.mkdir(parents=True, exist_ok=False)
            _write_failed_email_generation_artifacts(output_dir, exc)
            _write_job_debug_artifacts(output_dir, job)
            _log_step(f"Geração automática do e-mail falhou; detalhes salvos em {output_dir}")
            raise
        _log_step("Montando rascunho da candidatura")
        draft = build_application_draft(
            candidate,
            job,
            final_recipient or None,
            actual_job_recipient=job.contact_email or final_recipient or None,
            base_resume_markdown=resume_text,
            ai_email_content=reviewed_email.email,
            instruction_result=instruction_result,
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
        _write_application_instruction_artifacts(output_dir, instruction_result)
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
            instruction_result=instruction_result,
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
    subject: str = "",
    body_text: str = "",
    sender_email: str = "nilvanlopes@outlook.com",
) -> OutlookComSendResult:
    output_dir = Path(output_dir)
    manifest = _load_manifest(output_dir)
    resolved_subject = subject.strip() or _manifest_string(manifest, "subject")
    final_recipient = (
        recipient_email.strip()
        or _manifest_string(manifest, "final_recipient_email")
        or _load_job_contact_email(output_dir)
    )
    if not final_recipient:
        raise ValueError(
            "Destinatário final não encontrado nos artefatos. Informe --recipient-email para enviar."
        )
    if not resolved_subject:
        raise ValueError("Assunto não encontrado em application_manifest.json.")
    _ensure_manifest_email_review_approved(manifest)
    _ensure_manifest_application_instructions_complete(manifest)

    html_path = output_dir / (_manifest_string(manifest, "cover_email_html") or "cover_email.html")
    if body_text.strip():
        html_path = _write_final_body_override(output_dir, body_text)
    pdf_name = _manifest_string(manifest, "resume_pdf")
    if not pdf_name:
        raise ValueError("PDF final não encontrado em application_manifest.json.")
    pdf_path = output_dir / pdf_name

    _log_step(f"Enviando artefatos existentes para {final_recipient}")
    result = send_outlook_com_email(
        recipient_email=final_recipient,
        subject=resolved_subject,
        html_path=html_path,
        attachment_paths=[pdf_path],
        config=OutlookComConfig(sender_email=sender_email),
    )
    _write_send_result(
        output_dir / "final_send_result.json",
        result,
        override_html_path=html_path if body_text.strip() else None,
        subject_override=subject.strip() or None,
    )
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
        json.dumps(
            _email_review_payload(
                reviewed_email.attempts,
                alignment_brief=reviewed_email.alignment_brief,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "email_review.md").write_text(
        _email_review_markdown(
            reviewed_email.attempts,
            alignment_brief=reviewed_email.alignment_brief,
        ),
        encoding="utf-8",
    )


def _write_failed_email_review_artifacts(
    output_dir: Path,
    attempts: tuple[AIEmailReviewAttempt, ...],
    *,
    alignment_brief: AIEmailBrief | None = None,
) -> None:
    (output_dir / "email_review.json").write_text(
        json.dumps(
            _email_review_payload(attempts, alignment_brief=alignment_brief),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "email_review.md").write_text(
        _email_review_markdown(attempts, alignment_brief=alignment_brief),
        encoding="utf-8",
    )


def _write_application_instruction_artifacts(
    output_dir: Path,
    instruction_result: ApplicationInstructionResult,
) -> None:
    (output_dir / "application_instructions.json").write_text(
        json.dumps(instruction_result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "application_instructions.md").write_text(
        instructions_markdown(instruction_result),
        encoding="utf-8",
    )
    if instruction_result.has_pending:
        (output_dir / "application_instructions_pending.json").write_text(
            json.dumps(
                {"pending": [item.to_dict() for item in instruction_result.pending]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (output_dir / "application_instructions_pending.md").write_text(
            instructions_markdown(ApplicationInstructionResult((), instruction_result.pending)),
            encoding="utf-8",
        )


def _write_failed_email_generation_artifacts(output_dir: Path, exc: AIEmailGenerationError) -> None:
    payload = {
        "approved": False,
        "stage": "email_generation",
        "error": str(exc),
    }
    (output_dir / "email_generation_error.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "email_generation_error.md").write_text(
        "# Falha na geração automática do e-mail\n\n"
        f"- Etapa: {payload['stage']}\n"
        f"- Erro: {payload['error']}\n",
        encoding="utf-8",
    )


def _email_review_payload(
    attempts: tuple[AIEmailReviewAttempt, ...],
    *,
    alignment_brief: AIEmailBrief | None = None,
) -> dict:
    final_review = attempts[-1].review if attempts else None
    return {
        "approved": bool(final_review and final_review.passed),
        "attempts": len(attempts),
        "final_score": final_review.score if final_review else 0,
        "alignment_brief": alignment_brief.to_dict() if alignment_brief else None,
        "items": [
            {
                "attempt": attempt.number,
                "revision_directives": list(attempt.revision_directives),
                "subject": attempt.email.subject,
                "body": attempt.email.body,
                "metrics": _email_body_metrics(attempt.email.body),
                "review": {
                    "source": attempt.review.source,
                    "approved": attempt.review.approved,
                    "passed": attempt.review.passed,
                    "score": attempt.review.score,
                    "issues": list(attempt.review.issues),
                    "feedback": attempt.review.feedback,
                    "checks": [
                        {
                            "name": check.name,
                            "passed": check.passed,
                            "details": check.details,
                            "correction": check.correction,
                        }
                        for check in attempt.review.checks
                    ],
                },
            }
            for attempt in attempts
        ],
    }


def _email_review_markdown(
    attempts: tuple[AIEmailReviewAttempt, ...],
    *,
    alignment_brief: AIEmailBrief | None = None,
) -> str:
    payload = _email_review_payload(attempts, alignment_brief=alignment_brief)
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
                f"- Origem da revisão: {review['source']}",
                f"- Palavras depois da saudação: {item['metrics']['word_count_after_greeting']}",
                f"- Parágrafos depois da saudação: {item['metrics']['paragraphs_after_greeting']}",
                "",
                "### Correções recebidas nesta geração",
                "",
            ]
        )
        lines.extend([f"- {directive}" for directive in item["revision_directives"]] or ["- Nenhuma"])
        lines.extend(
            [
                "",
                "### Controles",
                "",
            ]
        )
        checks = review["checks"]
        lines.extend(
            [
                f"- {check['name']}: {'passou' if check['passed'] else 'reprovou'} — "
                f"{check['details'] or 'Sem detalhes.'}"
                + (f" Correção: {check['correction']}" if check["correction"] else "")
                for check in checks
            ]
            or ["- Nenhum controle registrado"]
        )
        lines.extend(["", "### Problemas bloqueantes", ""])
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
    instruction_result: ApplicationInstructionResult | None = None,
) -> None:
    manifest = {
        "manifest_version": APPLICATION_MANIFEST_VERSION,
        "subject": subject,
        "review_recipient_email": review_recipient_email,
        "final_recipient_email": final_recipient_email,
        "job_contact_email": job.contact_email,
        "requested_email_subject": job.requested_email_subject,
        "application_instructions": instruction_result.to_dict() if instruction_result else None,
        "application_instructions_pending": bool(instruction_result and instruction_result.has_pending),
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


def _write_final_body_override(output_dir: Path, body_text: str) -> Path:
    body = body_text.strip()
    if not body:
        raise ValueError("Arquivo de corpo do e-mail está vazio.")
    paragraphs = "".join(
        f"<p>{html.escape(part).replace(chr(10), '<br>')}</p>"
        for part in re.split(r"\n\s*\n", body)
        if part.strip()
    )
    html_path = output_dir / "cover_email_final_override.html"
    html_path.write_text(
        "<html><body style='font-family:Arial,Helvetica,sans-serif;color:#111;'>"
        f"{paragraphs}"
        "</body></html>",
        encoding="utf-8",
    )
    return html_path


def _ensure_manifest_email_review_approved(manifest: dict) -> None:
    if manifest.get("email_review_approved") is True:
        return
    raise ValueError(
        "Envio final bloqueado: os artefatos não têm revisão automática de e-mail aprovada. "
        "Regere a candidatura com o fluxo atual antes de enviar."
    )


def _ensure_manifest_application_instructions_complete(manifest: dict) -> None:
    if manifest.get("application_instructions_pending") is True:
        raise ValueError(
            "Envio final bloqueado: existem instruções obrigatórias da vaga pendentes. "
            "Regere a candidatura com um arquivo de respostas antes de enviar."
        )


def _manifest_string(manifest: dict, key: str) -> str:
    value = manifest.get(key)
    return value.strip() if isinstance(value, str) else ""


def _write_send_result(
    path: Path,
    result: OutlookComSendResult,
    *,
    override_html_path: Path | None = None,
    subject_override: str | None = None,
) -> None:
    path.write_text(
        json.dumps(
            {
                "recipient_email": result.recipient_email,
                "subject": result.subject,
                "subject_override": subject_override,
                "body_override_html": override_html_path.name if override_html_path else "",
                "status": result.status,
                "outbox_matches": result.outbox_matches,
                "sent_matches": result.sent_matches,
                "delivery_verification_source": getattr(
                    result,
                    "delivery_verification_source",
                    "outlook_com_local",
                ),
                "server_confirmed": getattr(result, "server_confirmed", False),
                "verification_status": getattr(result, "verification_status", "local_only"),
                "needs_resend": not getattr(result, "server_confirmed", False),
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
