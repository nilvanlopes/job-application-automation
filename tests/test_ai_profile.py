from __future__ import annotations

import json

from job_application_automation.ai_profile import generate_candidate_profile
from job_application_automation.models import CandidateProfile
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
        (
            "# Nilvan Lopes\n\nDesenvolvedor FullStack.\n\n"
            "## Experiência profissional\n\nEmpresa Exemplo\n- Integração de APIs REST.\n\n"
            "## Projetos\n\nProjeto Exemplo (`https://example.com`) com aplicação web responsiva.\n\n"
            "## Idiomas\n\nInglês intermediário.\n\nEmail: nilvanlopes@outlook.com\n"
        ),
        encoding="utf-8",
    )
    profile_path = tmp_path / "candidate.json"
    profile_path.write_text(
        json.dumps({"grammatical_gender": "masculino"}),
        encoding="utf-8",
    )
    calls = []

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
        "experiences": [
            {
                "company": "Empresa Exemplo",
                "role": "Desenvolvedor FullStack",
                "project": "Sistema Exemplo",
                "started_at": "2025",
                "ended_at": "",
                "activities": ["Integração de APIs REST."],
                "skills": ["Integração de APIs REST"],
            }
        ],
        "projects": [
            {
                "name": "Projeto Exemplo",
                "details": ["Aplicação web responsiva."],
                "references": ["https://example.com"],
                "skills": ["Responsividade"],
            }
        ],
        "languages": [
            {
                "name": "Inglês",
                "proficiency": "Intermediário",
                "notes": "",
            }
        ],
        "soft_skills": ["Comunicação clara"],
        "location": "Palmas - TO",
    }

    def opener(request, timeout):
        request_payload = json.loads(request.data.decode("utf-8"))
        calls.append(request_payload)
        system_prompt = request_payload["messages"][0]["content"]
        user_payload = json.loads(request_payload["messages"][1]["content"])
        final_instruction = request_payload["messages"][2]["content"]
        schema = request_payload["format"]
        required = schema["required"]

        assert request_payload["options"]["num_ctx"] == 32768
        assert request_payload["think"] is False
        assert user_payload.get("curriculo_original") or user_payload.get("fonte_exclusiva")
        if required == [
            "name",
            "title",
            "summary",
            "email",
            "phone",
            "website",
            "github",
            "linkedin",
            "whatsapp",
            "location",
        ]:
            assert "identificação, cargo, resumo" in system_prompt
            assert "copie o cargo" in final_instruction
        elif required == ["education", "languages", "soft_skills"]:
            assert "Um ano sozinho não prova conclusão" in system_prompt
            assert "Nunca coloque o status" in system_prompt
            assert "nenhum idioma foi omitido" in final_instruction
        elif required == ["skills"]:
            assert "exatamente uma competência" in schema["properties"]["skills"]["description"]
            assert schema["properties"]["skills"]["items"]["maxLength"] == 80
            if "fonte_exclusiva" in user_payload:
                assert user_payload["nome_da_fonte"]
                assert user_payload["fonte_exclusiva"]
                if "nomes técnicos literais" in system_prompt:
                    assert "todo nome técnico explícito" in final_instruction
                else:
                    assert "Cada item deve conter exatamente uma competência curta" in system_prompt
                    assert "cobertura completa da fonte exclusiva" in final_instruction
            else:
                assert "seções de habilidades técnicas" in system_prompt
                assert "Confira linha por linha" in final_instruction
        elif required == ["experiences", "highlights"]:
            assert "Atividades iguais ou parecidas em empresas diferentes" in system_prompt
            assert "nenhuma atividade foi removida" in final_instruction
        else:
            assert required == ["projects"]
            assert "compare caractere por caractere" in final_instruction
            assert schema["properties"]["projects"]["items"]["required"] == [
                "name",
                "details",
                "references",
            ]
            project_properties = schema["properties"]["projects"]["items"]["properties"]
            assert project_properties["details"]["items"]["maxLength"] == 60
            assert project_properties["references"]["items"]["enum"] == ["https://example.com"]

        response_data = {field: profile_data[field] for field in required}
        return FakeResponse({"choices": [{"message": {"content": json.dumps(response_data)}}]})

    profile = generate_candidate_profile(
        resume,
        model=DEFAULT_OLLAMA_MODEL,
        profile_path=profile_path,
        opener=opener,
    )

    output = capsys.readouterr().out
    assert "Resposta bruta" not in output
    assert "Resumo profissional." not in output
    assert len(calls) == 9
    assert profile.name == "Nilvan Lopes"
    assert profile.grammatical_gender == "masculino"
    assert profile.experiences[0].activities == ["Integração de APIs REST."]
    assert profile.projects[0].references == ["https://example.com"]
    assert profile.languages[0].proficiency == "Intermediário"
    assert profile.soft_skills == ["Comunicação clara"]
    assert profile_path.exists()
    saved = json.loads(profile_path.read_text(encoding="utf-8"))
    assert saved["title"] == "Desenvolvedor FullStack"
    assert saved["grammatical_gender"] == "masculino"
    assert saved["experiences"][0]["company"] == "Empresa Exemplo"
    assert saved["location"] == "Palmas - TO"


