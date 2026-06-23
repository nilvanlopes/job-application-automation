from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .json_utils import parse_strict_json_object
from .models import CandidateProfile, JobPosting
from .ollama import DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL, OllamaError, chat_completion


EMAIL_REVIEW_MIN_SCORE = 8
EMAIL_REVIEW_MAX_ATTEMPTS = 5


class AIEmailGenerationError(RuntimeError):
    pass


class AIEmailReviewError(AIEmailGenerationError):
    def __init__(self, message: str, attempts: tuple["AIEmailReviewAttempt", ...]):
        super().__init__(message)
        self.attempts = attempts


@dataclass(frozen=True, slots=True)
class AIEmailContent:
    subject: str
    body: str


@dataclass(frozen=True, slots=True)
class AIEmailReview:
    approved: bool
    score: int
    issues: tuple[str, ...]
    feedback: str

    @property
    def passed(self) -> bool:
        return self.approved and self.score >= EMAIL_REVIEW_MIN_SCORE and not self.issues


@dataclass(frozen=True, slots=True)
class AIEmailReviewAttempt:
    number: int
    email: AIEmailContent
    review: AIEmailReview


@dataclass(frozen=True, slots=True)
class ReviewedAIEmailContent:
    email: AIEmailContent
    attempts: tuple[AIEmailReviewAttempt, ...]

    @property
    def final_review(self) -> AIEmailReview:
        return self.attempts[-1].review


def generate_ai_email(
    candidate: CandidateProfile,
    job: JobPosting,
    *,
    resume_markdown: str = "",
    review_feedback: str = "",
    previous_draft: AIEmailContent | None = None,
    base_url: str | None = None,
    model: str | None = None,
    request_timeout: float = 60.0,
    opener=None,
) -> AIEmailContent:
    candidate_data = _candidate_data_for_email(candidate)
    resolved_model = (model or DEFAULT_OLLAMA_MODEL).strip()
    kwargs = {}
    if opener is not None:
        kwargs["opener"] = opener
    try:
        response_payload = chat_completion(
            _build_messages(candidate_data, resume_markdown, job, review_feedback, previous_draft),
            base_url=base_url or DEFAULT_OLLAMA_BASE_URL,
            model=resolved_model,
            response_format=_schema(),
            request_timeout=request_timeout,
            **kwargs,
        )
    except OllamaError as exc:
        raise AIEmailGenerationError(str(exc)) from exc

    output_text = _extract_output_text(response_payload)
    _log_ai_output(output_text)
    try:
        generated = parse_strict_json_object(output_text)
    except json.JSONDecodeError as exc:
        raise AIEmailGenerationError(
            f"A resposta da IA não contém JSON válido para o e-mail. Resposta bruta: {output_text.strip()}"
        ) from exc

    email = AIEmailContent(
        subject=_string(generated.get("subject")),
        body=_string(generated.get("body")),
    )
    if not email.subject:
        raise AIEmailGenerationError("A IA retornou um assunto de e-mail vazio.")
    if not email.body:
        raise AIEmailGenerationError("A IA retornou um corpo de e-mail vazio.")
    return email


def review_ai_email(
    candidate: CandidateProfile,
    job: JobPosting,
    email: AIEmailContent,
    *,
    resume_markdown: str = "",
    base_url: str | None = None,
    model: str | None = None,
    request_timeout: float = 60.0,
    opener=None,
) -> AIEmailReview:
    resolved_model = (model or DEFAULT_OLLAMA_MODEL).strip()
    kwargs = {}
    if opener is not None:
        kwargs["opener"] = opener
    try:
        response_payload = chat_completion(
            _build_review_messages(candidate.to_dict(), resume_markdown, job, email),
            base_url=base_url or DEFAULT_OLLAMA_BASE_URL,
            model=resolved_model,
            response_format=_review_schema(),
            request_timeout=request_timeout,
            **kwargs,
        )
    except OllamaError as exc:
        raise AIEmailGenerationError(str(exc)) from exc

    output_text = _extract_output_text(response_payload)
    _log_review_output(output_text)
    try:
        generated = parse_strict_json_object(output_text)
    except json.JSONDecodeError as exc:
        raise AIEmailGenerationError(
            f"A resposta da IA não contém JSON válido para a revisão. Resposta bruta: {output_text.strip()}"
        ) from exc
    return _review_from_dict(generated)


