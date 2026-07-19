from __future__ import annotations

import json
from datetime import date

import pytest

from job_application_automation.ai_email import (
    AIEmailBrief,
    AIEmailBriefMatch,
    AIEmailContent,
    AIEmailGenerationError,
    AIEmailReviewError,
    generate_ai_email,
    generate_ai_email_brief,
    generate_reviewed_ai_email,
    review_ai_email,
    _job_priority_catalog,
)
from job_application_automation.models import (
    CandidateProfile,
    EducationEntry,
    ExperienceEntry,
    JobPosting,
    LanguageEntry,
    ProjectEntry,
)
from job_application_automation.ollama import (
    DEFAULT_OLLAMA_EMAIL_ANALYSIS_MODEL,
    DEFAULT_OLLAMA_EMAIL_MODEL,
    DEFAULT_OLLAMA_MODEL,
)


CHECK_NAMES = (
    "factual_fidelity",
    "vacancy_alignment",
)


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _response(content: dict) -> FakeResponse:
    return FakeResponse({"choices": [{"message": {"content": json.dumps(content)}}]})


def _candidate_profile() -> CandidateProfile:
    return CandidateProfile(
        name="Nilvan Lopes Cruz",
        title="Desenvolvedor Fullstack",
        grammatical_gender="masculino",
        skills=["React", "JavaScript", "PHP", "Node.js", "SQL", "Git", "Docker"],
        education=[
            EducationEntry(
                name="Análise e Desenvolvimento de Sistemas",
                institution="UNITINS",
                status="cursando",
                started_at="2024",
            )
        ],
        summary="Atuo com desenvolvimento fullstack desde 2025.",
        email="nilvanlopes@outlook.com",
        phone="(63) 99999-9999",
        github="https://github.com/nilvanlopes",
        linkedin="https://linkedin.com/in/nilvanlopes",
        experiences=[
            ExperienceEntry(
                company="Niceplanet",
                role="Desenvolvedor Fullstack Junior",
                project="SMGEO",
                started_at="2025",
                activities=[
                    "Manutenção e evolução do sistema, atuando no front-end e no back-end.",
                    "Realizei correções de bugs e ajustes de funcionalidades com React, PHP e Node.js.",
                    "Integrei APIs REST e apoiei operações em bancos relacionais.",
                ],
            ),
            ExperienceEntry(
                company="Fity Ai",
                role="Desenvolvedor Fullstack",
                started_at="2026",
                activities=[
                    "Participei da modelagem do sistema e da documentação do produto.",
                    "Desenvolvi o aplicativo com React Native e NestJS.",
                ],
            ),
        ],
        projects=[
            ProjectEntry(
                name="Landing Page Hostinger",
                details=["Desenvolvi uma landing page responsiva com SASS."],
            )
        ],
        languages=[
            LanguageEntry(name="Inglês", proficiency="intermediário para leitura e escrita técnica")
        ],
        soft_skills=[
            "Comunicação clara e objetiva",
            "Rapidez no aprendizado de novas tecnologias e metodologias",
        ],
        location="Palmas - TO",
    )


def _job() -> JobPosting:
    return JobPosting(
        raw_text="Vaga completa",
        title="Desenvolvedor(a) Fullstack Junior",
        company="Elev Tecnologia",
        work_model="Híbrido",
        description=(
            "Ambiente colaborativo para desenvolvimento de produtos SaaS.\n"
            "- Desenvolver melhorias e novas funcionalidades\n"
            "- Atuar em backend, frontend, testes e documentação"
        ),
        requirements=[
            "Conhecimento básico em PHP/Laravel ou Node.js, e/ou React com JavaScript/TypeScript",
            "Noções de SQL, HTTP/REST e Git",
        ],
        nice_to_have=[
            "Conhecimento básico em Docker",
            "Experiência com frameworks modernos (Laravel, Nest, Next, etc.)",
            "Inglês para leitura técnica",
        ],
    )


