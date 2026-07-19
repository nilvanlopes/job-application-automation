from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date

from .ai_client import AIClient, AIProviderError
from .json_utils import parse_strict_json_object
from .models import CandidateProfile, JobPosting
from .ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_CONTEXT_LENGTH,
    DEFAULT_OLLAMA_EMAIL_ANALYSIS_MODEL,
    DEFAULT_OLLAMA_EMAIL_MODEL,
    DEFAULT_OLLAMA_MODEL,
    OllamaError,
    chat_completion,
)


EMAIL_REVIEW_MIN_SCORE = 9
EMAIL_REVIEW_MAX_ATTEMPTS = 10
EMAIL_BODY_MIN_WORDS = 90
EMAIL_BODY_MAX_WORDS = 160
EMAIL_BODY_TARGET_MIN_WORDS = 105
EMAIL_BODY_TARGET_MAX_WORDS = 130
EMAIL_ALIGNMENT_MAX_MATCHES = 24
EMAIL_ALIGNMENT_MAX_MATCHES_PER_STAGE = 8
EMAIL_OLLAMA_CONTEXT_LENGTH = DEFAULT_OLLAMA_CONTEXT_LENGTH
# Bounds writer context and keeps local inference within a 10 GiB card.
EMAIL_WRITER_OLLAMA_CONTEXT_LENGTH = 6144
EMAIL_WRITER_MAX_OUTPUT_TOKENS = 384
EMAIL_WRITER_TEMPERATURE = 0.1
EMAIL_WRITER_REQUEST_TIMEOUT = 300.0
EMAIL_WRITER_FORMAT_ATTEMPTS = 2
EMAIL_WRITER_REQUIRED_FIELDS = frozenset({"subject", "body"})
EMAIL_REVIEW_FORMAT_ATTEMPTS = 2
EMAIL_DISALLOWED_EXPRESSION_PATTERNS = (
    (r"\balinh\w*\s+perfeit\w*\b", "alinhamento perfeito"),
    (r"\bperfil\s+ideal\b", "perfil ideal"),
    (r"\bs[oó]lid[oa]s?\s+experi[eê]nci\w*\b", "sólida experiência"),
    (r"\bagreg\w*\s+valor\b", "agregar valor"),
    (r"\bansios[oa]s?\b", "ansioso/ansiosa"),
    (r"\bávid[oa]s?\b", "ávido/ávida"),
    (r"\bme\s+preparou\b", "me preparou"),
    (r"\bdesde\s+o\s+primeiro\s+dia\b", "desde o primeiro dia"),
)
EMAIL_DISALLOWED_GENDER_MARKERS = (
    (r"\([ao]\)", "marcação '(a)' ou '(o)'"),
    (r"\b\w+/(?:a|o)\b", "alternativa de gênero com barra"),
)
EMAIL_REVIEW_CHECKS = (
    ("factual_fidelity", "Fidelidade factual"),
    ("vacancy_alignment", "Aderência à vaga"),
)


class AIEmailGenerationError(RuntimeError):
    pass


class AIEmailReviewError(AIEmailGenerationError):
    def __init__(
        self,
        message: str,
        attempts: tuple["AIEmailReviewAttempt", ...],
        alignment_brief: "AIEmailBrief | None" = None,
    ):
        super().__init__(message)
        self.attempts = attempts
        self.alignment_brief = alignment_brief


@dataclass(frozen=True, slots=True)
class AIEmailContent:
    subject: str
    body: str


@dataclass(frozen=True, slots=True)
class AIEmailBriefMatch:
    category: str
    vacancy_priority: str
    candidate_evidence: str
    source_field: str
    source_context: str = ""
    source_kind: str = ""


@dataclass(frozen=True, slots=True)
class AIEmailBrief:
    matches: tuple[AIEmailBriefMatch, ...]

    def to_dict(self) -> dict:
        return {
            "matches": [
                {
                    "category": match.category,
                    "vacancy_priority": match.vacancy_priority,
                    "candidate_evidence": match.candidate_evidence,
                    "source_field": match.source_field,
                    "source_context": match.source_context,
                    "source_kind": match.source_kind,
                }
                for match in self.matches
            ]
        }


@dataclass(frozen=True, slots=True)
class AIEmailReviewCheck:
    name: str
    passed: bool
    details: str
    correction: str = ""


@dataclass(frozen=True, slots=True)
class AIEmailReview:
    approved: bool
    score: int
    issues: tuple[str, ...]
    feedback: str
    checks: tuple[AIEmailReviewCheck, ...] = ()
    source: str = "ai"

    @property
    def passed(self) -> bool:
        checks_passed = not self.checks or all(check.passed for check in self.checks)
        return self.approved and self.score >= EMAIL_REVIEW_MIN_SCORE and not self.issues and checks_passed


@dataclass(frozen=True, slots=True)
class AIEmailReviewAttempt:
    number: int
    email: AIEmailContent
    review: AIEmailReview
    revision_directives: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReviewedAIEmailContent:
    email: AIEmailContent
    attempts: tuple[AIEmailReviewAttempt, ...]
    alignment_brief: AIEmailBrief | None = None

    @property
    def final_review(self) -> AIEmailReview:
        return self.attempts[-1].review


def generate_ai_email_brief(
    candidate: CandidateProfile,
    job: JobPosting,
    *,
    base_url: str | None = None,
    model: str | None = None,
    request_timeout: float = 120.0,
    opener=None,
    ai_client: AIClient | None = None,
) -> AIEmailBrief:
    candidate_data = _candidate_data_for_email(candidate)
    evidence_catalog = _candidate_evidence_catalog(candidate_data)
    vacancy_catalog = _job_priority_catalog(job)
    if not evidence_catalog:
        raise AIEmailGenerationError("O perfil do candidato não contém evidências profissionais para o e-mail.")
    if not vacancy_catalog:
        raise AIEmailGenerationError(
            "Não foi possível identificar atividades, requisitos ou diferenciais "
            "nos dados estruturados nem no texto original da vaga."
        )

    resolved_model = (model or DEFAULT_OLLAMA_EMAIL_ANALYSIS_MODEL).strip()
    kwargs = {"opener": opener} if opener is not None else {}
    vacancy_by_id = {item["id"]: item for item in vacancy_catalog}
    evidence_by_id = {item["id"]: item for item in evidence_catalog}
    matches: list[AIEmailBriefMatch] = []
    categories = tuple(dict.fromkeys(item["category"] for item in vacancy_catalog))
    for category in categories:
        focus_ids = tuple(
            item["id"]
            for item in vacancy_catalog
            if item["category"] == category
        )
        max_items = min(
            EMAIL_ALIGNMENT_MAX_MATCHES_PER_STAGE,
            len(focus_ids) + 3,
        )
        try:
            messages = _build_brief_messages(
                evidence_catalog,
                vacancy_catalog,
                category=category,
                focus_ids=focus_ids,
                max_items=max_items,
            )
            schema = _brief_schema(
                vacancy_ids=focus_ids,
                evidence_ids=tuple(item["id"] for item in evidence_catalog),
                max_items=max_items,
                allow_empty=True,
            )
            if ai_client is not None:
                response_payload = ai_client.call_json(
                    messages,
                    response_format=schema,
                    model_role="email_analysis",
                    task_label=f"Gerando mapa de aderência do e-mail ({category})",
                    context_length=EMAIL_OLLAMA_CONTEXT_LENGTH,
                    request_timeout=request_timeout,
                )
            else:
                response_payload = chat_completion(
                    messages,
                    base_url=base_url or DEFAULT_OLLAMA_BASE_URL,
                    model=resolved_model,
                    response_format=schema,
                    context_length=EMAIL_OLLAMA_CONTEXT_LENGTH,
                    request_timeout=request_timeout,
                    **kwargs,
                )
        except (OllamaError, AIProviderError) as exc:
            raise AIEmailGenerationError(str(exc)) from exc

        output_text = _extract_output_text(response_payload)
        _log_brief_output(output_text, category)
        try:
            generated = _parse_brief_output(output_text)
        except json.JSONDecodeError as exc:
            raise AIEmailGenerationError(
                "A resposta da IA não contém JSON válido para o mapa de aderência "
                f"na categoria '{category}'."
            ) from exc
        stage_brief = _brief_from_dict(
            generated,
            vacancy_by_id=vacancy_by_id,
            evidence_by_id=evidence_by_id,
            max_items=max_items,
            allow_empty=True,
        )
        for match in stage_brief.matches:
            if _brief_match_is_direct(
                match,
                base_url=base_url or DEFAULT_OLLAMA_BASE_URL,
                model=resolved_model,
                request_timeout=request_timeout,
                ai_client=ai_client,
                **kwargs,
            ):
                matches.append(match)

    unique_matches = _unique_brief_matches(matches)
    if not unique_matches:
        raise AIEmailGenerationError("A IA não retornou aderências factuais para orientar o e-mail.")
    if len(unique_matches) > EMAIL_ALIGNMENT_MAX_MATCHES:
        raise AIEmailGenerationError("A IA retornou aderências demais para o mapa do e-mail.")
    return AIEmailBrief(matches=tuple(unique_matches))


