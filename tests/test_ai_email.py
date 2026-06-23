from __future__ import annotations

import json

import pytest

from job_application_automation.ai_email import (
    AIEmailGenerationError,
    AIEmailReviewError,
    generate_ai_email,
    generate_reviewed_ai_email,
)
from job_application_automation.models import CandidateProfile, EducationEntry, JobPosting
from job_application_automation.ollama import DEFAULT_OLLAMA_MODEL


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


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


def test_generate_ai_email_sends_candidate_and_job_data_to_ollama(capsys):
    captured = {}

    def fake_opener(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "subject": "Interesse na vaga de Python",
                                    "body": "Olá.\n\nTenho interesse na vaga de Python.\n\nAtenciosamente,",
                                }
                            )
                        }
                    }
                ]
            }
        )

    job = JobPosting.from_text("Desenvolvedor Python\nRequisitos: Python e Docker")
    result = generate_ai_email(
        _candidate_profile(),
        job,
        resume_markdown="# Currículo base\nExperiência real",
        model=DEFAULT_OLLAMA_MODEL,
        opener=fake_opener,
    )

    user_data = json.loads(captured["payload"]["messages"][1]["content"])
    system_prompt = captured["payload"]["messages"][0]["content"]
    assert captured["url"].endswith("/api/chat")
    assert captured["payload"]["model"] == DEFAULT_OLLAMA_MODEL
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["options"]["temperature"] == 0
    assert captured["payload"]["format"]["required"] == ["subject", "body"]
    assert user_data["vaga"]["raw_text"] == job.raw_text
    assert "name" not in user_data["candidato"]
    assert "email" not in user_data["candidato"]
    assert "phone" not in user_data["candidato"]
    assert "linkedin" not in user_data["candidato"]
    assert user_data["candidato"]["skills"]
    assert user_data["formacao"][0]["status"] == "interrompido"
    assert user_data["curriculo_base"] == ""
    assert user_data["cargo_para_email"] == "Desenvolvedor Python"
    assert "Equipe <nome da empresa>," in system_prompt
    assert "Prezados senhores" in system_prompt
    assert "[Seu Nome]" in system_prompt
    assert "em Palmas-TO" in system_prompt
    assert "oportunidade localizada em" in system_prompt
    assert result.subject == "Interesse na vaga de Python"
    assert "Python" in result.body
    output = capsys.readouterr().out
    assert "[job-application] Resposta bruta da IA na geração do e-mail" in output
    assert '"subject": "Interesse na vaga de Python"' in output


def test_generate_ai_email_requires_subject_from_model():
    def fake_opener(request, timeout):
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"body": "Olá.\n\nTenho interesse na vaga.\n\nAtenciosamente,"})
                        }
                    }
                ]
            }
        )

    with pytest.raises(AIEmailGenerationError, match="assunto de e-mail vazio"):
        generate_ai_email(
            _candidate_profile(),
            JobPosting.from_text("Vaga Python"),
            model=DEFAULT_OLLAMA_MODEL,
            opener=fake_opener,
        )


def test_generate_ai_email_rejects_invalid_json():
    def fake_opener(request, timeout):
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": "Rascunho pronto, mas sem JSON válido"
                        }
                    }
                ]
            }
        )

    with pytest.raises(AIEmailGenerationError, match="JSON válido"):
        generate_ai_email(
            _candidate_profile(),
            JobPosting.from_text("Vaga Python"),
            model=DEFAULT_OLLAMA_MODEL,
            opener=fake_opener,
        )


def test_generate_ai_email_uses_default_ollama_model():
    def fake_opener(request, timeout):
        assert request.full_url.endswith("/api/chat")
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"subject": "Interesse na vaga", "body": "Olá.\n\nTenho interesse.\n\nAtenciosamente,"}
                            )
                        }
                    }
                ]
            }
        )

    result = generate_ai_email(
        _candidate_profile(),
        JobPosting.from_text("Vaga Python"),
        opener=fake_opener,
    )

    assert result.subject == "Interesse na vaga"