def generate_reviewed_ai_email(
    candidate: CandidateProfile,
    job: JobPosting,
    *,
    resume_markdown: str = "",
    base_url: str | None = None,
    model: str | None = None,
    request_timeout: float = 60.0,
    max_attempts: int = EMAIL_REVIEW_MAX_ATTEMPTS,
    opener=None,
) -> ReviewedAIEmailContent:
    attempts: list[AIEmailReviewAttempt] = []
    feedback = ""
    previous_draft = None
    for number in range(1, max(1, max_attempts) + 1):
        email = generate_ai_email(
            candidate,
            job,
            resume_markdown=resume_markdown,
            review_feedback=feedback,
            previous_draft=previous_draft,
            base_url=base_url,
            model=model,
            request_timeout=request_timeout,
            opener=opener,
        )
        review = review_ai_email(
            candidate,
            job,
            email,
            resume_markdown=resume_markdown,
            base_url=base_url,
            model=model,
            request_timeout=request_timeout,
            opener=opener,
        )
        attempt = AIEmailReviewAttempt(number=number, email=email, review=review)
        attempts.append(attempt)
        if review.passed:
            return ReviewedAIEmailContent(email=email, attempts=tuple(attempts))
        feedback = _review_feedback_for_regeneration(review)
        previous_draft = email

    raise AIEmailReviewError(
        "A IA não gerou um e-mail aprovado pela revisão automática "
        f"após {len(attempts)} tentativa(s). Último feedback: {feedback}",
        tuple(attempts),
    )


def _build_messages(
    candidate_data: dict,
    resume_markdown: str,
    job: JobPosting,
    review_feedback: str = "",
    previous_draft: AIEmailContent | None = None,
) -> list[dict[str, str]]:
    system_content = """
    Você redige e-mails de candidatura profissionais em português do Brasil.

    Sua resposta deve gerar exatamente dois campos:
    Assunto: complemento curto, profissional e específico para a vaga, sem incluir o prefixo "Candidatura -".
    Corpo: texto do e-mail.

    Regras obrigatórias para o corpo do e-mail:
    - Use tom profissional, natural, direto e específico para a vaga.
    - Não use linguagem exagerada, artificial ou informal, como "estou encantado", "estou apaixonado pela oportunidade" ou frases parecidas. Prefira formulações profissionais como "tenho interesse na oportunidade".
    - Use somente fatos presentes nos dados fornecidos.
    - Não invente experiências, resultados, tempo de experiência, conhecimentos, habilidades, ferramentas, certificações, cursos, cargos ou informações pessoais.
    - Não adicione informações de contato, links, telefone, e-mail, LinkedIn, GitHub ou site.
    - Não use listas, títulos internos ou assinatura no corpo.
    - Não escreva o nome do candidato, "[Seu Nome]", "Seu Nome" ou qualquer placeholder no final do corpo; a assinatura já será adicionada automaticamente fora da IA.
    - Não inicie o texto com autoapresentações como "Me chamo", "Meu nome é" ou "Sou <nome do candidato>". A assinatura automática já identifica o candidato.
    - Não use fechamento em formato de assinatura, como "Atenciosamente," em uma linha separada.
    - Encerre com uma frase natural de disponibilidade terminada em ponto final, sem nome, sem iniciais, sem "Eu" isolado e sem qualquer identificação pessoal.
    - Exemplo permitido de encerramento: "Fico à disposição para conversar sobre como posso contribuir com a vaga."
    - Exemplos proibidos de encerramento: "Atenciosamente,\nNome", "Disponível para novos desafios,\nNome", "Eu".
    - Inclua uma saudação neutra no início.
    - Não use saudações com gênero presumido, como "Prezados senhores", "Prezadas senhoras", "Senhores" ou "Senhoras".
    - Se o nome da empresa estiver disponível, use uma saudação neutra no formato "Equipe <nome da empresa>,".
    - Se o nome da empresa não estiver disponível, use "Olá,".
    - Escreva dois ou três parágrafos curtos.
    - Use somente caracteres UTF-8 e texto em português do Brasil.

    Regras obrigatórias sobre formação:
    Considere o campo de formação exatamente como informado. Os status "concluido", "formado", "em andamento" e "interrompido" têm significados diferentes.
    Nunca diga que o candidato concluiu, se formou, é graduado ou possui diploma se o status não indicar isso explicitamente.
    Se a formação estiver "em andamento", diga apenas que está em andamento.
    Se a formação estiver "interrompido", diga apenas que foi interrompida, se isso for relevante para a vaga.
    Não infira conclusão, diploma ou graduação.

    Regras obrigatórias sobre vaga e gênero:
    Interprete nomes de vagas de forma natural. Por exemplo, "Pessoa desenvolvedora frontend" significa vaga para desenvolvimento frontend.
    Use o campo "cargo_para_email" como nome da vaga no assunto e no corpo.
    No assunto, não inclua o nome da empresa.
    Ao citar a vaga no corpo, não use o padrão "cargo + empresa", como "vaga de Analista de Sistemas em TI na Empresa" ou "Analista de Sistemas em TI - Empresa".
    O nome da empresa pode aparecer no corpo somente em menções naturais que não estejam coladas ao cargo.
    Não copie sufixos do cargo que pareçam nome de empresa, marca ou local após hífen, travessão ou barra.
    Ao mencionar a localização da vaga, use formulações diretas como "em Palmas-TO"; evite "vaga localizada em", "oportunidade localizada em" ou "cargo localizado em".
    Não altere, corrija ou reescreva nomes próprios; se houver dúvida sobre grafia, omita o nome próprio.
    Adapte o texto ao gênero do candidato quando essa informação estiver disponível nos dados fornecidos.
    Se o gênero não estiver disponível, use linguagem neutra e profissional sem inventar gênero.

    Antes de escrever, verifique mentalmente se cada informação usada aparece nos dados fornecidos. Se uma informação não estiver nos dados, não use.
    """ 
    return [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "objetivo": "Gerar o corpo personalizado do e-mail de candidatura.",
                    "candidato": candidate_data,
                    "formacao": candidate_data.get("education", []),
                    "curriculo_base": "",
                    "cargo_para_email": _job_title_without_company(job),
                    "vaga": job.to_dict(),
                    "rascunho_anterior": (
                        {"subject": previous_draft.subject, "body": previous_draft.body}
                        if previous_draft
                        else None
                    ),
                    "feedback_da_revisao": review_feedback,
                },
                ensure_ascii=False,
            ),
        },
    ]