def _brief_match_is_direct(
    match: AIEmailBriefMatch,
    *,
    base_url: str,
    model: str,
    request_timeout: float,
    opener=None,
    ai_client: AIClient | None = None,
) -> bool:
    messages = [
        {
            "role": "system",
            "content": """
            Audite um único par entre prioridade de vaga e evidência profissional. Não escreva e-mail.

            direct_match é true somente quando a evidência sustenta diretamente ao menos uma parte explícita da prioridade,
            sem usar potencial, associação de ecossistema ou conhecimento externo. Uma prioridade com alternativas pode ser
            atendida por uma alternativa comprovada; isso não comprova as demais.

            Tecnologia, ferramenta, framework, idioma, prática, processo ou metodologia nomeados exigem o mesmo nome ou
            conceito na evidência. Atividade genérica não comprova ritual específico. Linguagem, framework ou ferramenta não
            comprovam motivação, comportamento, lógica, comunicação ou interesse de carreira.

            Avalie somente a parte sustentada, nunca a lista inteira. Se a prioridade disser "A, B e C" ou "A, B ou C", uma
            evidência explícita de B é direct_match=true para a parte B, mesmo sem A e C. Da mesma forma, uma evidência de uma
            categoria listada como alternativa atende essa alternativa; não exija as demais.

            Quando a prioridade pedir conhecimento básico, noções ou familiaridade, uma skill com o mesmo nome é evidência
            suficiente. Quando pedir experiência ou uma ação realizada, source_kind=skill não basta; candidate_evidence precisa
            descrever a experiência ou ação. Não exija que a evidência cubra partes independentes da prioridade além da parte
            usada na correspondência.

            Uma soft_skill que declare literalmente rapidez, facilidade ou disposição para aprender sustenta a parte de uma
            prioridade que peça vontade ou capacidade de aprender. Isso não comprova tecnologias, SaaS ou atividades presentes
            em outras partes da mesma prioridade, mas ainda é direct_match=true para a parte comportamental comprovada.

            Responda somente o JSON do schema. reason deve indicar, em uma frase curta, qual parte está ou não comprovada.
            """,
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "category": match.category,
                    "vacancy_priority": match.vacancy_priority,
                    "candidate_evidence": match.candidate_evidence,
                    "source_field": match.source_field,
                    "source_context": match.source_context,
                    "source_kind": match.source_kind,
                },
                ensure_ascii=False,
            ),
        },
    ]
    kwargs = {"opener": opener} if opener is not None else {}
    try:
        if ai_client is not None:
            response_payload = ai_client.call_json(
                messages,
                response_format=_brief_validation_schema(),
                model_role="email_analysis",
                task_label="Validando aderência factual do e-mail",
                context_length=EMAIL_OLLAMA_CONTEXT_LENGTH,
                request_timeout=request_timeout,
            )
        else:
            response_payload = chat_completion(
                messages,
                base_url=base_url,
                model=model,
                response_format=_brief_validation_schema(),
                context_length=EMAIL_OLLAMA_CONTEXT_LENGTH,
                request_timeout=request_timeout,
                **kwargs,
            )
    except (OllamaError, AIProviderError) as exc:
        raise AIEmailGenerationError(str(exc)) from exc

    output_text = _extract_output_text(response_payload)
    _log_brief_validation_output(output_text, match.vacancy_priority)
    try:
        generated = parse_strict_json_object(output_text)
    except json.JSONDecodeError as exc:
        raise AIEmailGenerationError(
            "A resposta da IA não contém JSON válido para validar uma aderência."
        ) from exc
    direct_match = generated.get("direct_match")
    reason = generated.get("reason")
    if not isinstance(direct_match, bool) or not isinstance(reason, str):
        raise AIEmailGenerationError("A IA retornou uma validação inválida para uma aderência.")
    return direct_match


def generate_ai_email(
    candidate: CandidateProfile,
    job: JobPosting,
    *,
    resume_markdown: str = "",
    review_feedback: str = "",
    previous_draft: AIEmailContent | None = None,
    revision_directives: tuple[str, ...] = (),
    attempt_number: int = 1,
    alignment_brief: AIEmailBrief | None = None,
    base_url: str | None = None,
    model: str | None = None,
    request_timeout: float = 120.0,
    opener=None,
    ai_client: AIClient | None = None,
) -> AIEmailContent:
    candidate_data = _candidate_data_for_email(candidate)
    resolved_model = (model or DEFAULT_OLLAMA_EMAIL_MODEL).strip()
    kwargs = {"opener": opener} if opener is not None else {}
    corrections = revision_directives or ((review_feedback,) if review_feedback.strip() else ())
    base_messages = _build_messages(
        candidate_data,
        job,
        revision_directives=corrections,
        attempt_number=attempt_number,
        alignment_brief=alignment_brief,
    )
    messages = base_messages
    last_error = ""
    last_output = ""

    for _ in range(EMAIL_WRITER_FORMAT_ATTEMPTS):
        try:
            if ai_client is not None:
                response_payload = ai_client.call_json(
                    messages,
                    response_format="json",
                    model_role="email_writer",
                    task_label="Gerando rascunho do e-mail de candidatura",
                    context_length=EMAIL_WRITER_OLLAMA_CONTEXT_LENGTH,
                    max_output_tokens=EMAIL_WRITER_MAX_OUTPUT_TOKENS,
                    temperature=EMAIL_WRITER_TEMPERATURE,
                    request_timeout=max(request_timeout, EMAIL_WRITER_REQUEST_TIMEOUT),
                )
            else:
                response_payload = chat_completion(
                    messages,
                    base_url=base_url or DEFAULT_OLLAMA_BASE_URL,
                    model=resolved_model,
                    response_format="json",
                    context_length=EMAIL_WRITER_OLLAMA_CONTEXT_LENGTH,
                    max_output_tokens=EMAIL_WRITER_MAX_OUTPUT_TOKENS,
                    temperature=EMAIL_WRITER_TEMPERATURE,
                    request_timeout=max(request_timeout, EMAIL_WRITER_REQUEST_TIMEOUT),
                    **kwargs,
                )
        except (OllamaError, AIProviderError) as exc:
            raise AIEmailGenerationError(str(exc)) from exc

        last_output = _extract_output_text(response_payload)
        _log_ai_output(last_output)
        try:
            generated = parse_strict_json_object(last_output)
            return _validated_email_content(generated)
        except json.JSONDecodeError:
            last_error = "a resposta não é um objeto JSON válido"
        except AIEmailGenerationError as exc:
            last_error = str(exc)

        messages = [
            *base_messages,
            {"role": "assistant", "content": last_output},
            {
                "role": "user",
                "content": (
                    f"A resposta anterior foi rejeitada: {last_error}. "
                    "Retorne somente um objeto JSON com exatamente os campos subject e body, "
                    "ambos como strings não vazias. Não use Markdown nem acrescente outros campos."
                ),
            },
        ]

    raise AIEmailGenerationError(
        "A IA não respeitou o contrato JSON do e-mail após "
        f"{EMAIL_WRITER_FORMAT_ATTEMPTS} tentativas. Último erro: {last_error}."
    )


