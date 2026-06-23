from __future__ import annotations

import json

from job_application_automation.ai_profile import generate_candidate_profile
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


def test_generate_candidate_profile_writes_candidate_json(tmp_path, capsys):
    resume = tmp_path / "Curriculo.md"
    resume.write_text(
        "# Nilvan Lopes\n\nDesenvolvedor FullStack.\n\nEmail: nilvanlopes@outlook.com\n",
        encoding="utf-8",
    )
    profile_path = tmp_path / "candidate.json"

    profile_data = {
        "name": "Nilvan Lopes",
        "title": "Desenvolvedor FullStack",
        "skills": ["PHP", "Laravel"],
        "education": [
            {
                "name": "Análise e Desenvolvimento de Sistemas",
                "institution": "Faculdade Anhanguera",
                "status": "interrompido",
                "level": "",
                "started_at": "",
                "ended_at": "",
                "notes": "",
            }
        ],
        "summary": "Resumo profissional.",
        "email": "nilvanlopes@outlook.com",
        "phone": "+55 (63) 99223-0471",
        "website": "https://nilvanlopes.com",
        "github": "https://github.com/nilvanlopes",
        "linkedin": "https://www.linkedin.com/in/nilvanlopes",
        "whatsapp": "https://wa.me/5563992230471",
        "highlights": ["Destaque 1"],
    }

    def opener(request, timeout):
        return FakeResponse({"choices": [{"message": {"content": json.dumps(profile_data)}}]})

    profile = generate_candidate_profile(
        resume,
        model=DEFAULT_OLLAMA_MODEL,
        profile_path=profile_path,
        opener=opener,
    )

    output = capsys.readouterr().out
    assert "[job-application] Resposta bruta da IA no profile do candidato" in output
    assert profile.name == "Nilvan Lopes"
    assert profile_path.exists()
    saved = json.loads(profile_path.read_text(encoding="utf-8"))
    assert saved["title"] == "Desenvolvedor FullStack"


def test_generate_candidate_profile_uses_default_ollama_model(tmp_path):
    resume = tmp_path / "Curriculo.md"
    resume.write_text("# Nilvan Lopes\n", encoding="utf-8")

    def opener(request, timeout):
        assert request.full_url.endswith("/api/chat")
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "name": "Nilvan Lopes",
                                    "title": "Dev",
                                    "skills": [],
                                    "education": [],
                                    "summary": "",
                                    "email": "",
                                    "phone": "",
                                    "website": "",
                                    "github": "",
                                    "linkedin": "",
                                    "whatsapp": "",
                                    "highlights": [],
                                }
                            )
                        }
                    }
                ]
            }
        )

    profile = generate_candidate_profile(resume, opener=opener)

    assert profile.title == "Dev"
