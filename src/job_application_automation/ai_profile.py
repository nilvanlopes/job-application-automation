from __future__ import annotations

import json
from pathlib import Path

from .json_utils import parse_strict_json_object
from .models import CandidateProfile, EducationEntry
from .ollama import DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL, OllamaError, chat_completion
from .paths import CANDIDATE_PROFILE_PATH


class CandidateProfileGenerationError(RuntimeError):
    pass


def generate_candidate_profile(
    resume_path: Path,
    *,
    base_url: str | None = None,
    model: str | None = None,
    profile_path: Path = CANDIDATE_PROFILE_PATH,
    request_timeout: float = 90.0,
    opener=None,
) -> CandidateProfile:
    resume_text = resume_path.read_text(encoding="utf-8")
    resolved_model = (model or DEFAULT_OLLAMA_MODEL).strip()
    kwargs = {}
    if opener is not None:
        kwargs["opener"] = opener
    try:
        response_payload = chat_completion(
            _build_messages(resume_text),
            base_url=base_url or DEFAULT_OLLAMA_BASE_URL,
            model=resolved_model,
            response_format=_schema(),
            request_timeout=request_timeout,
            **kwargs,
        )
    except OllamaError as exc:
        raise CandidateProfileGenerationError(str(exc)) from exc

    output_text = _extract_output_text(response_payload)
    _log_ai_output(output_text)
    try:
        data = parse_strict_json_object(output_text)
    except json.JSONDecodeError as exc:
        raise CandidateProfileGenerationError(
            f"A IA não retornou JSON válido para o perfil do candidato. Resposta bruta: {output_text.strip()}"
        ) from exc

    candidate = _candidate_from_json(data)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        json.dumps(candidate.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return candidate


def _build_messages(resume_text: str) -> list[dict[str, str]]:
    system_content = (
        "Você estrutura um perfil de candidato a partir de um currículo em português do Brasil. "
        "Extraia somente fatos presentes no texto. Não invente nome, cargo, contatos, competências, "
        "formações, links ou destaques. Se um campo não estiver explicitamente presente, use string "
        "vazia ou lista vazia. Preserve exatamente e-mails, telefones e URLs. "
        "A formação deve ser uma lista de objetos com name, institution, status, level, started_at, ended_at e notes."
    )
    return [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "objetivo": "Estruturar o perfil do candidato para candidaturas.",
                    "curriculo_padrao": resume_text,
                },
                ensure_ascii=False,
            ),
        },
    ]


def _schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "title": {"type": "string"},
            "skills": {"type": "array", "items": {"type": "string"}},
            "education": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "institution": {"type": "string"},
                        "status": {"type": "string"},
                        "level": {"type": "string"},
                        "started_at": {"type": "string"},
                        "ended_at": {"type": "string"},
                        "notes": {"type": "string"},
                    },
                    "required": [
                        "name",
                        "institution",
                        "status",
                        "level",
                        "started_at",
                        "ended_at",
                        "notes",
                    ],
                    "additionalProperties": False,
                },
            },
            "summary": {"type": "string"},
            "email": {"type": "string"},
            "phone": {"type": "string"},
            "website": {"type": "string"},
            "github": {"type": "string"},
            "linkedin": {"type": "string"},
            "whatsapp": {"type": "string"},
            "highlights": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "name",
            "title",
            "skills",
            "education",
            "summary",
            "email",
            "phone",
            "website",
            "github",
            "linkedin",
            "whatsapp",
            "highlights",
        ],
        "additionalProperties": False,
    }


def _extract_output_text(payload: dict) -> str:
    message = payload.get("message", {})
    if isinstance(message, dict):
        if message.get("refusal"):
            raise CandidateProfileGenerationError(f"A IA recusou a geração: {message['refusal']}")
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content

    choices = payload.get("choices", [])
    if choices:
        message = choices[0].get("message", {})
        if message.get("refusal"):
            raise CandidateProfileGenerationError(f"A IA recusou a geração: {message['refusal']}")
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
    raise CandidateProfileGenerationError("O Ollama não retornou texto para o perfil do candidato.")


def _log_ai_output(content: str) -> None:
    print("[job-application] Resposta bruta da IA no profile do candidato:", flush=True)
    print(content.strip(), flush=True)


def _candidate_from_json(data: dict) -> CandidateProfile:
    return CandidateProfile(
        name=_string(data.get("name")),
        title=_string(data.get("title")),
        skills=_strings(data.get("skills")),
        education=[
            entry if isinstance(entry, EducationEntry) else EducationEntry(**entry)
            for entry in (data.get("education") or [])
        ],
        summary=_string(data.get("summary")),
        email=_string(data.get("email")),
        phone=_string(data.get("phone")),
        website=_string(data.get("website")),
        github=_string(data.get("github")),
        linkedin=_string(data.get("linkedin")),
        whatsapp=_string(data.get("whatsapp")),
        highlights=_strings(data.get("highlights")),
    )


def _string(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _strings(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