def test_job_priority_catalog_recovers_priorities_from_raw_vacancy_text():
    job = JobPosting(
        raw_text=(
            "Desenvolvedor Fullstack Junior\n"
            "REQUISITOS\n"
            "- Conhecimento em React\n"
            "- Noções de SQL\n"
            "DIFERENCIAIS\n"
            "- Conhecimento em Docker\n"
        ),
        title="",
    )

    catalog = _job_priority_catalog(job)

    assert catalog
    assert any("React" in item["text"] for item in catalog)
    assert any("Docker" in item["text"] for item in catalog)


def _brief() -> AIEmailBrief:
    return AIEmailBrief(
        matches=(
            AIEmailBriefMatch(
                category="atividade",
                vacancy_priority="Desenvolver melhorias e novas funcionalidades",
                candidate_evidence="Manutenção e evolução do sistema, atuando no front-end e no back-end.",
                source_field="experiences[0].activities[0]",
                source_context="Niceplanet | Desenvolvedor Fullstack Junior | SMGEO",
            ),
            AIEmailBriefMatch(
                category="requisito",
                vacancy_priority="Conhecimento básico em PHP/Laravel ou Node.js, e/ou React",
                candidate_evidence="Realizei correções de bugs e ajustes de funcionalidades com React, PHP e Node.js.",
                source_field="experiences[0].activities[1]",
                source_context="Niceplanet | Desenvolvedor Fullstack Junior | SMGEO",
            ),
            AIEmailBriefMatch(
                category="requisito",
                vacancy_priority="Noções de SQL, HTTP/REST e Git",
                candidate_evidence="Integrei APIs REST e apoiei operações em bancos relacionais.",
                source_field="experiences[0].activities[2]",
                source_context="Niceplanet | Desenvolvedor Fullstack Junior | SMGEO",
            ),
            AIEmailBriefMatch(
                category="diferencial",
                vacancy_priority="Conhecimento básico em Docker",
                candidate_evidence="Docker",
                source_field="skills[6]",
            ),
            AIEmailBriefMatch(
                category="diferencial",
                vacancy_priority="Inglês para leitura técnica",
                candidate_evidence="Inglês - intermediário para leitura e escrita técnica",
                source_field="languages[0]",
            ),
        )
    )


def _checks(*failed: str) -> dict:
    return {
        name: {
            "passed": name not in failed,
            "details": "Falha específica." if name in failed else "Critério atendido.",
            "correction": f"Corrija {name}." if name in failed else "",
        }
        for name in CHECK_NAMES
    }


def _valid_body(*, opening: str = "Tenho interesse na oportunidade de Desenvolvedor Fullstack Junior da Elev Tecnologia.") -> str:
    return (
        "Olá,\n\n"
        f"{opening} A proposta de desenvolver melhorias em um produto real combina com o momento em que busco aprofundar "
        "minha atuação no front-end e no back-end, aprendendo com acompanhamento técnico e contribuindo com entregas concretas.\n\n"
        "Na Niceplanet, atuo na manutenção e evolução do Sistema SMGEO, realizando correções de bugs e ajustes de "
        "funcionalidades com React, PHP e Node.js. Também integro APIs REST, gerencio estado com React Context e apoio "
        "operações em bancos relacionais. Essa experiência reúne atividades centrais da vaga e conhecimento prático em "
        "SQL, HTTP e Git, sem deixar de lado a disposição para receber feedback e continuar evoluindo.\n\n"
        "Gostaria de conversar sobre a oportunidade e conhecer melhor os desafios da equipe."
    )


def _catalog_item(items: list[dict], text: str) -> dict:
    return next(item for item in items if text in item["text"])


