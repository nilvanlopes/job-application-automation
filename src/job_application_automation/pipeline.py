from __future__ import annotations

import html

from .ai_email import AIEmailContent
from .email_tools import format_verification_markdown, verify_email_address
from .models import ApplicationDraft, CandidateProfile, EmailDraft, JobPosting
from .signature import SignatureProfile, build_signature_html, build_signature_text


def build_application_draft(
    candidate: CandidateProfile,
    job: JobPosting,
    recipient_email: str | None = None,
    include_signature: bool = True,
    actual_job_recipient: str | None = None,
    base_resume_markdown: str | None = None,
    ai_email_content: AIEmailContent | None = None,
) -> ApplicationDraft:
    effective_recipient = recipient_email or job.contact_email or ""
    actual_recipient = actual_job_recipient or job.contact_email or effective_recipient
    match = _build_match(candidate, job)
    resume = base_resume_markdown.strip() if base_resume_markdown and base_resume_markdown.strip() else _build_resume(candidate, job, match)
    email_draft = _build_email(
        candidate,
        job,
        effective_recipient,
        include_signature=include_signature,
        ai_email_content=ai_email_content,
    )
    summary = _build_summary(candidate, job, actual_recipient, effective_recipient, match)
    verification_markdown = (
        format_verification_markdown(email_draft.verification)
        if email_draft.verification is not None
        else ""
    )
    return ApplicationDraft(
        email_subject=email_draft.subject,
        resume_markdown=resume,
        email_markdown=email_draft.text,
        email_html=email_draft.html,
        summary_markdown=summary,
        verification_markdown=verification_markdown,
        job_extracted_markdown=_build_job_extracted(job),
        match_report_markdown=_build_match_report(job, match),
        job_structured=job.to_dict(),
    )


def _build_match(candidate: CandidateProfile, job: JobPosting) -> dict[str, list[str]]:
    candidate_terms = {skill.lower() for skill in candidate.skills}
    met: list[str] = []
    partial: list[str] = []
    gaps: list[str] = []

    aliases = {
        "git/github": {"git", "github", "git/github"},
        "apis rest": {"api", "apis", "apis rest", "apis restful", "rest"},
        "testes automatizados": {"teste", "testes", "phpunit", "testing", "testes automatizados"},
        "mysql": {"mysql", "sql"},
        "postgresql": {"postgresql", "sql"},
        "vue.js": {"vue", "vue.js"},
    }
    expanded_terms = set(candidate_terms)
    for skill in candidate_terms:
        expanded_terms.update(aliases.get(skill, set()))

    for requirement in job.requirements:
        req_lower = requirement.lower()
        if any(term and term in req_lower for term in expanded_terms):
            met.append(requirement)
        elif any(keyword in req_lower for keyword in job.keywords):
            partial.append(requirement)
        else:
            gaps.append(requirement)

    return {"met": met, "partial": partial, "gaps": gaps}


def _build_resume(candidate: CandidateProfile, job: JobPosting, match: dict[str, list[str]]) -> str:
    skills = ", ".join(candidate.skills)
    met = match["met"] or ["Experiência geral em desenvolvimento web e automação"]
    return (
        f"# {candidate.name}\n\n"
        f"**{candidate.title}**\n\n"
        f"Email: {candidate.email}\n"
        f"Telefone: {candidate.phone}\n"
        f"Site: {candidate.website}\n"
        f"GitHub: {candidate.github}\n"
        f"LinkedIn: {candidate.linkedin}\n\n"
        f"{_build_education_section(candidate)}\n"
        f"## Objetivo\n"
        f"Candidatura para **{job.title}**"
        f"{f' na {job.company}' if job.company else ''}.\n\n"
        f"## Resumo profissional\n{candidate.summary}\n\n"
        f"## Competências relevantes\n{skills}\n\n"
        f"## Aderência à vaga\n"
        + "".join(f"- {item}\n" for item in met)
        + "\n## Destaques\n"
        + "".join(f"- {item}\n" for item in candidate.highlights)
    )