def test_generate_candidate_profile_uses_default_ollama_model(tmp_path):
    resume = tmp_path / "Curriculo.md"
    resume.write_text("# Nilvan Lopes\n", encoding="utf-8")

    def opener(request, timeout):
        assert request.full_url.endswith("/api/chat")
        request_payload = json.loads(request.data.decode("utf-8"))
        complete_data = {
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
            "experiences": [],
            "projects": [],
            "languages": [],
            "soft_skills": [],
            "location": "",
        }
        response_data = {
            field: complete_data[field]
            for field in request_payload["format"]["required"]
        }
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(response_data)
                        }
                    }
                ]
            }
        )

    profile = generate_candidate_profile(
        resume,
        profile_path=tmp_path / "candidate.json",
        opener=opener,
    )

    assert profile.title == "Dev"


def test_generate_candidate_profile_normalizes_common_model_shape_variants(tmp_path):
    resume = tmp_path / "Curriculo.md"
    resume.write_text("# Nilvan Lopes\n\nProjeto Exemplo (`example.com`).", encoding="utf-8")

    complete_data = {
        "name": "Nilvan Lopes",
        "title": "Desenvolvedor Fullstack",
        "summary": "Resumo profissional.",
        "contacts": {
            "phone": "(63) 99223-0471",
            "email": "nilvanlopes@outlook.com",
            "urls": ["https://www.linkedin.com/in/nilvanlopes/", "https://github.com/nilvanlopes"],
        },
        "location": {"city": "Palmas", "state": "TO"},
        "education": [
            {
                "started_at": "2024",
                "ended_at": "",
                "status": "Cursando",
                "level": "",
                "notes": "Análise e Desenvolvimento de Sistemas, UNITINS",
            }
        ],
        "languages": [
            {"language": "Inglês", "level": "Intermediário", "notes": "leitura técnica"},
        ],
        "soft_skills": ["Comunicação clara"],
        "experiences": [],
        "highlights": [],
        "projects": [
            {
                "title": "Projeto Exemplo",
                "details": ["Aplicação web responsiva."],
                "references": ["example.com"],
            }
        ],
        "skills": [],
    }

    def opener(request, timeout):
        request_payload = json.loads(request.data.decode("utf-8"))
        required = request_payload["format"]["required"]
        response_data = {field: complete_data[field] for field in required if field in complete_data}
        if "email" in required:
            response_data.update(
                {
                    "name": complete_data["name"],
                    "title": complete_data["title"],
                    "summary": complete_data["summary"],
                    "contacts": complete_data["contacts"],
                    "location": complete_data["location"],
                }
            )
        return FakeResponse({"choices": [{"message": {"content": json.dumps(response_data)}}]})

    profile = generate_candidate_profile(
        resume,
        profile_path=tmp_path / "candidate.json",
        opener=opener,
    )

    assert profile.email == "nilvanlopes@outlook.com"
    assert profile.phone == "(63) 99223-0471"
    assert profile.linkedin == "https://www.linkedin.com/in/nilvanlopes/"
    assert profile.github == "https://github.com/nilvanlopes"
    assert profile.location == "Palmas - TO"
    assert profile.education[0].name == "Análise e Desenvolvimento de Sistemas, UNITINS"
    assert profile.languages[0].name == "Inglês"
    assert profile.languages[0].proficiency == "Intermediário"
    assert profile.projects[0].name == "Projeto Exemplo"


def test_candidate_profile_loads_legacy_json_without_rich_fields(tmp_path):
    profile_path = tmp_path / "candidate.json"
    profile_path.write_text(
        json.dumps(
            {
                "name": "Nilvan Lopes",
                "title": "Desenvolvedor",
                "skills": ["Python"],
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
        ),
        encoding="utf-8",
    )

    profile = CandidateProfile.from_file(profile_path)

    assert profile.skills == ["Python"]
    assert profile.experiences == []
    assert profile.projects == []
    assert profile.languages == []
    assert profile.soft_skills == []
    assert profile.location == ""
    assert profile.grammatical_gender == ""
