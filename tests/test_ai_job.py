from __future__ import annotations

import json

import pytest

from job_application_automation.ai_job import AIJobExtractionError, extract_job_with_ai
from job_application_automation.ollama import DEFAULT_OLLAMA_MODEL


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def _content(data):
    return {"choices": [{"message": {"content": json.dumps(data)}}]}


def _approved_review():
    return {
        "approved": True,
        "issues": [],
        "feedback": "",
    }


def test_ai_structures_extracted_text_and_preserves_exact_contact(capsys):
    captured = {}
    structured = {
        "title": "Desenvolvedor Backend",
        "company": "Empresa Exemplo",
        "location": "Palmas",
        "work_model": "Remoto",
        "contact_email": "inventado@example.com",
        "contact_whatsapp": "",
        "description": "Desenvolvimento de APIs.",
        "requirements": ["Python", "APIs REST"],
        "nice_to_have": ["Docker"],
        "benefits": ["Plano de saúde"],
        "keywords": ["python", "api", "docker"],
        "title_evidence": "Vaga backend",
        "company_evidence": "Empresa Exemplo",
    }
    responses = [_content(structured), _content(_approved_review())]

    def opener(request, timeout):
        captured.setdefault("calls", []).append(json.loads(request.data.decode("utf-8")))
        captured["url"] = request.full_url
        return FakeResponse(responses.pop(0))

    job = extract_job_with_ai(
        "Vaga backend. Contato real@empresa.com",
        model=DEFAULT_OLLAMA_MODEL,
        opener=opener,
    )

    extraction_payload = captured["calls"][0]
    review_payload = captured["calls"][1]
    user_data = json.loads(extraction_payload["messages"][1]["content"])
    assert captured["url"].endswith("/api/chat")
    assert extraction_payload["model"] == DEFAULT_OLLAMA_MODEL
    assert extraction_payload["stream"] is False
    assert extraction_payload["options"]["temperature"] == 0
    assert extraction_payload["options"]["num_ctx"] == 32768
    assert extraction_payload["think"] is False
    assert extraction_payload["format"]["required"] == [
        "title",
        "company",
        "location",
        "work_model",
        "contact_email",
        "contact_whatsapp",
        "description",
        "requirements",
        "nice_to_have",
        "benefits",
        "requested_email_subject",
        "application_instructions",
        "keywords",
        "title_evidence",
        "company_evidence",
    ]
    assert review_payload["format"]["required"] == ["approved", "issues", "feedback"]
    assert user_data["texto_extraido"] == job.raw_text
    assert job.title == "Desenvolvedor Backend"
    assert job.contact_email == "inventado@example.com"
    assert job.requirements == ["Python", "APIs REST"]
    output = capsys.readouterr().out
    assert "Resposta bruta" not in output
    assert "Desenvolvedor Backend" not in output