def _build_review_messages(
    candidate_data: dict,
    resume_markdown: str,
    job: JobPosting,
    email: AIEmailContent,
) -> list[dict[str, str]]:
    system_content = f"""
    Você é revisor de qualidade de e-mails de candidatura em português do Brasil.

    Avalie se o rascunho está pronto para ser enviado. Não reescreva o e-mail.
    A saída deve ser JSON com:
    - approved: booleano.
    - score: inteiro de 0 a 10.
    - issues: lista somente com problemas que bloqueiam o envio.
    - feedback: orientação objetiva para a próxima tentativa, quando houver reprovação.

    Critérios bloqueantes:
    - Texto com erro gramatical evidente, frase quebrada ou lacuna como "Me chamo e".
    - Autoapresentação proibida com nome ou placeholder no corpo, como "Me chamo", "Meu nome é", "Sou <nome do candidato>" ou "Me chamo [Seu Nome]".
    - Placeholder como "[Seu Nome]", "Seu Nome" ou assinatura manual do candidato no corpo.
    - Contradição objetiva com os dados fornecidos, apenas quando o texto afirma o oposto do status informado.
    - Informações de contato no corpo, como links, telefone, e-mail, LinkedIn, GitHub ou site.
    - Formação tratada como concluída quando o status não informar conclusão.
    - Saudação com gênero presumido ou inadequada.
    - Assunto incluindo o prefixo "Candidatura -"; esse prefixo será aplicado depois.
    - Assunto vazio, corpo vazio ou corpo sem relação clara com a vaga.

    Regras de interpretação:
    - "Olá," é saudação neutra e permitida; não reprove por gênero quando a saudação for "Olá,".
    - Nunca inclua "Saudação com gênero presumido" em issues quando a saudação for "Olá,".
    - Não use "tom genérico", "tom artificial" ou "informações inventadas" como problema bloqueante sem apontar uma contradição objetiva e verificável.
    - O assunto gerado deve ser apenas o complemento. Nunca exija o prefixo "Candidatura -"; reprove se ele aparecer.
    - O corpo não deve conter assinatura manual nem fechamento em formato de assinatura, porque a assinatura automática será adicionada depois.
    - Frases profissionais em primeira pessoa são permitidas quando não contêm nome, placeholder ou assinatura, por exemplo: "Tenho interesse na vaga", "Atualmente estou cursando..." e "Possuo experiência em...".
    - Nunca reprove frases como "Tenho interesse na vaga", "Atualmente estou cursando..." ou "Possuo experiência em..." como autoapresentação.
    - "Eu" no meio de uma frase não é autoapresentação nem nome do candidato.
    - Se "Atenciosamente," aparecer em linha separada, ou se "Eu", iniciais, nome abreviado ou nome completo aparecerem depois de uma despedida, classifique como assinatura manual, não como autoapresentação.
    - Encerramentos terminados com vírgula e seguidos por nome, iniciais ou "Eu" são assinatura manual.
    - Quando reprovar por assinatura manual, o feedback deve dizer para encerrar com uma frase completa terminada em ponto final, como "Fico à disposição para conversar sobre como posso contribuir com a vaga.", e não usar fechamento com vírgula.
    - Se houver autoapresentação proibida com nome/placeholder ou assinatura manual no corpo, reprove mesmo que o restante esteja bom.

    Aprove somente se score >= {EMAIL_REVIEW_MIN_SCORE} e não houver problemas bloqueantes.
    Se reprovar, explique o que a IA escritora deve mudar sem sugerir correção por script.
    """
    return [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "objetivo": "Revisar qualidade e fidelidade do e-mail gerado.",
                    "candidato": candidate_data,
                    "formacao": candidate_data.get("education", []),
                    "curriculo_base": resume_markdown,
                    "cargo_para_email": _job_title_without_company(job),
                    "vaga": job.to_dict(),
                    "email_gerado": {
                        "subject": email.subject,
                        "body": email.body,
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]


def _schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": "Complemento curto e profissional do assunto do e-mail, sem o prefixo 'Candidatura -'.",
            },
            "body": {
                "type": "string",
                "description": "Corpo completo do e-mail, sem assunto e sem assinatura pessoal.",
            },
        },
        "required": ["subject", "body"],
        "additionalProperties": False,
    }


