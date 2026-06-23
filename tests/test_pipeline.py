from __future__ import annotations

from job_application_automation.ai_email import AIEmailContent
from job_application_automation.email_tools import verify_email_address
from job_application_automation.models import CandidateProfile, EducationEntry, JobPosting
from job_application_automation.pipeline import build_application_draft
from job_application_automation.signature import SignatureProfile, build_signature_text


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

def test_build_application_draft_includes_signature_and_html():
    candidate = _candidate_profile()
    job = JobPosting.from_text("Senior Python Developer\nWe need Python and Docker experience.")

    draft = build_application_draft(
        candidate,
        job,
        "recruiter@example.com",
        ai_email_content=AIEmailContent(
            subject="Interesse na vaga de Senior Python Developer",
            body="Olá, equipe.\n\nTenho interesse na vaga de Senior Python Developer.\n\nAtenciosamente,"
        ),
    )

    assert draft.email_subject == "Candidatura - Interesse na vaga de Senior Python Developer"
    assert "Senior Python Developer" in draft.resume_markdown
    assert "## Formação" in draft.resume_markdown
    assert "interrompido" in draft.resume_markdown
    assert "Senior Python Developer" in draft.email_markdown
    assert "Nilvan Lopes" in draft.email_markdown
    assert "<html>" in draft.email_html
    assert "python" in draft.summary_markdown.lower()
    assert draft.verification_markdown


def test_verify_email_address_rejects_invalid_syntax():
    result = verify_email_address("not-an-email")

    assert result.syntax_valid is False
    assert result.deliverable is False


def test_build_application_draft_does_not_duplicate_subject_prefix():
    draft = build_application_draft(
        _candidate_profile(),
        JobPosting.from_text("Senior Python Developer"),
        "recruiter@example.com",
        ai_email_content=AIEmailContent(
            subject="Candidatura - Senior Python Developer",
            body="Olá.\n\nTenho interesse na vaga.\n\nAtenciosamente,",
        ),
    )

    assert draft.email_subject == "Candidatura - Senior Python Developer"


def test_build_application_draft_preserves_ai_generated_text():
    draft = build_application_draft(
        _candidate_profile(),
        JobPosting.from_text("Analista de Sistemas em TI\nEmpresa: Fazendão Agronegócio"),
        "recruiter@example.com",
        ai_email_content=AIEmailContent(
            subject="Analista de Sistemas em TI - Fazendão Agronegoclo",
            body=(
                "Prezados senhores,\n\n"
                "Tenho interesse na vaga de Analista de Sistemas em TI na Fazendão Agronegoclo.\n\n"
                "Acredito que posso contribuir com a Fazendão Agronegócio em soluções de tecnologia.\n\n"
                "Atenciosamente,\nNilvan Lopes"
            ),
        ),
    )

    assert draft.email_subject == "Candidatura - Analista de Sistemas em TI - Fazendão Agronegoclo"
    assert "vaga de Analista de Sistemas em TI na Fazendão" in draft.email_markdown
    assert "Agronegoclo" in draft.email_markdown
    assert "contribuir com a Fazendão Agronegócio" in draft.email_markdown
    assert draft.email_markdown.count("Nilvan Lopes") == 2


def test_build_application_draft_does_not_repair_self_intro_before_signature():
    draft = build_application_draft(
        _candidate_profile(),
        JobPosting.from_text("Programador Junior"),
        "recruiter@example.com",
        ai_email_content=AIEmailContent(
            subject="Programador Junior",
            body=(
                "Olá,\n\n"
                "Me chamo Nilvan Lopes e tenho interesse na vaga de Programador Junior.\n\n"
                "Atenciosamente,\n[Seu Nome]"
            ),
        ),
    )

    assert "Me chamo Nilvan Lopes e tenho interesse na vaga de Programador Junior." in draft.email_markdown
    assert "[Seu Nome]" in draft.email_markdown
    assert draft.email_markdown.count("Nilvan Lopes") == 2


def test_signature_text_contains_contact_details():
    signature = build_signature_text(SignatureProfile.from_candidate(_candidate_profile()))

    assert "Nilvan Lopes" in signature
    assert "nilvanlopes@outlook.com" in signature
from job_application_automation.models import CandidateProfile, EducationEntry, JobPosting
