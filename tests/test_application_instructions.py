from job_application_automation.ai_job import _job_from_ai_data
from job_application_automation.models import JobPosting


def test_resume_recipient_line_is_not_a_candidate_instruction():
    baseline = JobPosting.from_text(
        "Vaga de Estágio – Desenvolvimento PHP (Laravel)\n"
        "Vaga de Estágio\n"
        "Envie seu currículo para: alvarocalebee@gmail.com"
    )
    job = _job_from_ai_data(
        {
            "title": "Estagiário(a) em Desenvolvimento PHP",
            "application_instructions": [
                {
                    "text": "Envie seu currículo para: alvarocalebee@gmail.com",
                    "kind": "custom",
                    "required": True,
                    "evidence_hint": "Trecho solicitando o envio do currículo",
                }
            ],
        },
        baseline,
    )

    assert job.application_instructions == []


def test_generic_resume_call_is_not_a_required_candidate_answer():
    baseline = JobPosting.from_text(
        "VAGA ABERTA | ANALISTA DE SUPORTE N1 – NOTURNO\n"
        "Interessados, enviem seu currículo e venha fazer parte do nosso time!\n"
        "rh@3structure.com.br"
    )
    job = _job_from_ai_data(
        {
            "title": "Analista de Suporte N1",
            "application_instructions": [
                {
                    "text": "Interessados, enviem seu currículo",
                    "kind": "custom",
                    "required": True,
                    "evidence_hint": "No final do anúncio",
                }
            ],
        },
        baseline,
    )

    assert job.application_instructions == []