def test_generate_ai_email_brief_compares_complete_job_and_profile_in_focused_stages():
    captured = []

    def opener(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        if payload["format"]["required"] == ["direct_match", "reason"]:
            return _response({"direct_match": True, "reason": "A evidência sustenta a prioridade."})
        captured.append(payload)
        user_data = json.loads(payload["messages"][1]["content"])
        priorities = user_data["prioridades_da_vaga"]
        evidence = user_data["evidencias_do_candidato"]
        category = user_data["categoria_em_foco"]
        if category == "atividade":
            vacancy = _catalog_item(priorities, "melhorias e novas funcionalidades")
            candidate_evidence = _catalog_item(evidence, "correções de bugs")
        elif category == "requisito":
            vacancy = _catalog_item(priorities, "PHP/Laravel")
            candidate_evidence = _catalog_item(evidence, "APIs REST")
        else:
            vacancy = _catalog_item(priorities, "Inglês para leitura técnica")
            candidate_evidence = _catalog_item(evidence, "Inglês - intermediário")
        return _response(
            {"matches": [{"vacancy_id": vacancy["id"], "evidence_id": candidate_evidence["id"]}]}
        )

    brief = generate_ai_email_brief(_candidate_profile(), _job(), opener=opener)

    assert len(captured) == 3
    payload = captured[0]
    system_prompt = payload["messages"][0]["content"]
    user_data = json.loads(payload["messages"][1]["content"])
    evidence = user_data["evidencias_do_candidato"]
    assert all(item["model"] == DEFAULT_OLLAMA_EMAIL_ANALYSIS_MODEL for item in captured)
    assert all(item["options"]["num_ctx"] == 32768 for item in captured)
    assert all(item["format"]["required"] == ["matches"] for item in captured)
    assert all(item["format"]["properties"]["matches"]["maxItems"] <= 6 for item in captured)
    assert all(
        json.loads(item["messages"][1]["content"])["prioridades_da_vaga"]
        == user_data["prioridades_da_vaga"]
        for item in captured
    )
    assert {
        json.loads(item["messages"][1]["content"])["categoria_em_foco"]
        for item in captured
    } == {"atividade", "requisito", "diferencial"}
    assert "Compare a vaga inteira com o perfil profissional inteiro" in system_prompt
    assert "A seleção é inteiramente semântica" in system_prompt
    assert "cobertura completa, não preencher uma cota" in system_prompt
    assert "sempre vence skill" in system_prompt
    assert "avalie cada parte separadamente" in system_prompt
    assert any(item["source_field"].startswith("experiences[") for item in evidence)
    assert any("início declarado: 2025" in item["source_context"] for item in evidence)
    assert any(item["source_field"].startswith("projects[") for item in evidence)
    assert any(item["source_field"].startswith("languages[") for item in evidence)
    assert any(item["source_field"].startswith("skills[") for item in evidence)
    assert all("nilvanlopes" not in json.dumps(item).lower() for item in evidence)
    assert len(brief.matches) == 3
    assert brief.matches[0].source_context.startswith("Niceplanet")
    assert brief.matches[-1].category == "diferencial"


def test_generate_ai_email_brief_rejects_unknown_references():
    def opener(request, timeout):
        return _response({"matches": [{"vacancy_id": "v999", "evidence_id": "e999"}]})

    with pytest.raises(AIEmailGenerationError, match="referência inexistente"):
        generate_ai_email_brief(_candidate_profile(), _job(), opener=opener)


def test_generate_ai_email_brief_accepts_top_level_match_list_from_model():
    def opener(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        if payload["format"]["required"] == ["direct_match", "reason"]:
            return _response({"direct_match": True, "reason": "A evidência sustenta a prioridade."})
        user_data = json.loads(payload["messages"][1]["content"])
        focus_id = user_data["focus_vacancy_ids"][0]
        content = [
            {
                "vacancy_id": focus_id,
                "evidence_id": user_data["evidencias_do_candidato"][0]["id"],
            }
        ]
        return FakeResponse({"choices": [{"message": {"content": json.dumps(content)}}]})

    brief = generate_ai_email_brief(
        _candidate_profile(),
        JobPosting(raw_text="Vaga", title="Desenvolvedor", description="Desenvolver melhorias."),
        opener=opener,
    )

    assert len(brief.matches) == 1


def test_generate_ai_email_brief_validates_extra_pairs_when_model_exceeds_schema_limit():
    def opener(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        if payload["format"]["required"] == ["direct_match", "reason"]:
            return _response({"direct_match": True, "reason": "A evidência sustenta a prioridade."})
        user_data = json.loads(payload["messages"][1]["content"])
        vacancy_id = user_data["focus_vacancy_ids"][0]
        matches = [
            {"vacancy_id": vacancy_id, "evidence_id": evidence["id"]}
            for evidence in user_data["evidencias_do_candidato"]
        ]
        return _response({"matches": matches})

    brief = generate_ai_email_brief(
        _candidate_profile(),
        JobPosting(raw_text="Vaga", title="Desenvolvedor", description="Desenvolver melhorias."),
        opener=opener,
    )

    assert len(brief.matches) > 4


def test_generate_ai_email_brief_recovers_ids_from_malformed_model_json():
    def opener(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        if payload["format"]["required"] == ["direct_match", "reason"]:
            return _response({"direct_match": True, "reason": "A evidência sustenta a prioridade."})
        user_data = json.loads(payload["messages"][1]["content"])
        vacancy_id = user_data["focus_vacancy_ids"][0]
        evidence_id = user_data["evidencias_do_candidato"][0]["id"]
        content = (
            '{"matches": ['
            '{"vacancy_id": "' + vacancy_id + '", '
            '"priority_text": "texto extra", '
            '"evidence_id": "' + evidence_id + '", '
            "\"reasoning\": 'campo extra com aspas inválidas'}"
            "]}"
        )
        return FakeResponse({"choices": [{"message": {"content": content}}]})

    brief = generate_ai_email_brief(
        _candidate_profile(),
        JobPosting(raw_text="Vaga", title="Desenvolvedor", description="Desenvolver melhorias."),
        opener=opener,
    )

    assert len(brief.matches) == 1


def test_generate_ai_email_requests_one_complete_body_and_preserves_it():
    body = (
        "Olá,\n\n"
        "Tenho interesse na vaga de Desenvolvedor Fullstack Junior da Elev Tecnologia, especialmente pela atuação em "
        "produtos SaaS dentro de um ambiente colaborativo.\n\n"
        "Na Niceplanet, atuo na manutenção e evolução de um sistema no front-end e no back-end, realizando correções de "
        "bugs com React, PHP e Node.js. Também integro APIs REST e apoio operações em bancos relacionais; além disso, tenho "
        "conhecimento em Docker e inglês intermediário para leitura técnica.\n\n"
        "Gostaria de conversar sobre como essa trajetória pode contribuir para as próximas entregas da equipe."
    )
    captured = {}

    def opener(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        captured["payload"] = payload
        captured["timeout"] = timeout
        return _response({"subject": "Desenvolvedor Fullstack Junior", "body": body})

    result = generate_ai_email(
        _candidate_profile(),
        _job(),
        alignment_brief=_brief(),
        opener=opener,
    )

    payload = captured["payload"]
    system_prompt = payload["messages"][0]["content"]
    user_data = json.loads(payload["messages"][1]["content"])
    assert payload["model"] == DEFAULT_OLLAMA_EMAIL_MODEL
    assert payload["options"]["num_ctx"] == 6144
    assert payload["options"]["num_predict"] == 384
    assert payload["format"] == "json"
    assert user_data["ano_atual"] == date.today().year
    assert "Rapidez no aprendizado de novas tecnologias e metodologias" in user_data[
        "atributos_profissionais_declarados"
    ]
    assert user_data["genero_gramatical_candidato"] == "masculino"
    assert user_data["cargo_para_email"] == "Desenvolvedor Fullstack Junior"
    assert user_data["vaga"]["title"] == "Desenvolvedor Fullstack Junior"
    assert user_data["brief_de_alinhamento"] == _brief().to_dict()
    assert "perfil_profissional" not in user_data
    assert "Escreva o conteúdo completo de body de uma vez" in system_prompt
    assert "não o use como forma artificial de se chamar" in system_prompt
    assert 'Nunca escreva alternativas como "interessado(a)"' in system_prompt
    assert "Evidência de PHP autoriza mencionar PHP" in system_prompt
    assert "mas nunca Laravel" in system_prompt
    assert "Manifestar interesse, vontade ou intenção presente de aprender" in system_prompt
    assert "tipo de produto ou adjetivo promocional" in system_prompt
    assert "sem evidência direta correspondente" in system_prompt
    assert "Cada correção é uma restrição" in system_prompt
    assert payload["options"]["temperature"] == 0.1
    assert captured["timeout"] == 300.0
    assert user_data["correcoes_obrigatorias"] == []
    assert result.subject == "Desenvolvedor Fullstack Junior"
    assert result.body == body


def test_generate_ai_email_without_brief_uses_full_sanitized_profile():
    def opener(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        user_data = json.loads(payload["messages"][1]["content"])
        profile = user_data["perfil_profissional"]
        assert profile["experiences"]
        assert profile["projects"]
        assert profile["languages"]
        assert profile["skills"]
        assert "name" not in profile
        assert "email" not in profile
        assert "phone" not in profile
        return _response(
            {
                "subject": "Desenvolvedor Fullstack Junior",
                "body": "Olá,\n\nTenho interesse na oportunidade.\n\nMinha atuação é aderente à vaga.\n\nGostaria de conversar.",
            }
        )

    result = generate_ai_email(_candidate_profile(), _job(), opener=opener)

    assert result.body.startswith("Olá,")


def test_generate_ai_email_retries_after_invalid_json_contract():
    calls = []

    def opener(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        calls.append(payload)
        if len(calls) == 1:
            return _response({"title": "Desenvolvedor", "body": "Olá, tenho interesse."})
        return _response({"subject": "Desenvolvedor", "body": "Olá, tenho interesse."})

    result = generate_ai_email(_candidate_profile(), _job(), alignment_brief=_brief(), opener=opener)

    assert result.subject == "Desenvolvedor"
    assert len(calls) == 2
    assert calls[0]["format"] == "json"
    assert calls[1]["messages"][-2]["role"] == "assistant"
    assert "exatamente os campos subject e body" in calls[1]["messages"][-1]["content"]


@pytest.mark.parametrize(
    ("invalid_content", "expected_error"),
    [
        ({"subject": "Desenvolvedor"}, "Campos obrigatórios ausentes"),
        (
            {"subject": "Desenvolvedor", "body": "Olá, tenho interesse.", "extra": "inválido"},
            "Campos inesperados",
        ),
        ({"subject": 123, "body": "Olá, tenho interesse."}, "subject do e-mail deve ser texto"),
        ({"subject": "Desenvolvedor", "body": "   "}, "corpo de e-mail vazio"),
    ],
)
def test_generate_ai_email_rejects_invalid_json_contract(invalid_content, expected_error):
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        return _response(invalid_content)

    with pytest.raises(AIEmailGenerationError, match=expected_error):
        generate_ai_email(_candidate_profile(), _job(), alignment_brief=_brief(), opener=opener)

    assert calls == 2


def test_generate_reviewed_ai_email_builds_brief_once_and_rewrites_complete_draft():
    calls = []

    def opener(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        calls.append(payload)
        if payload["format"] == "json":
            writer_calls = [call for call in calls if call["format"] == "json"]
            user_data = json.loads(payload["messages"][1]["content"])
            assert payload["model"] == DEFAULT_OLLAMA_EMAIL_MODEL
            assert user_data["brief_de_alinhamento"]["matches"]
            if len(writer_calls) == 1:
                return _response(
                        {
                            "subject": "Desenvolvedor Fullstack Junior",
                            "body": _valid_body(),
                        }
                    )
            assert "rascunho_anterior" not in user_data
            assert "feedback_da_revisao" not in user_data
            assert "Corrija vacancy_alignment." in user_data["correcoes_obrigatorias"]
            return _response(
                {
                    "subject": "Desenvolvedor Fullstack Junior",
                    "body": _valid_body(),
                }
            )

        required = payload["format"]["required"]
        if required == ["direct_match", "reason"]:
            return _response({"direct_match": True, "reason": "A evidência sustenta a prioridade."})
        if required == ["matches"]:
            user_data = json.loads(payload["messages"][1]["content"])
            return _response(
                {
                    "matches": [
                        {
                            "vacancy_id": user_data["focus_vacancy_ids"][0],
                            "evidence_id": user_data["evidencias_do_candidato"][0]["id"],
                        }
                    ]
                }
            )

        review_calls = [
            call
            for call in calls
            if isinstance(call["format"], dict) and "checks" in call["format"]["required"]
        ]
        review_data = json.loads(payload["messages"][1]["content"])
        assert payload["model"] == DEFAULT_OLLAMA_MODEL
        assert review_data["brief_de_alinhamento"]["matches"]
        if len(review_calls) == 1:
            return _response(
                {
                    "checks": _checks("vacancy_alignment"),
                    "approved": False,
                    "score": 6,
                    "issues": ["O texto repete o mesmo argumento."],
                    "feedback": "Elimine a repetição entre os parágrafos.",
                }
            )
        return _response(
            {
                "checks": _checks(),
                "approved": True,
                "score": 9,
                "issues": [],
                "feedback": "",
            }
        )

    result = generate_reviewed_ai_email(_candidate_profile(), _job(), opener=opener)

    assert len(
        [
            call
            for call in calls
            if isinstance(call["format"], dict) and call["format"]["required"] == ["matches"]
        ]
    ) == 3
    assert len(result.attempts) == 2
    assert result.final_review.passed is True
    assert result.alignment_brief is not None
    assert "(a)" not in result.email.subject
    assert "Tenho interesse" in result.email.body


def test_generate_reviewed_ai_email_fails_after_rejections():
    def opener(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        if payload["format"] == "json":
            return _response(
                {
                    "subject": "Desenvolvedor(a)",
                    "body": "Olá,\n\nEstou interessado(a).\n\nRepito o argumento.\n\nRepito o argumento.",
                }
            )
        return _response(
            {
                "checks": _checks("identity_and_gender"),
                "approved": False,
                "score": 4,
                "issues": ["Há marcação de gênero '(a)'."],
                "feedback": "Use o gênero masculino informado.",
            }
        )

    with pytest.raises(AIEmailReviewError, match="não gerou um e-mail aprovado"):
        generate_reviewed_ai_email(
            _candidate_profile(),
            _job(),
            alignment_brief=_brief(),
            opener=opener,
            max_attempts=2,
        )


def test_generate_reviewed_ai_email_repairs_objective_format_before_semantic_review():
    calls = []

    def opener(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        calls.append(payload)
        if payload["format"] == "json":
            writer_calls = [call for call in calls if call["format"] == "json"]
            user_data = json.loads(payload["messages"][1]["content"])
            if len(writer_calls) == 1:
                assert user_data["correcoes_obrigatorias"] == []
                return _response(
                    {
                        "subject": "Desenvolvedor(a) Fullstack Junior",
                        "body": "Olá,\n\nTenho interesse.\n\nAtuo com React.\n\nEstou disponível. Gostaria de conversar.",
                    }
                )
            assert "rascunho_anterior" not in user_data
            assert any("105-130 palavras" in item for item in user_data["correcoes_obrigatorias"])
            assert any("gênero gramatical" in item for item in user_data["correcoes_obrigatorias"])
            assert any("única frase" in item for item in user_data["correcoes_obrigatorias"])
            return _response(
                {
                    "subject": "Desenvolvedor Fullstack Junior",
                    "body": _valid_body(),
                }
            )
        return _response(
            {
                "checks": _checks(),
                "approved": True,
                "score": 9,
                "issues": [],
                "feedback": "",
            }
        )

    result = generate_reviewed_ai_email(
        _candidate_profile(),
        _job(),
        alignment_brief=_brief(),
        opener=opener,
        max_attempts=2,
    )

    writer_calls = [call for call in calls if call["format"] == "json"]
    review_calls = [
        call
        for call in calls
        if isinstance(call["format"], dict) and "checks" in call["format"].get("required", [])
    ]
    assert len(writer_calls) == 2
    assert len(review_calls) == 1
    assert result.attempts[0].review.source == "local"
    assert result.attempts[1].revision_directives
    assert result.final_review.passed is True


def test_review_ai_email_requires_all_structured_checks_to_pass():
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        return _response(
            {
                "checks": _checks("factual_fidelity"),
                "approved": calls == 1,
                "score": 10 if calls == 1 else 8,
                "issues": [] if calls == 1 else ["factual_fidelity: Há afirmação sem fonte."],
                "feedback": "" if calls == 1 else "Remova a afirmação sem fonte.",
            }
        )

    review = review_ai_email(
        _candidate_profile(),
        _job(),
        AIEmailContent(subject="Desenvolvedor Fullstack Junior", body=_valid_body()),
        alignment_brief=_brief(),
        opener=opener,
    )

    assert calls == 2
    assert review.approved is False
    assert review.score == 8
    assert review.passed is False
    assert review.checks[0].name == "factual_fidelity"
    assert review.checks[0].passed is False


def test_review_ai_email_objectively_rejects_disallowed_generic_expressions():
    def opener(request, timeout):
        return _response(
            {
                "checks": _checks(),
                "approved": True,
                "score": 10,
                "issues": [],
                "feedback": "",
            }
        )

    review = review_ai_email(
        _candidate_profile(),
        _job(),
        AIEmailContent(
            subject="Desenvolvedor Fullstack Junior",
            body=_valid_body(opening="A vaga se alinha perfeitamente ao meu perfil profissional."),
        ),
        alignment_brief=_brief(),
        opener=opener,
    )

    persuasive_check = next(check for check in review.checks if check.name == "persuasive_quality")
    assert review.approved is False
    assert review.score == 8
    assert review.passed is False
    assert persuasive_check.passed is False
    assert "alinhamento perfeito" in persuasive_check.details
    assert f"persuasive_quality: {persuasive_check.details}" in review.issues
    assert "formulações concretas" in review.feedback


def test_review_ai_email_receives_complete_factual_sources_and_format_metrics():
    captured = {}
    body = _valid_body(opening="Atuo com desenvolvimento fullstack desde 2025 e tenho interesse na vaga da Elev Tecnologia.")

    def opener(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _response(
            {
                "checks": _checks(),
                "approved": True,
                "score": 9,
                "issues": [],
                "feedback": "",
            }
        )

    review = review_ai_email(
        _candidate_profile(),
        _job(),
        AIEmailContent(subject="Desenvolvedor Fullstack Junior", body=body),
        alignment_brief=_brief(),
        opener=opener,
    )

    request_payload = captured["payload"]
    system_prompt = request_payload["messages"][0]["content"]
    user_data = json.loads(request_payload["messages"][1]["content"])
    profile = user_data["perfil_profissional_completo"]
    metrics = user_data["metricas_formato"]
    assert review.passed is True
    assert request_payload["model"] == DEFAULT_OLLAMA_MODEL
    assert user_data["ano_atual"] == date.today().year
    assert user_data["cargo_para_email"] == "Desenvolvedor Fullstack Junior"
    assert user_data["vaga"]["title"] == "Desenvolvedor Fullstack Junior"
    assert profile["summary"] == "Atuo com desenvolvimento fullstack desde 2025."
    assert profile["experiences"][0]["started_at"] == "2025"
    assert "PHP" in profile["skills"]
    assert "Laravel" not in profile["skills"]
    assert metrics["starts_with_exact_greeting"] is True
    assert metrics["paragraphs_after_greeting"] == 3
    assert metrics["word_count_after_greeting"] > 10
    assert "uma data de início explícita menor ou igual ao ano atual não é futura" in system_prompt
    assert "PHP no perfil comprova PHP, nunca Laravel" in system_prompt
    assert "source_kind=skill permite somente" in system_prompt
    assert "audite separadamente cada tecnologia" in request_payload["messages"][2]["content"]
    assert '"tenho vontade de aprender"' in system_prompt
    assert "validados objetivamente antes desta chamada" in system_prompt
    assert "tipo de produto ou descrição promocional" in system_prompt


def test_review_ai_email_accepts_legacy_flat_checks_from_model():
    def opener(request, timeout):
        return _response(
            {
                "factual_fidelity": True,
                "vacancy_alignment": False,
                "persuasive_quality": True,
                "cohesion_and_non_repetition": False,
                "identity_and_gender": True,
                "language_and_format": True,
                "approved": False,
                "score": 7,
                "issues": [
                    {
                        "control": "vacancy_alignment",
                        "issue_text": "Inclui uma prática sem evidência.",
                        "feedback": "Remova a prática sem fonte.",
                    },
                    {
                        "control": "cohesion_and_non_repetition",
                        "issue_text": "Repete a mesma tecnologia.",
                        "feedback": "Una os argumentos repetidos.",
                    },
                ],
            }
        )

    review = review_ai_email(
        _candidate_profile(),
        _job(),
        AIEmailContent(
            subject="Desenvolvedor Fullstack Junior",
            body=_valid_body(),
        ),
        alignment_brief=_brief(),
        opener=opener,
    )

    assert review.passed is False
    assert "vacancy_alignment: Inclui uma prática sem evidência." in review.issues
    assert "Remova a prática sem fonte." in review.feedback
    assert review.checks[1].name == "vacancy_alignment"
    assert review.checks[1].passed is False


def test_review_ai_email_retries_malformed_json():
    calls = []

    def opener(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        calls.append(payload)
        if len(calls) == 1:
            return FakeResponse({"choices": [{"message": {"content": '{"checks":'}}]})
        return _response(
            {
                "checks": _checks(),
                "approved": True,
                "score": 9,
                "issues": [],
                "feedback": "",
            }
        )

    review = review_ai_email(
        _candidate_profile(),
        _job(),
        AIEmailContent(
            subject="Desenvolvedor Fullstack Junior",
            body=_valid_body(),
        ),
        alignment_brief=_brief(),
        opener=opener,
    )

    assert review.passed is True
    assert len(calls) == 2
    assert calls[1]["messages"][-2] == {"role": "assistant", "content": '{"checks":'}
    assert "Repita a auditoria completa" in calls[1]["messages"][-1]["content"]


def test_review_ai_email_preserves_aliases_and_defaults_to_safe_rejection():
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        return _response(
            {
                "factual_fidelity": True,
                    "vacancy_alignment": False,
                "persuasive_quality": True,
                "cohesion_and_non_repetition": True,
                "identity_and_gender": True,
                "language_and_format": True,
                "issues": [
                    {
                            "issue_type": "vacancy_alignment",
                        "description": "O argumento principal foi omitido.",
                        "correction_guidance": "Inclua a evidência mais forte do brief.",
                    }
                ],
            }
        )

    review = review_ai_email(
        _candidate_profile(),
        _job(),
        AIEmailContent(
            subject="Desenvolvedor Fullstack Junior",
            body=_valid_body(),
        ),
        alignment_brief=_brief(),
        opener=opener,
    )

    assert calls == 1
    assert review.approved is False
    assert review.score == 8
    assert review.passed is False
    assert review.issues == ("vacancy_alignment: O argumento principal foi omitido.",)
    assert review.checks[1].details == "O argumento principal foi omitido."
    assert review.feedback == "Inclua a evidência mais forte do brief."


def test_review_ai_email_rejects_repeated_malformed_json():
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        return FakeResponse({"choices": [{"message": {"content": "{"}}]})

    with pytest.raises(AIEmailGenerationError, match="não respeitou o contrato JSON da revisão"):
        review_ai_email(
            _candidate_profile(),
            _job(),
            AIEmailContent(subject="Desenvolvedor", body="Olá,\n\nTenho interesse."),
            alignment_brief=_brief(),
            opener=opener,
        )

    assert calls == 2


def test_review_ai_email_rejects_score_outside_zero_to_ten():
    def opener(request, timeout):
        return _response(
            {
                "checks": _checks(),
                "approved": True,
                "score": 85,
                "issues": [],
                "feedback": "",
            }
        )

    with pytest.raises(AIEmailGenerationError, match="intervalo de 0 a 10"):
        review_ai_email(
            _candidate_profile(),
            _job(),
            AIEmailContent(subject="Desenvolvedor Fullstack Junior", body="Olá,\n\nTenho interesse na vaga."),
            alignment_brief=_brief(),
            opener=opener,
        )