def _review_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "approved": {
                "type": "boolean",
                "description": "True somente quando o e-mail está pronto para envio.",
            },
            "score": {
                "type": "integer",
                "description": "Nota de qualidade de 0 a 10.",
            },
            "issues": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Problemas bloqueantes que impedem envio.",
            },
            "feedback": {
                "type": "string",
                "description": "Orientação objetiva para regenerar o e-mail quando reprovado.",
            },
        },
        "required": ["approved", "score", "issues", "feedback"],
        "additionalProperties": False,
    }


def _extract_output_text(payload: dict) -> str:
    message = payload.get("message", {})
    if isinstance(message, dict):
        if message.get("refusal"):
            raise AIEmailGenerationError(f"A IA recusou a geração: {message['refusal']}")
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content

    choices = payload.get("choices", [])
    if choices:
        message = choices[0].get("message", {})
        if message.get("refusal"):
            raise AIEmailGenerationError(f"A IA recusou a geração: {message['refusal']}")
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
    raise AIEmailGenerationError("O Ollama não retornou texto para o e-mail.")


def _log_ai_output(content: str) -> None:
    if content.strip():
        print("[job-application] Resposta bruta da IA na geração do e-mail:", flush=True)
        print(content.strip(), flush=True)


def _log_review_output(content: str) -> None:
    if content.strip():
        print("[job-application] Resposta bruta da IA na revisão do e-mail:", flush=True)
        print(content.strip(), flush=True)


def _string(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _review_from_dict(data: dict) -> AIEmailReview:
    approved = data.get("approved")
    score = data.get("score")
    issues = data.get("issues")
    feedback = data.get("feedback")
    if not isinstance(approved, bool):
        raise AIEmailGenerationError("A revisão da IA retornou 'approved' inválido.")
    if not isinstance(score, int):
        raise AIEmailGenerationError("A revisão da IA retornou 'score' inválido.")
    if not isinstance(issues, list) or not all(isinstance(item, str) for item in issues):
        raise AIEmailGenerationError("A revisão da IA retornou 'issues' inválido.")
    if not isinstance(feedback, str):
        raise AIEmailGenerationError("A revisão da IA retornou 'feedback' inválido.")
    return AIEmailReview(
        approved=approved,
        score=max(0, min(10, score)),
        issues=tuple(item.strip() for item in issues if item.strip()),
        feedback=feedback.strip(),
    )


def _review_feedback_for_regeneration(review: AIEmailReview) -> str:
    pieces = list(review.issues)
    if review.feedback:
        pieces.append(review.feedback)
    return "\n".join(f"- {piece}" for piece in pieces) or "Reescreva o e-mail com mais qualidade e aderência à vaga."


def _candidate_data_for_email(candidate: CandidateProfile) -> dict:
    data = candidate.to_dict()
    for key in ("name", "email", "phone", "website", "github", "linkedin", "whatsapp"):
        data.pop(key, None)
    data["education"] = [
        entry
        for entry in data.get("education", [])
        if isinstance(entry, dict) and entry.get("status")
    ]
    return data


def _job_title_without_company(job: JobPosting) -> str:
    title = job.title.strip()
    company = job.company.strip()
    if not title or not company:
        return title or job.title

    company_suffix = re.compile(
        rf"\s*(?:[-–—/]|na|no|pela|pelo|da|do)\s+{re.escape(company)}\s*$",
        flags=re.IGNORECASE,
    )
    title = company_suffix.sub("", title).strip()
    title = re.sub(r"\s+[-–—/]\s*$", "", title).strip()
    return title or job.title