def _build_education_section(candidate: CandidateProfile) -> str:
    if not candidate.education:
        return "## Formação\nNenhuma formação informada.\n\n"

    lines = ["## Formação"]
    for entry in candidate.education:
        details = [entry.name]
        if entry.institution:
            details.append(entry.institution)
        if entry.status:
            details.append(f"status: {entry.status}")
        if entry.started_at or entry.ended_at:
            period = " - ".join(part for part in (entry.started_at, entry.ended_at) if part)
            details.append(period)
        if entry.notes:
            details.append(entry.notes)
        lines.append(f"- {' | '.join(details)}")
    lines.append("")
    return "\n".join(lines) + "\n"


def _build_email(
    candidate: CandidateProfile,
    job: JobPosting,
    recipient_email: str | None,
    include_signature: bool,
    ai_email_content: AIEmailContent | None,
) -> EmailDraft:
    if ai_email_content is None:
        raise ValueError("ai_email_content is required; fixed email copy is no longer supported")

    generated_subject = ai_email_content.subject.strip()
    if not generated_subject:
        raise ValueError("ai_email_content.subject is required")
    subject = _build_subject(generated_subject)
    body = ai_email_content.body.strip()

    signature_profile = SignatureProfile.from_candidate(candidate)
    signature_text = build_signature_text(signature_profile) if include_signature else ""
    signature_html = build_signature_html(signature_profile) if include_signature else ""
    full_text = f"Subject: {subject}\n\n{body}"
    if signature_text:
        full_text = f"{full_text}\n\n{signature_text}"

    paragraphs = "".join(f"<p>{html.escape(part).replace(chr(10), '<br>')}</p>" for part in body.split("\n\n"))
    html_body = (
        "<html><body style='font-family:Arial,Helvetica,sans-serif;color:#111;'>"
        f"{paragraphs}"
        f"{signature_html}"
        "</body></html>"
    )

    verification = verify_email_address(recipient_email) if recipient_email else None
    return EmailDraft(subject=subject, text=full_text, html=html_body, verification=verification)


def _build_subject(generated_subject: str) -> str:
    prefix = "Candidatura - "
    if generated_subject.lower().startswith(prefix.lower()):
        return generated_subject
    return f"{prefix}{generated_subject}"


def _build_summary(candidate: CandidateProfile, job: JobPosting, actual_recipient: str, effective_recipient: str, match: dict[str, list[str]]) -> str:
    keywords = job.keywords if job.keywords else ["nenhuma keyword explícita encontrada"]
    return (
        f"# Match Summary\n\n"
        f"- Candidato: {candidate.name}\n"
        f"- Cargo alvo: {job.title}\n"
        f"- Empresa: {job.company or 'não identificada'}\n"
        f"- Local/modelo: {job.location or 'não identificado'} / {job.work_model or 'não identificado'}\n"
        f"- Contato real da vaga: {actual_recipient or 'não identificado'}\n"
        f"- Destinatário efetivo: {effective_recipient or 'não definido'}\n"
        f"- Keywords detectadas: {', '.join(keywords)}\n"
        f"- Requisitos atendidos: {len(match['met'])}\n"
        f"- Lacunas/itens a revisar: {len(match['gaps'])}\n"
    )


def _build_job_extracted(job: JobPosting) -> str:
    return f"# Texto extraído da vaga\n\n```text\n{job.raw_text}\n```\n"


def _build_match_report(job: JobPosting, match: dict[str, list[str]]) -> str:
    def section(title: str, items: list[str]) -> str:
        body = "".join(f"- {item}\n" for item in items) if items else "- Nenhum item identificado\n"
        return f"## {title}\n{body}\n"

    return (
        f"# Relatório de aderência — {job.title}\n\n"
        + section("Requisitos atendidos", match["met"])
        + section("Requisitos parcialmente relacionados", match["partial"])
        + section("Lacunas ou pontos para revisar", match["gaps"])
    )