def _validated_email_content(data: dict) -> AIEmailContent:
    fields = set(data)
    missing = sorted(EMAIL_WRITER_REQUIRED_FIELDS - fields)
    unexpected = sorted(fields - EMAIL_WRITER_REQUIRED_FIELDS)
    if missing:
        raise AIEmailGenerationError(f"Campos obrigatórios ausentes no e-mail: {', '.join(missing)}.")
    if unexpected:
        raise AIEmailGenerationError(f"Campos inesperados no e-mail: {', '.join(unexpected)}.")

    subject = data["subject"]
    body = data["body"]
    if not isinstance(subject, str):
        raise AIEmailGenerationError("O campo subject do e-mail deve ser texto.")
    if not isinstance(body, str):
        raise AIEmailGenerationError("O campo body do e-mail deve ser texto.")

    email = AIEmailContent(subject=subject.strip(), body=body.strip())
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
    alignment_brief: AIEmailBrief | None = None,
    base_url: str | None = None,
    model: str | None = None,
    request_timeout: float = 120.0,
    opener=None,
    ai_client: AIClient | None = None,
) -> AIEmailReview:
    candidate_data = _candidate_data_for_email(candidate)
    resolved_model = (model or DEFAULT_OLLAMA_MODEL).strip()
    kwargs = {"opener": opener} if opener is not None else {}
    base_messages = _build_review_messages(candidate_data, job, email, alignment_brief)
    messages = base_messages
    last_error = ""
    last_output = ""
    last_generated: dict | None = None

    for _ in range(EMAIL_REVIEW_FORMAT_ATTEMPTS):
        try:
            if ai_client is not None:
                response_payload = ai_client.call_json(
                    messages,
                    response_format=_review_schema(),
                    model_role="email_analysis",
                    task_label="Revisando e-mail de candidatura",
                    context_length=EMAIL_OLLAMA_CONTEXT_LENGTH,
                    request_timeout=request_timeout,
                )
            else:
                response_payload = chat_completion(
                    messages,
                    base_url=base_url or DEFAULT_OLLAMA_BASE_URL,
                    model=resolved_model,
                    response_format=_review_schema(),
                    context_length=EMAIL_OLLAMA_CONTEXT_LENGTH,
                    request_timeout=request_timeout,
                    **kwargs,
                )
        except (OllamaError, AIProviderError) as exc:
            raise AIEmailGenerationError(str(exc)) from exc

        last_output = _extract_output_text(response_payload)
        _log_review_output(last_output)
        try:
            generated = parse_strict_json_object(last_output)
            last_generated = generated
            return _apply_objective_review_checks(_review_from_dict(generated), email, job)
        except json.JSONDecodeError:
            last_error = "a resposta não é um objeto JSON válido"
        except AIEmailGenerationError as exc:
            last_error = str(exc)

        messages = [
            *base_messages,
            {"role": "assistant", "content": last_output},
            {
                "role": "user",
                "content": (
                    f"A revisão anterior foi rejeitada pelo validador: {last_error}. "
                    "Repita a auditoria completa e retorne somente um objeto JSON que obedeça exatamente ao schema."
                ),
            },
        ]

    if last_generated is not None:
        try:
            review = _review_from_dict(last_generated, allow_safe_rejection_defaults=True)
            return _apply_objective_review_checks(review, email, job)
        except AIEmailGenerationError:
            pass

    raise AIEmailGenerationError(
        "A IA não respeitou o contrato JSON da revisão após "
        f"{EMAIL_REVIEW_FORMAT_ATTEMPTS} tentativas. Último erro: {last_error}. "
        f"Última resposta: {last_output[:2000]}"
    )


def generate_reviewed_ai_email(
    candidate: CandidateProfile,
    job: JobPosting,
    *,
    resume_markdown: str = "",
    alignment_brief: AIEmailBrief | None = None,
    base_url: str | None = None,
    model: str | None = None,
    email_model: str | None = None,
    review_model: str | None = None,
    request_timeout: float = 120.0,
    max_attempts: int = EMAIL_REVIEW_MAX_ATTEMPTS,
    opener=None,
    ai_client: AIClient | None = None,
) -> ReviewedAIEmailContent:
    brief = alignment_brief or generate_ai_email_brief(
        candidate,
        job,
        base_url=base_url,
        model=model,
        request_timeout=request_timeout,
        opener=opener,
        ai_client=ai_client,
    )
    attempts: list[AIEmailReviewAttempt] = []
    revision_directives: tuple[str, ...] = ()
    for number in range(1, max(1, max_attempts) + 1):
        email = generate_ai_email(
            candidate,
            job,
            resume_markdown=resume_markdown,
            revision_directives=revision_directives,
            attempt_number=number,
            alignment_brief=brief,
            base_url=base_url,
            model=email_model,
            request_timeout=request_timeout,
            opener=opener,
            ai_client=ai_client,
        )
        review = _objective_email_review(email, job)
        if review is None:
            review = review_ai_email(
                candidate,
                job,
                email,
                resume_markdown=resume_markdown,
                alignment_brief=brief,
                base_url=base_url,
                model=review_model,
                request_timeout=request_timeout,
                opener=opener,
                ai_client=ai_client,
            )
        attempt = AIEmailReviewAttempt(
            number=number,
            email=email,
            review=review,
            revision_directives=revision_directives,
        )
        attempts.append(attempt)
        if review.passed:
            return ReviewedAIEmailContent(
                email=email,
                attempts=tuple(attempts),
                alignment_brief=brief,
            )
        revision_directives = _review_feedback_for_regeneration(review)

    raise AIEmailReviewError(
        "A IA não gerou um e-mail aprovado pela revisão automática "
        f"após {len(attempts)} tentativa(s). Últimas correções: "
        f"{' | '.join(revision_directives)}",
        tuple(attempts),
        brief,
    )


def _build_brief_messages(
    evidence_catalog: list[dict[str, str]],
    vacancy_catalog: list[dict[str, str]],
    *,
    category: str,
    focus_ids: tuple[str, ...],
    max_items: int,
) -> list[dict[str, str]]:
    system_content = f"""
    Você é responsável pela estratégia factual de um e-mail de candidatura. Não escreva o e-mail.

    Compare a vaga inteira com o perfil profissional inteiro. A lista "prioridades_da_vaga" contém atividades, requisitos,
    diferenciais e contexto; a lista "evidencias_do_candidato" contém todas as fontes profissionais autorizadas. Examine cada
    item das duas listas antes de selecionar. Nesta chamada, selecione somente a categoria "{category}" e somente vacancy_id
    presente em focus_vacancy_ids. Os demais itens da vaga servem apenas como contexto.

    Retorne até {max_items} correspondências diretas e úteis, ordenadas da mais forte para a menos forte. Cada correspondência
    deve usar somente um vacancy_id e um evidence_id existentes. Não copie nem reescreva os textos. "matches": [] é a resposta
    correta quando nenhuma prioridade em foco tiver prova.

    O objetivo é obter cobertura completa, não preencher uma cota: percorra cada prioridade em foco e inclua uma correspondência
    para toda prioridade que possua evidência direta. Omita toda prioridade sem prova; nunca escolha uma evidência apenas para
    fazer cada vacancy_id aparecer.

    CRITÉRIOS DE SELEÇÃO
    - Uma evidência é válida quando sustenta literalmente ou por paráfrase fiel a parte relevante da prioridade. Não use
      conhecimento externo, potencial, suposição ou proximidade entre tecnologias.
    - Em requisitos com alternativas, uma alternativa comprovada basta, mas não torna as demais verdadeiras.
    - Tecnologia, ferramenta, framework, idioma, prática, processo ou metodologia nomeados exigem o mesmo nome ou conceito na
      evidência. Uma tecnologia diferente, atividade genérica, qualidade de código, deploy ou colaboração não comprovam uma
      prática ou ritual específico.
    - Interesse de carreira, vontade de aprender, lógica, comunicação e outros atributos só podem ser ligados a uma declaração
      correspondente no perfil. Linguagem, framework ou ferramenta não comprovam motivação nem comportamento.
    - Quando uma prioridade combinar atributos ou requisitos independentes, avalie cada parte separadamente e inclua a melhor
      evidência para cada parte comprovada. Evidência de lógica não substitui evidência de vontade ou rapidez para aprender, e
      vice-versa; ambas podem gerar pares distintos para a mesma prioridade.
    - Um nome isolado em habilidades comprova conhecimento, não experiência prática, domínio, resultado ou tempo de uso.
      Use source_kind para distinguir a origem: skill comprova conhecimento declarado; experience_activity e project_activity
      comprovam a ação descrita; language comprova somente idioma e nível; soft_skill comprova somente o atributo escrito.
      Quando a prioridade pedir apenas conhecimento básico ou noções, uma skill de mesmo nome é válida. Quando pedir
      experiência ou uma ação, prefira obrigatoriamente experience_activity ou project_activity que contenha essa ação.
    - Uma atividade de experiência ou projeto comprova somente as ações, tecnologias e escopo que aparecem no texto e no
      contexto da fonte.
    - Para uma mesma prioridade, evidência de experiência ou projeto sempre vence skill, resumo ou highlight quando declarar a
      ação ou tecnologia necessária. Nunca selecione uma skill isolada se o catálogo contiver uma atividade profissional ou de
      projeto que comprove o mesmo ponto com mais contexto.
    - Priorize primeiro evidências de trabalho ou projeto para as atividades centrais; depois requisitos técnicos explícitos;
      por fim diferenciais relevantes. Quando houver correspondências reais nas três categorias, represente as três.
    - Busque variedade sem sacrificar cobertura. Evite pares que produziriam exatamente o mesmo argumento, mas mantenha pares
      distintos quando eles revelarem atuação, tecnologias, práticas ou diferenciais diferentes.
    - Se uma prioridade reunir várias atividades ou tecnologias, você pode usar mais de um par para ela quando cada evidência
      comprovar uma parte diferente e relevante. Para prioridades agrupadas, procure até três evidências complementares antes
      de seguir. Não atribua ao candidato as partes que nenhuma evidência sustenta.
    - Ignore ferramentas e habilidades do perfil que não respondam à vaga. Não preencha a quantidade máxima à força.

    A seleção é inteiramente semântica e deve funcionar para qualquer currículo e qualquer vaga. Retorne somente o JSON do
    schema, sem explicação fora dele.
    """
    return [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "objetivo": f"Selecionar aderências factuais da categoria {category} para orientar um único e-mail.",
                    "categoria_em_foco": category,
                    "focus_vacancy_ids": focus_ids,
                    "prioridades_da_vaga": vacancy_catalog,
                    "evidencias_do_candidato": evidence_catalog,
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "user",
            "content": (
                "Faça a comparação completa e devolva um objeto JSON com matches. Cubra toda prioridade comprovável, incluindo "
                "trabalho principal, requisitos e diferenciais. Para cada par, confirme antes que não existe uma experiência "
                "ou projeto mais forte que a skill escolhida. Em prioridades compostas, verifique cada parte independente antes "
                "de seguir. Não repita argumento nem invente equivalências."
            ),
        },
    ]


