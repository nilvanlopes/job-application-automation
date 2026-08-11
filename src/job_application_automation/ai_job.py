from __future__ import annotations

import json

from .ai_client import AIClient, AIProviderError
from .json_utils import parse_strict_json_object
from .models import JobPosting, is_resume_delivery_instruction
from .ollama import DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL, OllamaError, chat_completion


class AIJobExtractionError(RuntimeError):
    pass


JOB_EXTRACTION_ATTEMPTS = 2


def extract_job_with_ai(
    text: str,
    *,
    base_url: str | None = None,
    model: str | None = None,
    request_timeout: float = 90.0,
    opener=None,
    ai_client: AIClient | None = None,
) -> JobPosting:
    baseline = JobPosting.from_text(text)
    resolved_model = (model or DEFAULT_OLLAMA_MODEL).strip()
    kwargs = {}
    if opener is not None:
        kwargs["opener"] = opener
    feedback = ""
    last_review: dict | None = None
    last_job: JobPosting | None = None
    for attempt in range(1, JOB_EXTRACTION_ATTEMPTS + 1):
        data = _call_job_extraction(
            baseline.raw_text,
            feedback=feedback,
            ai_client=ai_client,
            base_url=base_url,
            resolved_model=resolved_model,
            request_timeout=request_timeout,
            kwargs=kwargs,
        )
        job = _job_from_ai_data(data, baseline)
        last_job = job
        review = _call_job_review(
            baseline.raw_text,
            data,
            ai_client=ai_client,
            base_url=base_url,
            resolved_model=resolved_model,
            request_timeout=request_timeout,
            kwargs=kwargs,
        )
        last_review = review
        if bool(review.get("approved")):
            return job
        feedback = _string(review.get("feedback")) or "; ".join(_strings(review.get("issues")))

    if last_job is not None and _looks_like_clean_professional_title(last_job.title):
        return last_job

    details = _string((last_review or {}).get("feedback")) or "a IA não validou o cargo profissional extraído"
    raise AIJobExtractionError(f"A IA não estruturou um cargo adequado para o currículo: {details}")


def _build_messages(raw_text: str) -> list[dict[str, str]]:
    system_content = (
        "Você estrutura anúncios de vagas em português do Brasil. Analise somente o texto "
        "fornecido, corrija ruídos evidentes de OCR e preencha os campos relevantes. "
        "Não invente empresa, contato, requisitos, benefícios ou tecnologias. Use string "
        "vazia ou lista vazia quando a informação não estiver presente. Preserve e-mails e "
        "telefones exatamente como aparecem. O campo title será usado como título profissional "
        "logo abaixo do nome do candidato no currículo: ele deve conter somente o cargo, sem "
        "frases de anúncio, chamadas como 'temos vaga', nome da empresa, local, modalidade, "
        "prefixo de candidatura ou instruções de envio. O campo company deve conter a empresa "
        "somente quando ela estiver explícita no texto. Explique em title_evidence e "
        "company_evidence quais trechos do anúncio sustentam esses campos. Extraia também "
        "instruções explícitas de candidatura, como assunto exigido, GitHub, LinkedIn, "
        "disponibilidade, valor pretendido, contratos ativos ou perguntas a responder. "
        "Não trate chamadas genéricas para enviar ou encaminhar o currículo como perguntas "
        "nem como application_instructions; frases como 'Interessados, enviem seu currículo', "
        "'envie o currículo para o e-mail informado' e 'venha fazer parte do time' são apenas "
        "orientações de entrega ou divulgação. "
        "Use requested_email_subject somente quando o anúncio pedir um assunto exato."
    )
    return [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": json.dumps(
                {"objetivo": "Estruturar os dados da vaga", "texto_extraido": raw_text},
                ensure_ascii=False,
            ),
        },
    ]


def _build_retry_messages(raw_text: str, feedback: str) -> list[dict[str, str]]:
    messages = _build_messages(raw_text)
    messages.append(
        {
            "role": "user",
            "content": (
                "A revisão rejeitou a estruturação anterior. Refaça a extração obedecendo ao feedback "
                f"sem aplicar regras fixas e sem inventar dados: {feedback}"
            ),
        }
    )
    return messages


