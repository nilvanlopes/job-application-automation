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
    }

    def opener(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({"choices": [{"message": {"content": json.dumps(structured)}}]})

    job = extract_job_with_ai(
        "Vaga backend. Contato real@empresa.com",
        model=DEFAULT_OLLAMA_MODEL,
        opener=opener,
    )

    user_data = json.loads(captured["payload"]["messages"][1]["content"])
    assert captured["url"].endswith("/api/chat")
    assert captured["payload"]["model"] == DEFAULT_OLLAMA_MODEL
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["options"]["temperature"] == 0
    assert captured["payload"]["options"]["num_ctx"] == 32768
    assert captured["payload"]["think"] is False
    assert captured["payload"]["format"]["required"] == [
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
        "keywords",
    ]
    assert user_data["texto_extraido"] == job.raw_text
    assert job.title == "Desenvolvedor Backend"
    assert job.contact_email == "inventado@example.com"
    assert job.requirements == ["Python", "APIs REST"]
    output = capsys.readouterr().out
    assert "[job-application] Resposta bruta da IA na estruturação da vaga" in output
    assert '"title": "Desenvolvedor Backend"' in output


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
    def opener(request, timeout):
        assert request.full_url.endswith("/api/chat")
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
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
                                }
                            )
                        }
                    }
                ]
            }
        )

    job = extract_job_with_ai("Vaga Python", opener=opener)

    assert job.title == "Desenvolvedor Python"