def _build_messages(
    candidate_data: dict,
    job: JobPosting,
    *,
    revision_directives: tuple[str, ...] = (),
    attempt_number: int = 1,
    alignment_brief: AIEmailBrief | None = None,
) -> list[dict[str, str]]:
    grammatical_gender = _string(candidate_data.get("grammatical_gender"))
    system_content = f"""
    Você é um redator sênior de e-mails de candidatura em português do Brasil. Escreva um texto específico, humano e seguro,
    cuja força venha da escolha de evidências concretas. Sua saída possui somente "subject" e "body".

    FONTE E RELEVÂNCIA
    - A vaga define o que importa. O brief de alinhamento define quais fatos do candidato têm relação comprovada com ela.
      Quando houver brief, use somente candidate_evidence e source_context para afirmações profissionais sobre o candidato.
    - O objeto vaga é a fonte factual para cargo, empresa, atividades e requisitos. Mencionar o cargo ou a empresa anunciada não
      é uma afirmação sobre o histórico do candidato e não exige candidate_evidence.
    - vacancy_priority explica por que a evidência é relevante, mas não prova que o candidato realizou a atividade da vaga.
      Nunca transforme uma tarefa futura, requisito ou tecnologia presente apenas na vaga em experiência passada.
    - Não combine duas fontes para criar um detalhe novo. "Procuro feedback" não autoriza acrescentar quem forneceu o feedback;
      mentoria ou desenvolvedores mais experientes presentes apenas na vaga continuam sendo contexto futuro.
    - Quando as fontes registrarem atuação profissional anterior, não diga "iniciar minha carreira" ou "primeiro emprego".
      Expresse continuidade, crescimento ou aprofundamento da carreira já iniciada.
    - Preserve o sentido factual de cada evidência. Não acrescente senioridade, domínio, duração, frequência, método, contexto,
      resultado, impacto ou responsabilidade que a fonte não declare.
    - Evidência com source_kind=skill permite afirmar conhecimento naquela habilidade, e nada além disso. Evidências com
      source_kind=experience_activity ou project_activity permitem descrever somente as ações e o escopo registrados.
      Nunca agrupe uma habilidade isolada em frases como "experiência prática em X, Y e Z", "atuei com X" ou "domino X".
    - Requisitos com barra, vírgula, "ou" ou "e/ou" contêm alternativas independentes. Evidência de PHP autoriza mencionar PHP,
      mas nunca Laravel; evidência de Node.js autoriza Node.js, mas não as outras alternativas da mesma frase.
    - Manifestar interesse, vontade ou intenção presente de aprender e crescer é linguagem legítima de candidatura, não uma
      alegação de experiência passada. Já afirmar facilidade, rapidez ou histórico de aprendizado exige um atributo declarado em
      atributos_profissionais_declarados ou outra evidência explícita.
    - Escolha de três a cinco argumentos fortes e variados do brief. Dê prioridade ao trabalho central da função e aos requisitos
      técnicos. Diferenciais são opcionais: só use um quando ele melhorar claramente o argumento. Não faça inventário do currículo.
    - Não transforme descrição institucional, segmento, tipo de produto ou adjetivo promocional da empresa em motivo principal
      da candidatura apenas porque aparece na vaga. Só destaque esse contexto quando houver evidência direta do candidato ligada
      a ele. Sem essa correspondência, fundamente o interesse nas atividades, requisitos e condições de aprendizado explicitamente
      anunciadas que possuam relação concreta com o perfil.

    UMA ÚNICA COMPOSIÇÃO
    - Escreva o conteúdo completo de body de uma vez, como uma única string. Ele deve começar exatamente com "Olá," e conter,
      depois da saudação, três parágrafos curtos separados por uma linha em branco. Não gere os parágrafos em campos separados.
    - O intervalo aceito é de {EMAIL_BODY_MIN_WORDS} a {EMAIL_BODY_MAX_WORDS} palavras depois da saudação. Mire entre
      {EMAIL_BODY_TARGET_MIN_WORDS} e {EMAIL_BODY_TARGET_MAX_WORDS} palavras para não ficar próximo dos limites.
      Planeje abertura, prova e convite antes de redigir para que uma ideia conduza à seguinte.
    - Primeiro parágrafo: manifeste interesse direto pela vaga e pela empresa e conecte uma atividade central, requisito ou
      condição concreta de desenvolvimento profissional ao momento do candidato. Não antecipe uma lista de tecnologias nem use
      segmento, tipo de produto ou linguagem promocional da empresa como eixo da abertura sem evidência direta correspondente.
    - Segundo parágrafo: desenvolva um argumento integrado com três a cinco aderências fortes e variadas, ligando entregas ou
      conhecimentos reais ao trabalho anunciado. Agrupe fatos relacionados com naturalidade, sem parecer uma lista.
    - Terceiro parágrafo: faça, em uma única frase, um convite natural para conversa ou entrevista. Um convite simples é válido;
      não tente torná-lo específico repetindo tecnologias, projetos, qualificações ou promessas de contribuição.
    - Cada tecnologia, atividade, evidência e conclusão deve aparecer uma única vez no e-mail. Não resuma o parágrafo anterior
      com frases como "essas atividades me prepararam" e não repita no convite como o candidato contribuirá.

    VOZ, IDENTIDADE E GÊNERO
    - Prefira verbos diretos em primeira pessoa, como "Tenho interesse" e "Atuei", a rótulos sobre si mesmo, como "sou
      interessado" ou "sou candidato". O título da vaga nomeia a oportunidade; não o use como forma artificial de se chamar.
    - Use genero_gramatical_candidato em toda flexão referente ao candidato. Remova marcações inclusivas do anúncio e escolha a
      forma correspondente. Nunca escreva alternativas como "interessado(a)", "desenvolvedor(a)" ou "candidato/a".
    - Não use nome de pessoa, placeholder, contato, despedida ou assinatura; a aplicação adiciona a assinatura automaticamente.
    - Evite autopromoção vazia e clichês como "perfil ideal", "alinhamento perfeito", "sólida experiência", "agregar valor",
      "ansioso" ou "me preparou". Não prometa entrevista, contratação ou resultado.

    ASSUNTO
    - subject deve conter somente o cargo da vaga em cargo_para_email, com a flexão adequada ao candidato. Não inclua empresa,
      nome, slogan nem o prefixo "Candidatura -", que será aplicado pela aplicação.

    Se correcoes_obrigatorias não estiver vazio, produza uma composição totalmente nova a partir das fontes. Não tente reconstruir
    nem imaginar o rascunho rejeitado. Cada correção é uma restrição, não uma nova fonte: ignore qualquer orientação que contradiga
    vaga, brief, source_context, ano_atual ou atributos declarados. Retorne somente JSON válido.
    """
    payload = {
        "objetivo": "Escrever o e-mail completo a partir dos melhores alinhamentos reais.",
        "tentativa": attempt_number,
        "cargo_para_email": _job_title_for_email(job, grammatical_gender),
        "genero_gramatical_candidato": grammatical_gender,
        "ano_atual": date.today().year,
        "vaga": _job_data_for_email(job, grammatical_gender=grammatical_gender),
        "brief_de_alinhamento": alignment_brief.to_dict() if alignment_brief else None,
        "atributos_profissionais_declarados": candidate_data.get("soft_skills") or [],
        "correcoes_obrigatorias": list(revision_directives),
    }
    if alignment_brief is None:
        payload["perfil_profissional"] = candidate_data

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        {
            "role": "user",
            "content": (
                "Antes de responder, selecione silenciosamente os argumentos, defina a progressão entre os três parágrafos e "
                "elimine sobreposição entre abertura, prova e convite. Escreva body inteiro em uma única string, aplique o "
                f"gênero informado, mire entre {EMAIL_BODY_TARGET_MIN_WORDS} e {EMAIL_BODY_TARGET_MAX_WORDS} palavras e retorne "
                "somente subject e body."
            ),
        },
    ]