def _build_review_messages(raw_text: str, data: dict) -> list[dict[str, str]]:
    system_content = (
        "Você revisa a estruturação de uma vaga para proteger um currículo profissional. "
        "Aprove somente se title for um cargo profissional limpo que poderia aparecer abaixo "
        "do nome do candidato no currículo. Reprove se title contiver frase promocional, "
        "manchete de anúncio, nome da empresa, local, modalidade, instrução de envio ou "
        "marcadores de rede social. Verifique também se company não foi inventada e se "
        "contatos explícitos foram preservados. Verifique se instruções explícitas de candidatura "
        "foram preservadas sem virarem title. Chamadas genéricas para enviar o currículo ou fazer "
        "parte do time são orientações de entrega, não perguntas obrigatórias, e devem ser "
        "removidas de application_instructions. Não corrija por lista de palavras; interprete "
        "o anúncio e dê feedback semântico curto para uma nova extração quando reprovar."
    )
    return [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "objetivo": "Revisar a estruturação da vaga antes de gerar currículo",
                    "texto_extraido": raw_text,
                    "vaga_estruturada": data,
                },
                ensure_ascii=False,
            ),
        },
    ]


def _schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "company": {"type": "string"},
            "location": {"type": "string"},
            "work_model": {"type": "string"},
            "contact_email": {"type": "string"},
            "contact_whatsapp": {"type": "string"},
            "description": {"type": "string"},
            "requirements": {"type": "array", "items": {"type": "string"}},
            "nice_to_have": {"type": "array", "items": {"type": "string"}},
            "benefits": {"type": "array", "items": {"type": "string"}},
            "requested_email_subject": {"type": "string"},
            "application_instructions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "kind": {
                            "type": "string",
                            "enum": [
                                "resume_or_linkedin",
                                "github_or_portfolio",
                                "legacy_php_paragraph",
                                "availability_and_compensation",
                                "active_contracts",
                                "custom",
                            ],
                        },
                        "required": {"type": "boolean"},
                        "evidence_hint": {"type": "string"},
                    },
                    "required": ["text", "kind", "required", "evidence_hint"],
                    "additionalProperties": False,
                },
            },
            "keywords": {"type": "array", "items": {"type": "string"}},
            "title_evidence": {"type": "string"},
            "company_evidence": {"type": "string"},
        },
        "required": [
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
        ],
        "additionalProperties": False,
    }


def _review_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "approved": {"type": "boolean"},
            "issues": {"type": "array", "items": {"type": "string"}},
            "feedback": {"type": "string"},
        },
        "required": ["approved", "issues", "feedback"],
        "additionalProperties": False,
    }


def _call_job_extraction(
    raw_text: str,
    *,
    feedback: str,
    ai_client: AIClient | None,
    base_url: str | None,
    resolved_model: str,
    request_timeout: float,
    kwargs: dict,
) -> dict:
    messages = _build_retry_messages(raw_text, feedback) if feedback else _build_messages(raw_text)
    response_payload = _call_json(
        messages,
        response_format=_schema(),
        ai_client=ai_client,
        base_url=base_url,
        resolved_model=resolved_model,
        request_timeout=request_timeout,
        kwargs=kwargs,
    )
    content = _extract_output_text(response_payload)
    _log_ai_output(content)
    return _parse_ai_object(content)


def _call_job_review(
    raw_text: str,
    data: dict,
    *,
    ai_client: AIClient | None,
    base_url: str | None,
    resolved_model: str,
    request_timeout: float,
    kwargs: dict,
) -> dict:
    response_payload = _call_json(
        _build_review_messages(raw_text, data),
        response_format=_review_schema(),
        ai_client=ai_client,
        base_url=base_url,
        resolved_model=resolved_model,
        request_timeout=request_timeout,
        kwargs=kwargs,
    )
    content = _extract_output_text(response_payload)
    _log_ai_output(content)
    return _parse_ai_object(content)