def test_ai_job_extracts_explicit_application_instructions():
    structured = {
        "title": "Dev Full Stack",
        "company": "",
        "location": "remoto",
        "work_model": "PJ",
        "contact_email": "leoxcontato@gmail.com",
        "contact_whatsapp": "",
        "description": "Manutenção de sistemas existentes.",
        "requirements": ["PHP", "JavaScript e TypeScript", "SQL", "Docker"],
        "nice_to_have": [],
        "benefits": ["Pagamento semanal"],
        "requested_email_subject": "Dev Full Stack",
        "application_instructions": [
            {
                "text": "Currículo ou LinkedIn",
                "kind": "resume_or_linkedin",
                "required": True,
                "evidence_hint": "currículo anexado e LinkedIn do perfil",
            },
            {
                "text": "Link do GitHub (ou portfólio de projetos)",
                "kind": "github_or_portfolio",
                "required": True,
                "evidence_hint": "github, website ou projetos do perfil",
            },
            {
                "text": "Sua disponibilidade semanal (horas) e o valor semanal ou por hora que busca",
                "kind": "availability_and_compensation",
                "required": True,
                "evidence_hint": "resposta explícita do candidato",
            },
        ],
        "keywords": ["PHP", "Docker"],
        "title_evidence": "Dev Full Stack",
        "company_evidence": "",
    }
    responses = [_content(structured), _content(_approved_review())]

    def opener(request, timeout):
        return FakeResponse(responses.pop(0))

    job = extract_job_with_ai(
        "Dev Full Stack - PJ remoto\n"
        "Como se candidatar:\n"
        "Envie para leoxcontato@gmail.com com o assunto \"Dev Full Stack\":\n"
        "1. Currículo ou LinkedIn\n"
        "2. Link do GitHub (ou portfólio de projetos)\n"
        "3. Sua disponibilidade semanal (horas) e o valor semanal ou por hora que busca",
        opener=opener,
    )

    assert job.requested_email_subject == "Dev Full Stack"
    assert [item.kind for item in job.application_instructions] == [
        "resume_or_linkedin",
        "github_or_portfolio",
        "availability_and_compensation",
    ]


def test_ai_job_rejects_garbage_response():
    def opener(request, timeout):
        return FakeResponse({"choices": [{"message": {"content": "thinking... sem JSON útil"}}]})

    with pytest.raises(AIJobExtractionError, match="JSON válido"):
        extract_job_with_ai(
            "Vaga backend. Contato real@empresa.com",
            model=DEFAULT_OLLAMA_MODEL,
            opener=opener,
        )


def test_ai_job_uses_default_ollama_model():
    responses = [
        _content(
            {
                "title": "Desenvolvedor Python",
                "company": "",
                "location": "",
                "work_model": "",
                "contact_email": "",
                "contact_whatsapp": "",
                "description": "",
                "requirements": [],
                "nice_to_have": [],
                "benefits": [],
                "keywords": [],
                "title_evidence": "Vaga Python",
                "company_evidence": "",
            }
        ),
        _content(_approved_review()),
    ]

    def opener(request, timeout):
        assert request.full_url.endswith("/api/chat")
        return FakeResponse(responses.pop(0))

    job = extract_job_with_ai("Vaga Python", opener=opener)

    assert job.title == "Desenvolvedor Python"


def test_ai_job_fails_when_ai_leaves_title_empty():
    def opener(request, timeout):
        return FakeResponse(_content(
            {
                "title": "",
                "company": "",
                "location": "",
                "work_model": "",
                "contact_email": "",
                "contact_whatsapp": "",
                "description": "",
                "requirements": [],
                "nice_to_have": [],
                "benefits": [],
                "keywords": [],
                "title_evidence": "",
                "company_evidence": "",
            }
        ))

    with pytest.raises(AIJobExtractionError, match="cargo da vaga"):
        extract_job_with_ai(
            "Vaga SoftwareDeveloper Jr.\n"
            "Modelo: 100% Home Office\n"
            "Envie seu currículo para jobs.br@coffeebeantech.com com o assunto.",
            opener=opener,
        )