def test_generate_ai_email_preserves_model_text_without_rewriting():
    def fake_opener(request, timeout):
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "subject": "Analista de Sistemas em TI - Fazendão Agronegoclo",
                                    "body": (
                                        "Prezados senhores,\n\n"
                                        "Me chamo Nilvan Lopes e tenho interesse na vaga de Analista de Sistemas em TI na Fazendão Agronegoclo.\n\n"
                                        "Atenciosamente,\n[Seu Nome]"
                                    ),
                                }
                            )
                        }
                    }
                ]
            }
        )

    job = JobPosting.from_text(
        "Analista de Sistemas em TI\nEmpresa: Fazendão Agronegócio\nLocal: Palmas-TO"
    )
    result = generate_ai_email(
        _candidate_profile(),
        job,
        model=DEFAULT_OLLAMA_MODEL,
        opener=fake_opener,
    )

    assert result.subject == "Analista de Sistemas em TI - Fazendão Agronegoclo"
    assert "Me chamo Nilvan Lopes" in result.body
    assert "Agronegoclo" in result.body
    assert "[Seu Nome]" in result.body


def test_generate_reviewed_ai_email_regenerates_with_review_feedback():
    candidate = _candidate_profile()
    candidate.name = "Nilvan Lopes Cruz"
    calls = []

    def fake_opener(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        calls.append(payload)
        required = payload["format"]["required"]
        if required == ["subject", "body"] and len(calls) == 1:
            return FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "subject": "Programador Junior",
                                        "body": (
                                            "Olá,\n\n"
                                            "Me chamo Nilvan Lopes Cruz e tenho interesse na vaga de Programador Junior.\n\n"
                                            "Atenciosamente,\n[Seu Nome]"
                                        ),
                                    }
                                )
                            }
                        }
                    ]
                }
            )
        if required == ["approved", "score", "issues", "feedback"] and len(calls) == 2:
            review_prompt = payload["messages"][0]["content"]
            assert '"Olá," é saudação neutra e permitida' in review_prompt
            assert 'Nunca exija o prefixo "Candidatura -"' in review_prompt
            assert '"Eu" no meio de uma frase não é autoapresentação' in review_prompt
            assert "classifique como assinatura manual" in review_prompt
            assert "não usar fechamento com vírgula" in review_prompt
            assert "frase completa terminada em ponto final" in review_prompt
            assert 'Nunca reprove frases como "Tenho interesse na vaga"' in review_prompt
            assert 'Não use "tom genérico", "tom artificial" ou "informações inventadas"' in review_prompt
            return FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "approved": False,
                                        "score": 4,
                                        "issues": ["Há autoapresentação com assinatura manual."],
                                        "feedback": "Reescreva sem 'Me chamo' e sem placeholder.",
                                    }
                                )
                            }
                        }
                    ]
                }
            )
        if required == ["subject", "body"]:
            user_data = json.loads(payload["messages"][1]["content"])
            assert "Reescreva sem 'Me chamo'" in user_data["feedback_da_revisao"]
            assert "Me chamo Nilvan Lopes Cruz" in user_data["rascunho_anterior"]["body"]
            return FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "subject": "Programador Junior",
                                        "body": (
                                            "Olá,\n\n"
                                            "Tenho interesse na vaga de Programador Junior e posso contribuir com minha experiência em React e Angular.\n\n"
                                            "Atenciosamente,"
                                        ),
                                    }
                                )
                            }
                        }
                    ]
                }
            )
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "approved": True,
                                    "score": 9,
                                    "issues": [],
                                    "feedback": "",
                                }
                            )
                        }
                    }
                ]
            }
        )

    result = generate_reviewed_ai_email(
        candidate,
        JobPosting.from_text("Programador Junior"),
        model=DEFAULT_OLLAMA_MODEL,
        opener=fake_opener,
    )

    assert result.email.subject == "Programador Junior"
    assert "Tenho interesse na vaga de Programador Junior" in result.email.body
    assert len(result.attempts) == 2
    assert result.final_review.passed is True


def test_generate_reviewed_ai_email_fails_after_rejections():
    def fake_opener(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        if payload["format"]["required"] == ["subject", "body"]:
            return FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "subject": "Programador Junior",
                                        "body": "Olá,\n\nMe chamo e tenho interesse na vaga de Programador Junior.",
                                    }
                                )
                            }
                        }
                    ]
                }
            )
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "approved": False,
                                    "score": 3,
                                    "issues": ["Frase quebrada: 'Me chamo e'."],
                                    "feedback": "Reescreva a abertura sem autoapresentação.",
                                }
                            )
                        }
                    }
                ]
            }
        )

    with pytest.raises(AIEmailReviewError, match="não gerou um e-mail aprovado"):
        generate_reviewed_ai_email(
            _candidate_profile(),
            JobPosting.from_text("Programador Junior"),
            model=DEFAULT_OLLAMA_MODEL,
            opener=fake_opener,
            max_attempts=2,
        )