def _call_json(
    messages: list[dict[str, str]],
    *,
    response_format: object,
    ai_client: AIClient | None,
    base_url: str | None,
    resolved_model: str,
    request_timeout: float,
    kwargs: dict,
) -> dict:
    try:
        if ai_client is not None:
            return ai_client.call_json(
                messages,
                response_format=response_format,
                model_role="default",
                request_timeout=request_timeout,
            )
        return chat_completion(
            messages,
            base_url=base_url or DEFAULT_OLLAMA_BASE_URL,
            model=resolved_model,
            response_format=response_format,
            request_timeout=request_timeout,
            **kwargs,
        )
    except (OllamaError, AIProviderError) as exc:
        raise AIJobExtractionError(str(exc)) from exc


def _parse_ai_object(content: str) -> dict:
    try:
        return parse_strict_json_object(content)
    except json.JSONDecodeError as exc:
        raise AIJobExtractionError("A IA não retornou JSON válido para a vaga.") from exc


def _looks_like_clean_professional_title(title: str) -> bool:
    value = _string(title)
    if not value or len(value.split()) < 2:
        return False
    lowered = value.casefold()
    blocked_fragments = (
        "temos vaga",
        "estamos contratando",
        "candidate",
        "currículo",
        "curriculo",
        "@",
        "http",
        "remoto",
        "home office",
        "pj",
    )
    if any(fragment in lowered for fragment in blocked_fragments):
        return False
    professional_terms = (
        "desenvolvedor",
        "desenvolvedora",
        "analista",
        "engenheiro",
        "engenheira",
        "técnico",
        "tecnico",
        "programador",
        "programadora",
        "suporte",
    )
    return any(term in lowered for term in professional_terms)


def _job_from_ai_data(data: dict, baseline: JobPosting) -> JobPosting:
    title = _string(data.get("title"))
    if not title:
        raise AIJobExtractionError("A IA não retornou o cargo da vaga.")
    return JobPosting(
        raw_text=baseline.raw_text,
        title=title,
        company=_string(data.get("company")),
        location=_string(data.get("location")) or baseline.location,
        work_model=_string(data.get("work_model")) or baseline.work_model,
        contact_email=_string(data.get("contact_email")) or baseline.contact_email,
        contact_whatsapp=_string(data.get("contact_whatsapp")) or baseline.contact_whatsapp,
        description=_string(data.get("description")) or baseline.description,
        requirements=_strings(data.get("requirements")) or baseline.requirements,
        nice_to_have=_strings(data.get("nice_to_have")) or baseline.nice_to_have,
        benefits=_strings(data.get("benefits")) or baseline.benefits,
        requested_email_subject=_string(data.get("requested_email_subject")) or baseline.requested_email_subject,
        application_instructions=_instructions(data.get("application_instructions"))
        or baseline.application_instructions,
        keywords=_strings(data.get("keywords")) or baseline.keywords,
    )


def _extract_output_text(payload: dict) -> str:
    message = payload.get("message", {})
    if isinstance(message, dict):
        if message.get("refusal"):
            raise AIJobExtractionError(f"A IA recusou a estruturação: {message['refusal']}")
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content

    choices = payload.get("choices", [])
    if choices:
        message = choices[0].get("message", {})
        if message.get("refusal"):
            raise AIJobExtractionError(f"A IA recusou a estruturação: {message['refusal']}")
        content = message.get("content")
        if isinstance(content, str):
            return content
    raise AIJobExtractionError("O Ollama não retornou texto para a vaga.")


def _log_ai_output(content: str) -> None:
    return None


def _string(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _strings(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _instructions(value) -> list:
    if not isinstance(value, list):
        return []
    from .models import ApplicationInstruction

    instructions: list[ApplicationInstruction] = []
    allowed_kinds = {
        "resume_or_linkedin",
        "github_or_portfolio",
        "legacy_php_paragraph",
        "availability_and_compensation",
        "active_contracts",
        "custom",
    }
    for item in value:
        if not isinstance(item, dict):
            continue
        text = _string(item.get("text"))
        if not text or is_resume_delivery_instruction(text):
            continue
        kind = _string(item.get("kind")) or "custom"
        if kind not in allowed_kinds:
            kind = "custom"
        required = item.get("required")
        instructions.append(
            ApplicationInstruction(
                text=text,
                kind=kind,
                required=required if isinstance(required, bool) else True,
                evidence_hint=_string(item.get("evidence_hint")),
            )
        )
    return instructions