def test_ai_job_retries_when_review_rejects_promotional_title():
    responses = [
        _content(
            {
                "title": "Temos Vaga Para Desenvolvedor Full Stack Pleno | Grupo Easy",
                "company": "",
                "location": "Remoto",
                "work_model": "",
                "contact_email": "jennyfer.ferreti@grupoeasy.com.br",
                "contact_whatsapp": "",
                "description": "",
                "requirements": [],
                "nice_to_have": [],
                "benefits": [],
                "keywords": ["php", "laravel", "vue.js"],
                "title_evidence": "Cabeçalho completo do anúncio",
                "company_evidence": "",
            }
        ),
        _content(
            {
                "approved": False,
                "issues": ["title mistura chamada de vaga e empresa"],
                "feedback": "Use somente o cargo profissional no title e coloque Grupo Easy em company.",
            }
        ),
        _content(
            {
                "title": "Desenvolvedor Full Stack Pleno",
                "company": "Grupo Easy",
                "location": "Remoto",
                "work_model": "",
                "contact_email": "jennyfer.ferreti@grupoeasy.com.br",
                "contact_whatsapp": "",
                "description": "",
                "requirements": [],
                "nice_to_have": [],
                "benefits": [],
                "keywords": ["php", "laravel", "vue.js"],
                "title_evidence": "DESENVOLVEDOR FULL STACK PLENO",
                "company_evidence": "GRUPO EASY",
            }
        ),
        _content(_approved_review()),
    ]
    calls = []

    def opener(request, timeout):
        calls.append(json.loads(request.data.decode("utf-8")))
        return FakeResponse(responses.pop(0))

    job = extract_job_with_ai(
        "TEMOS VAGA PARA DESENVOLVEDOR FULL STACK PLENO | GRUPO EASY\n"
        "Local: Remoto\n"
        "Envie seu currículo para: jennyfer.ferreti@grupoeasy.com.br",
        opener=opener,
    )

    assert job.title == "Desenvolvedor Full Stack Pleno"
    assert job.company == "Grupo Easy"
    assert job.contact_email == "jennyfer.ferreti@grupoeasy.com.br"
    assert "A revisão rejeitou" in calls[2]["messages"][2]["content"]


def test_ai_job_fails_when_review_keeps_rejecting_title():
    bad = {
        "title": "Temos Vaga Para Desenvolvedor Full Stack Pleno | Grupo Easy",
        "company": "",
        "location": "Remoto",
        "work_model": "",
        "contact_email": "jennyfer.ferreti@grupoeasy.com.br",
        "contact_whatsapp": "",
        "description": "",
        "requirements": [],
        "nice_to_have": [],
        "benefits": [],
        "keywords": [],
        "title_evidence": "Cabeçalho completo do anúncio",
        "company_evidence": "",
    }
    rejected = {
        "approved": False,
        "issues": ["title não é cargo profissional limpo"],
        "feedback": "O title ainda parece manchete da vaga.",
    }
    responses = [_content(bad), _content(rejected), _content(bad), _content(rejected)]

    def opener(request, timeout):
        return FakeResponse(responses.pop(0))

    with pytest.raises(AIJobExtractionError, match="cargo adequado"):
        extract_job_with_ai(
            "TEMOS VAGA PARA DESENVOLVEDOR FULL STACK PLENO | GRUPO EASY",
            opener=opener,
        )


def test_ai_job_accepts_clean_title_when_review_false_rejects():
    clean = {
        "title": "Desenvolvedor Full Stack Júnior",
        "company": "Alvo RH / Instituto CDT",
        "location": "Home Office, todo o Brasil",
        "work_model": "100% remoto",
        "contact_email": "rh@institutocdt.com.br",
        "contact_whatsapp": "",
        "description": "Desenvolver e manter aplicações web.",
        "requirements": ["React", "Next.js", "Node.js", "Git"],
        "nice_to_have": ["CRM", "Automação de processos"],
        "benefits": [],
        "keywords": ["Full Stack", "React", "Node.js"],
        "title_evidence": "Cargo: Desenvolvedor Full Stack Júnior",
        "company_evidence": "Empresa: Alvo RH / Instituto CDT",
    }
    rejected = {
        "approved": False,
        "issues": ["reviewer false negative"],
        "feedback": "",
    }
    responses = [_content(clean), _content(rejected), _content(clean), _content(rejected)]

    def opener(request, timeout):
        return FakeResponse(responses.pop(0))

    job = extract_job_with_ai(
        "Cargo: Desenvolvedor Full Stack Júnior\nEmpresa: Alvo RH / Instituto CDT",
        opener=opener,
    )

    assert job.title == "Desenvolvedor Full Stack Júnior"
    assert job.contact_email == "rh@institutocdt.com.br"