def _build_review_messages(
    candidate_data: dict,
    job: JobPosting,
    email: AIEmailContent,
    alignment_brief: AIEmailBrief | None = None,
) -> list[dict[str, str]]:
    grammatical_gender = _string(candidate_data.get("grammatical_gender"))
    system_content = f"""
    Você revisa e-mails de candidatura em português do Brasil. Avalie o texto como uma composição completa e não o reescreva.
    A vaga define relevância; o brief seleciona os argumentos mais relevantes; perfil_profissional_completo é a fonte factual de
    conferência sobre o candidato. Uma paráfrase fiel é válida. Só classifique como invenção uma afirmação profissional sobre o
    candidato que não exista nem no brief nem no perfil completo.

    BLOQUEADORES E NOTA
    - Reprove somente um problema que impeça o envio: invenção ou exagero factual, baixa aderência material à vaga, argumento
      irrelevante, clichê concreto, repetição que prejudique a leitura, erro de identidade ou erro real de linguagem.
    - Sugestões opcionais como citar Docker, TypeScript, inglês, outro projeto ou uma evidência adicional não são bloqueadores.
      Se o e-mail já possui seleção suficiente, o controle deve passar e a sugestão deve ser omitida.
    - Score 9 significa pronto para envio com, no máximo, polimento opcional. Score 10 significa pronto e especialmente forte.
      Score de 0 a 8 exige ao menos um controle reprovado com trecho/problema concreto e correção obrigatória.
    - Em cada controle, details descreve o problema concreto. correction informa apenas a ação necessária para corrigi-lo.
      Quando passed=true, correction deve ser vazio. Não escreva recomendações opcionais em correction.

    REGRAS DE INTERPRETAÇÃO DAS FONTES
    - O objeto vaga é fonte válida para cargo, empresa, atividades e requisitos. Mencionar a empresa ou manifestar interesse na
      vaga não exige evidência no perfil e nunca é invenção factual.
    - candidate_evidence e source_context são fontes literais. Empresa, projeto, cargo e período presentes nessas fontes ou no
      perfil podem ser usados. Não descarte um fato explícito por achar que ele parece improvável.
    - Se o perfil registra atuação anterior, "iniciar minha carreira" é incompatível com as fontes. Se o texto atribuir feedback,
      acompanhamento ou mentoria a uma pessoa ou grupo não identificado na evidência, factual_fidelity deve reprovar.
    - Para cada uso de "experiência", "experiência prática", "atuei", "utilizei" ou "domino", confira individualmente todas as
      tecnologias ligadas à expressão. source_kind=skill permite somente "conhecimento em"; se uma habilidade isolada for
      apresentada como experiência ou domínio, factual_fidelity deve reprovar e mandar limitar a frase a conhecimento.
    - Use ano_atual para datas: uma data de início explícita menor ou igual ao ano atual não é futura. Ser júnior ou iniciante não
      significa não possuir experiência anterior e não invalida "desde 2025" quando isso estiver nas fontes.
    - Requisitos separados por barra, vírgula, "ou" ou "e/ou" são alternativas. PHP no perfil comprova PHP, nunca Laravel. Não
      atribua ao candidato todas as alternativas listadas na vaga.
    - "Tenho interesse", "quero aprender", "tenho vontade de aprender" e equivalentes expressam intenção presente ou futura;
      não alegam experiência passada e são válidos em uma candidatura. Afirmações de facilidade ou rapidez para aprender são
      atributos e precisam existir no perfil.
    - Buscar um ambiente colaborativo ou querer crescer nele também é intenção válida. Isso não autoriza afirmar que uma empresa
      anterior oferecia esse ambiente quando a fonte não o declara.
    - Classifique clichês e exageros subjetivos em persuasive_quality, não como invenção factual. Antes de reprovar fidelidade,
      localize a afirmação exata nas duas fontes do candidato e só então conclua que ela está ausente.
    - Use o perfil completo somente para conferir afirmações já presentes no e-mail. Nunca proponha em correction uma tecnologia,
      atividade, empresa ou projeto novo; a correção deve remover, limitar ou reformular o material já selecionado no brief.

    Preencha os {len(EMAIL_REVIEW_CHECKS)} controles do schema:
    - factual_fidelity: toda afirmação profissional está sustentada pelo brief ou pelo perfil completo, sem elevar seu sentido;
      source_kind=skill comprova apenas conhecimento. Fato verdadeiro presente somente no perfil não é invenção; avalie em
      content_selection se ele é irrelevante para a vaga.
    - vacancy_alignment: o texto relaciona de três a cinco evidências às prioridades concretas da vaga, não apresenta tarefas
      futuras como experiência passada e não inclui detalhes alheios. Diferenciais são opcionais. Três argumentos relevantes são
      suficientes; nunca reprove para pedir uma evidência adicional quando a seleção existente já sustenta a candidatura.
      Reprove quando a abertura escolhe como argumento principal um segmento, tipo de produto ou descrição promocional sem
      correspondência direta no perfil, apesar de existirem atividades ou requisitos centrais com evidências mais fortes.
    Formato, gênero gramatical, expressões proibidas, identidade, quantidade de parágrafos e contagem de palavras já foram
    validados objetivamente antes desta chamada. Não os reavalie, não crie controles adicionais e não faça revisão estilística.

    Um convite convencional como "Gostaria de conversar sobre a oportunidade." é válido no terceiro parágrafo e não deve ser
    reprovado por ser genérico. Não peça tecnologias, projetos ou qualificações no encerramento.

    Não exija que o e-mail mencione todas as correspondências. Exija seleção suficiente para representar a aderência real sem
    virar lista. Não reprove um fato existente apenas porque foi parafraseado. Quando reprovar, cite em issues o trecho concreto
    e explique em feedback como corrigi-lo usando as fontes. É proibido sugerir code review, pair programming, testes ou qualquer
    outra vivência apenas porque ela aparece na vaga; ela precisa existir no brief ou perfil. Não peça novas evidências no terceiro
    parágrafo, que é reservado ao convite final.

    approved só pode ser true quando todos os controles passarem, issues estiver vazio e score for de
    {EMAIL_REVIEW_MIN_SCORE} a 10. Qualquer controle reprovado exige approved=false, score no máximo 8, ao menos uma issue e
    correction não vazio no controle correspondente. Não reduza a nota por aperfeiçoamentos opcionais.
    Retorne somente o JSON do schema, com textos em português do Brasil.
    """
    payload = {
        "objetivo": "Auditar fidelidade, aderência, persuasão e coesão do e-mail.",
        "cargo_para_email": _job_title_for_email(job, grammatical_gender),
        "genero_gramatical_candidato": grammatical_gender,
        "ano_atual": date.today().year,
        "vaga": _job_data_for_email(job, grammatical_gender=grammatical_gender),
        "brief_de_alinhamento": alignment_brief.to_dict() if alignment_brief else None,
        "perfil_profissional_completo": candidate_data,
        "email_gerado": {"subject": email.subject, "body": email.body},
        "metricas_formato": _email_body_metrics(email.body),
    }

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        {
            "role": "user",
            "content": (
                "Leia o corpo em sequência, confronte cada afirmação primeiro com o brief e depois com o perfil completo, e "
                "audite separadamente cada tecnologia ligada a experiência, prática, atuação ou domínio. Respeite as métricas "
                "calculadas. Depois preencha todos os controles, sem expor "
                "raciocínio e sem sugerir informações ausentes das fontes."
            ),
        },
    ]


def _brief_schema(
    *,
    vacancy_ids: tuple[str, ...],
    evidence_ids: tuple[str, ...],
    max_items: int = EMAIL_ALIGNMENT_MAX_MATCHES,
    allow_empty: bool = False,
) -> dict:
    return {
        "type": "object",
        "properties": {
            "matches": {
                "type": "array",
                "minItems": 0 if allow_empty else 1,
                "maxItems": max_items,
                "items": {
                    "type": "object",
                    "properties": {
                        "vacancy_id": {"type": "string", "enum": list(vacancy_ids)},
                        "evidence_id": {"type": "string", "enum": list(evidence_ids)},
                    },
                    "required": ["vacancy_id", "evidence_id"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["matches"],
        "additionalProperties": False,
    }


def _brief_validation_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "direct_match": {"type": "boolean"},
            "reason": {"type": "string", "maxLength": 300},
        },
        "required": ["direct_match", "reason"],
        "additionalProperties": False,
    }


def _review_schema() -> dict:
    check_schema = {
        "type": "object",
        "properties": {
            "passed": {"type": "boolean"},
            "details": {"type": "string", "maxLength": 300},
            "correction": {"type": "string", "maxLength": 300},
        },
        "required": ["passed", "details", "correction"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "checks": {
                "type": "object",
                "properties": {
                    name: {**check_schema, "description": label}
                    for name, label in EMAIL_REVIEW_CHECKS
                },
                "required": [name for name, _ in EMAIL_REVIEW_CHECKS],
                "additionalProperties": False,
            },
            "approved": {"type": "boolean"},
            "score": {"type": "integer", "minimum": 0, "maximum": 10},
            "issues": {
                "type": "array",
                "maxItems": 6,
                "items": {"type": "string", "maxLength": 300},
            },
            "feedback": {"type": "string", "maxLength": 800},
        },
        "required": ["checks", "approved", "score", "issues", "feedback"],
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
    return None


def _log_brief_output(content: str, category: str) -> None:
    return None


def _log_brief_validation_output(content: str, vacancy_priority: str) -> None:
    return None


def _log_review_output(content: str) -> None:
    return None


def _email_body_metrics(body: str) -> dict[str, int | bool]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", body.strip()) if block.strip()]
    starts_with_exact_greeting = bool(blocks and blocks[0] == "Olá,")
    content_blocks = blocks[1:] if starts_with_exact_greeting else blocks
    words = re.findall(r"\b[\wÀ-ÿ]+(?:[-'][\wÀ-ÿ]+)*\b", " ".join(content_blocks), flags=re.UNICODE)
    return {
        "starts_with_exact_greeting": starts_with_exact_greeting,
        "paragraphs_after_greeting": len(content_blocks),
        "word_count_after_greeting": len(words),
    }


def _string(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _parse_brief_output(output_text: str) -> dict:
    try:
        return parse_strict_json_object(output_text)
    except json.JSONDecodeError as object_error:
        stripped = output_text.strip()
        try:
            generated = json.loads(stripped)
        except json.JSONDecodeError:
            recovered_matches = _recover_brief_matches_from_text(stripped)
            if recovered_matches:
                return {"matches": recovered_matches}
            raise object_error
        if isinstance(generated, list):
            return {"matches": generated}
        raise object_error


def _recover_brief_matches_from_text(output_text: str) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    for object_text in re.findall(r"\{[^{}]*\}", output_text, flags=re.DOTALL):
        vacancy_match = re.search(r'"vacancy_id"\s*:\s*"([^"]+)"', object_text)
        evidence_match = re.search(r'"evidence_id"\s*:\s*"([^"]+)"', object_text)
        if vacancy_match and evidence_match:
            matches.append(
                {
                    "vacancy_id": vacancy_match.group(1),
                    "evidence_id": evidence_match.group(1),
                }
            )
    return matches


def _brief_from_dict(
    data: dict,
    *,
    vacancy_by_id: dict[str, dict[str, str]],
    evidence_by_id: dict[str, dict[str, str]],
    max_items: int = EMAIL_ALIGNMENT_MAX_MATCHES,
    allow_empty: bool = False,
) -> AIEmailBrief:
    raw_matches = data.get("matches")
    if not isinstance(raw_matches, list) or (not raw_matches and not allow_empty):
        raise AIEmailGenerationError("A IA não retornou aderências factuais para orientar o e-mail.")
    matches: list[AIEmailBriefMatch] = []
    seen: set[tuple[str, str]] = set()
    for item in raw_matches:
        if not isinstance(item, dict):
            raise AIEmailGenerationError("A IA retornou uma aderência inválida para o e-mail.")
        vacancy_id = _string(item.get("vacancy_id"))
        evidence_id = _string(item.get("evidence_id"))
        vacancy = vacancy_by_id.get(vacancy_id)
        evidence = evidence_by_id.get(evidence_id)
        if vacancy is None or evidence is None:
            raise AIEmailGenerationError("A IA retornou uma referência inexistente no mapa de aderência.")
        key = (vacancy_id, evidence_id)
        if key in seen:
            continue
        seen.add(key)
        matches.append(
            AIEmailBriefMatch(
                category=vacancy["category"],
                vacancy_priority=vacancy["text"],
                candidate_evidence=evidence["text"],
                source_field=evidence["source_field"],
                source_context=evidence.get("source_context", ""),
                source_kind=evidence.get("source_kind", ""),
            )
        )
    if not matches:
        if allow_empty:
            return AIEmailBrief(matches=())
        raise AIEmailGenerationError("A IA não retornou aderências únicas para orientar o e-mail.")
    return AIEmailBrief(matches=tuple(matches))


def _unique_brief_matches(matches: list[AIEmailBriefMatch]) -> list[AIEmailBriefMatch]:
    unique: list[AIEmailBriefMatch] = []
    seen: set[tuple[str, str, str]] = set()
    for match in matches:
        key = (
            match.category.casefold(),
            match.vacancy_priority.casefold(),
            match.candidate_evidence.casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(match)
    return unique


def _review_from_dict(data: dict, *, allow_safe_rejection_defaults: bool = False) -> AIEmailReview:
    feedback = data.get("feedback")
    if not isinstance(feedback, str):
        feedback = _review_feedback_from_issues(data.get("issues"))
    checks = _review_checks_from_dict(
        data.get("checks") or _legacy_review_checks_from_dict(data),
        fallback_correction=feedback,
        raw_issues=data.get("issues"),
    )
    approved = data.get("approved")
    score = data.get("score")
    issues = tuple(
        f"{check.name}: {check.details}"
        for check in checks
        if not check.passed
    )
    feedback = "\n".join(
        check.correction
        for check in checks
        if not check.passed and check.correction
    )
    checks_rejected = any(not check.passed for check in checks)
    if approved is None:
        approved = not checks_rejected
    elif not isinstance(approved, bool):
        raise AIEmailGenerationError("A revisão da IA retornou 'approved' inválido.")
    if score is None:
        failed_count = sum(not check.passed for check in checks)
        score = EMAIL_REVIEW_MIN_SCORE if not failed_count else max(0, EMAIL_REVIEW_MIN_SCORE - failed_count)
    elif isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 10:
        raise AIEmailGenerationError("A revisão da IA retornou 'score' fora do intervalo de 0 a 10.")
    if checks_rejected and score >= EMAIL_REVIEW_MIN_SCORE:
        raise AIEmailGenerationError("A revisão reprovou controles, mas retornou score 9 ou 10.")
    if not checks_rejected and score < EMAIL_REVIEW_MIN_SCORE:
        raise AIEmailGenerationError("A revisão retornou score abaixo de 9 sem indicar controle reprovado.")
    expected_approval = not checks_rejected and score >= EMAIL_REVIEW_MIN_SCORE and not issues
    if approved is not expected_approval:
        raise AIEmailGenerationError("A revisão retornou aprovação incompatível com score, controles ou issues.")
    return AIEmailReview(
        approved=approved,
        score=score,
        issues=issues,
        feedback=feedback,
        checks=checks,
    )


def _objective_email_review(email: AIEmailContent, job: JobPosting) -> AIEmailReview | None:
    violations = _objective_email_violations(email, job)
    if not violations:
        return None
    grouped: dict[str, tuple[list[str], list[str]]] = {}
    for name, details, correction in violations:
        detail_parts, correction_parts = grouped.setdefault(name, ([], []))
        detail_parts.append(details)
        correction_parts.append(correction)
    checks = tuple(
        AIEmailReviewCheck(
            name=name,
            passed=False,
            details=" ".join(detail_parts),
            correction=" ".join(dict.fromkeys(correction_parts)),
        )
        for name, (detail_parts, correction_parts) in grouped.items()
    )
    return AIEmailReview(
        approved=False,
        score=EMAIL_REVIEW_MIN_SCORE - 1,
        issues=tuple(f"{check.name}: {check.details}" for check in checks),
        feedback="\n".join(check.correction for check in checks),
        checks=checks,
        source="local",
    )


def _objective_email_violations(
    email: AIEmailContent,
    job: JobPosting,
) -> tuple[tuple[str, str, str], ...]:
    violations: list[tuple[str, str, str]] = []
    metrics = _email_body_metrics(email.body)
    if not metrics["starts_with_exact_greeting"]:
        violations.append(
            (
                "language_and_format",
                "O corpo não começa com a saudação exata 'Olá,'.",
                "Comece body exatamente com 'Olá,'.",
            )
        )
    paragraph_count = int(metrics["paragraphs_after_greeting"])
    if paragraph_count != 3:
        violations.append(
            (
                "language_and_format",
                f"O corpo possui {paragraph_count} parágrafo(s) depois da saudação; são exigidos 3.",
                "Escreva exatamente três parágrafos depois da saudação: abertura, prova e convite.",
            )
        )
    blocks = [block.strip() for block in re.split(r"\n\s*\n", email.body.strip()) if block.strip()]
    content_blocks = blocks[1:] if blocks and blocks[0] == "Olá," else blocks
    if len(content_blocks) == 3:
        final_sentences = re.findall(r"[^.!?]+[.!?]+(?:[\"')\]]+)?", content_blocks[-1])
        if len(final_sentences) != 1:
            violations.append(
                (
                    "language_and_format",
                    f"O convite final possui {len(final_sentences)} frase(s); é exigida exatamente uma.",
                    "Escreva o terceiro parágrafo como uma única frase de convite para conversa ou entrevista.",
                )
            )
    word_count = int(metrics["word_count_after_greeting"])
    if not EMAIL_BODY_MIN_WORDS <= word_count <= EMAIL_BODY_MAX_WORDS:
        violations.append(
            (
                "language_and_format",
                f"O corpo possui {word_count} palavras depois da saudação; o intervalo aceito é "
                f"{EMAIL_BODY_MIN_WORDS}-{EMAIL_BODY_MAX_WORDS}.",
                f"Produza uma nova composição com {EMAIL_BODY_TARGET_MIN_WORDS}-{EMAIL_BODY_TARGET_MAX_WORDS} palavras "
                "depois da saudação.",
            )
        )

    found = [
        label
        for pattern, label in EMAIL_DISALLOWED_EXPRESSION_PATTERNS
        if re.search(pattern, email.body, flags=re.IGNORECASE)
    ]
    if found:
        expressions = ", ".join(f"'{item}'" for item in found)
        violations.append(
            (
                "persuasive_quality",
                f"O corpo usa expressão genérica proibida: {expressions}.",
                "Substitua as expressões proibidas por formulações concretas sustentadas pelo brief.",
            )
        )
    gender_markers = [
        label
        for pattern, label in EMAIL_DISALLOWED_GENDER_MARKERS
        if re.search(pattern, f"{email.subject}\n{email.body}", flags=re.IGNORECASE)
    ]
    if gender_markers:
        markers = ", ".join(dict.fromkeys(gender_markers))
        violations.append(
            (
                "identity_and_gender",
                f"O e-mail usa {markers}.",
                "Use somente a flexão correspondente ao gênero gramatical informado, sem parênteses ou barras.",
            )
        )
    return tuple(violations)


def _apply_objective_review_checks(
    review: AIEmailReview,
    email: AIEmailContent,
    job: JobPosting,
) -> AIEmailReview:
    objective_review = _objective_email_review(email, job)
    if objective_review is None:
        return review

    objective_by_name = {check.name: check for check in objective_review.checks}
    checks = tuple(objective_by_name.get(check.name, check) for check in review.checks)
    known_names = {check.name for check in checks}
    checks = (*checks, *(check for check in objective_review.checks if check.name not in known_names))
    issues = tuple(dict.fromkeys((*review.issues, *objective_review.issues)))
    feedback = "\n".join(
        dict.fromkeys(part for part in (review.feedback, objective_review.feedback) if part)
    )
    return AIEmailReview(
        approved=False,
        score=min(review.score, EMAIL_REVIEW_MIN_SCORE - 1),
        issues=issues,
        feedback=feedback,
        checks=checks,
        source="local+ai",
    )


def _review_checks_from_dict(
    value,
    *,
    fallback_correction: str = "",
    raw_issues=None,
) -> tuple[AIEmailReviewCheck, ...]:
    if not isinstance(value, dict):
        raise AIEmailGenerationError("A revisão da IA não retornou os controles obrigatórios.")
    checks: list[AIEmailReviewCheck] = []
    for name, _ in EMAIL_REVIEW_CHECKS:
        raw_check = value.get(name)
        if isinstance(raw_check, bool):
            passed = raw_check
            details = _legacy_review_details(raw_issues, name)
            if not details:
                details = "Critério atendido." if passed else f"O controle '{name}' foi reprovado."
            correction = "" if passed else fallback_correction or details
        elif isinstance(raw_check, dict):
            passed = raw_check.get("passed")
            details = _string(
                raw_check.get("details")
                or raw_check.get("detail")
                or raw_check.get("reason")
                or raw_check.get("explanation")
            )
            correction = raw_check.get("correction")
            if not isinstance(correction, str):
                correction = _string(
                    raw_check.get("feedback")
                    or raw_check.get("correction_guidance")
                    or raw_check.get("recommendation")
                )
        else:
            raise AIEmailGenerationError(
                f"A revisão da IA retornou o controle '{name}' inválido: {raw_check!r}; "
                f"chaves disponíveis: {sorted(value)}."
            )
        if not isinstance(passed, bool):
            raise AIEmailGenerationError(
                f"A revisão da IA retornou o controle '{name}' inválido: {raw_check!r}."
            )
        if not details:
            details = "Critério atendido." if passed else f"O controle '{name}' foi reprovado."
        if not isinstance(correction, str) or (not passed and not correction.strip()):
            correction = "" if passed else fallback_correction or details
        correction = correction.strip()
        if passed and correction:
            raise AIEmailGenerationError(
                f"A revisão retornou correção para o controle aprovado '{name}'."
            )
        if not passed and not correction:
            raise AIEmailGenerationError(
                f"A revisão reprovou o controle '{name}' sem informar correção."
            )
        checks.append(
            AIEmailReviewCheck(
                name=name,
                passed=passed,
                details=details.strip(),
                correction=correction,
            )
        )
    return tuple(checks)


def _legacy_review_checks_from_dict(data: dict) -> dict:
    checks: dict[str, dict[str, object]] = {}
    raw_issues = data.get("issues")
    for name, label in EMAIL_REVIEW_CHECKS:
        raw_check = data.get(name)
        if isinstance(raw_check, dict):
            checks[name] = raw_check
            continue
        passed = raw_check
        if not isinstance(passed, bool):
            continue
        details = _legacy_review_details(raw_issues, name)
        if not details:
            details = "Critério atendido." if passed else f"{label} reprovado."
        checks[name] = {"passed": passed, "details": details, "correction": ""}
    return checks


def _legacy_review_details(raw_issues, check_name: str) -> str:
    if not isinstance(raw_issues, list):
        return ""
    details: list[str] = []
    for item in raw_issues:
        if isinstance(item, dict) and _review_issue_control(item) == check_name:
            issue_text = _review_issue_text(item)
            if isinstance(issue_text, str) and issue_text.strip():
                details.append(issue_text.strip())
        elif isinstance(item, str) and check_name in item:
            details.append(item.strip())
    return " ".join(details)


def _review_issue_strings(raw_issues) -> list[str]:
    if not isinstance(raw_issues, list):
        raise AIEmailGenerationError("A revisão da IA retornou 'issues' inválido.")
    issues: list[str] = []
    for item in raw_issues:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            control = _review_issue_control(item)
            issue_text = _review_issue_text(item)
            text = f"{control}: {issue_text}".strip(": ")
        else:
            raise AIEmailGenerationError("A revisão da IA retornou 'issues' inválido.")
        if text:
            issues.append(text)
    return issues


def _review_feedback_from_issues(raw_issues) -> str:
    if not isinstance(raw_issues, list):
        return ""
    feedback: list[str] = []
    for item in raw_issues:
        if isinstance(item, dict):
            text = _string(
                item.get("feedback")
                or item.get("feedback_correction")
                or item.get("correction")
                or item.get("correction_guidance")
            )
            if text:
                feedback.append(text)
    return "\n".join(feedback)


def _review_issue_control(item: dict) -> str:
    return _string(item.get("control") or item.get("issue_type"))


def _review_issue_text(item: dict) -> str:
    return _string(item.get("issue_text") or item.get("description") or item.get("explanation"))


def _review_feedback_for_regeneration(review: AIEmailReview) -> tuple[str, ...]:
    corrections = tuple(
        dict.fromkeys(
            check.correction.strip()
            for check in review.checks
            if not check.passed and check.correction.strip()
        )
    )
    return corrections or ("Produza uma nova composição corrigindo os controles reprovados.",)


def _candidate_data_for_email(candidate: CandidateProfile) -> dict:
    data = candidate.to_dict()
    for key in ("name", "email", "phone", "website", "github", "linkedin", "whatsapp"):
        data.pop(key, None)
    return data


def _candidate_evidence_catalog(candidate_data: dict) -> list[dict[str, str]]:
    catalog: list[dict[str, str]] = []

    def add(
        source_field: str,
        value,
        source_context: str = "",
        source_kind: str = "",
    ) -> None:
        evidence_text = _string(value)
        if not evidence_text:
            return
        catalog.append(
            {
                "id": f"e{len(catalog) + 1:03d}",
                "source_field": source_field,
                "text": evidence_text,
                "source_context": source_context,
                "source_kind": source_kind,
            }
        )

    add("title", candidate_data.get("title"), source_kind="professional_title")
    add("summary", candidate_data.get("summary"), source_kind="professional_summary")
    add("location", candidate_data.get("location"), source_kind="location")
    for index, highlight in enumerate(candidate_data.get("highlights") or []):
        add(f"highlights[{index}]", highlight, source_kind="experience_highlight")

    for experience_index, experience in enumerate(candidate_data.get("experiences") or []):
        if not isinstance(experience, dict):
            continue
        context = " | ".join(
            part
            for part in (
                _string(experience.get("company")),
                _string(experience.get("role")),
                _string(experience.get("project")),
                (
                    f"início declarado: {_string(experience.get('started_at'))}"
                    if _string(experience.get("started_at"))
                    else ""
                ),
                (
                    f"fim declarado: {_string(experience.get('ended_at'))}"
                    if _string(experience.get("ended_at"))
                    else ""
                ),
            )
            if part
        )
        for activity_index, activity in enumerate(experience.get("activities") or []):
            add(
                f"experiences[{experience_index}].activities[{activity_index}]",
                activity,
                context,
                "experience_activity",
            )
        for skill_index, skill in enumerate(experience.get("skills") or []):
            add(
                f"experiences[{experience_index}].skills[{skill_index}]",
                skill,
                context,
                "experience_skill",
            )

    for project_index, project in enumerate(candidate_data.get("projects") or []):
        if not isinstance(project, dict):
            continue
        context = _string(project.get("name"))
        for detail_index, detail in enumerate(project.get("details") or []):
            add(
                f"projects[{project_index}].details[{detail_index}]",
                detail,
                context,
                "project_activity",
            )
        for skill_index, skill in enumerate(project.get("skills") or []):
            add(
                f"projects[{project_index}].skills[{skill_index}]",
                skill,
                context,
                "project_skill",
            )

    for language_index, language in enumerate(candidate_data.get("languages") or []):
        if not isinstance(language, dict):
            continue
        value = " - ".join(
            part
            for part in (
                _string(language.get("name")),
                _string(language.get("proficiency")),
                _string(language.get("notes")),
            )
            if part
        )
        add(f"languages[{language_index}]", value, source_kind="language")

    for education_index, education in enumerate(candidate_data.get("education") or []):
        if not isinstance(education, dict):
            continue
        value = " - ".join(
            part
            for part in (
                _string(education.get("name")),
                _string(education.get("institution")),
                _string(education.get("status")),
                _string(education.get("started_at")),
                _string(education.get("ended_at")),
                _string(education.get("notes")),
            )
            if part
        )
        add(f"education[{education_index}]", value, source_kind="education")

    for index, soft_skill in enumerate(candidate_data.get("soft_skills") or []):
        add(f"soft_skills[{index}]", soft_skill, source_kind="soft_skill")
    for index, skill in enumerate(candidate_data.get("skills") or []):
        add(f"skills[{index}]", skill, source_kind="skill")
    return catalog


def _job_priority_catalog(job: JobPosting) -> list[dict[str, str]]:
    catalog: list[dict[str, str]] = []

    def add(category: str, value) -> None:
        text = _string(value)
        if not text:
            return
        key = (category.casefold(), text.casefold())
        if any((item["category"].casefold(), item["text"].casefold()) == key for item in catalog):
            return
        catalog.append(
            {
                "id": f"v{len(catalog) + 1:03d}",
                "category": category,
                "text": text,
            }
        )

    for priority in _description_priorities(job.description):
        add("atividade", priority)
    for requirement in job.requirements:
        add("requisito", requirement)
    for item in job.nice_to_have:
        add("diferencial", item)
    if not catalog:
        add("contexto", job.title)
    if not catalog and job.raw_text.strip():
        recovered_job = JobPosting.from_text(job.raw_text)
        for priority in _description_priorities(recovered_job.description):
            add("atividade", priority)
        for requirement in recovered_job.requirements:
            add("requisito", requirement)
        for item in recovered_job.nice_to_have:
            add("diferencial", item)
        add("contexto", recovered_job.title)
    if not catalog:
        add("contexto", job.raw_text)
    return catalog


def _description_priorities(description: str) -> list[str]:
    if not description.strip():
        return []
    priorities: list[str] = []
    for raw_line in description.splitlines():
        line = raw_line.strip()
        if not line or re.fullmatch(r"\*{0,2}[^*]+\*{0,2}:?", line) and line.startswith("**"):
            continue
        line = re.sub(r"^[-*•]\s*", "", line).strip()
        if line:
            priorities.append(line)
    return list(dict.fromkeys(priorities)) or [description.strip()]


def _job_data_for_email(job: JobPosting, *, grammatical_gender: str = "") -> dict:
    return {
        "title": _job_title_for_email(job, grammatical_gender),
        "company": job.company,
        "location": job.location,
        "work_model": job.work_model,
        "description": job.description,
        "requirements": job.requirements,
        "nice_to_have": job.nice_to_have,
    }


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


def _job_title_for_email(job: JobPosting, grammatical_gender: str) -> str:
    title = _job_title_without_company(job)
    gender = grammatical_gender.strip().casefold()
    if gender == "masculino":
        return re.sub(r"\([ao]\)", "", title).strip()
    if gender == "feminino":
        title = re.sub(r"or\(a\)", "ora", title, flags=re.IGNORECASE)
        title = re.sub(r"o\(a\)", "a", title, flags=re.IGNORECASE)
        return re.sub(r"\(a\)", "a", title, flags=re.IGNORECASE).strip()
    return title
