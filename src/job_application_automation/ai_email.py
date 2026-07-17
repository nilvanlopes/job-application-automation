from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date

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
EMAIL_REVIEW_MAX_ATTEMPTS = 5
EMAIL_ALIGNMENT_MAX_MATCHES = 24
EMAIL_ALIGNMENT_MAX_MATCHES_PER_STAGE = 8
EMAIL_OLLAMA_CONTEXT_LENGTH = DEFAULT_OLLAMA_CONTEXT_LENGTH
# Keeps the default 14B writer fully GPU-resident on a 10 GiB card.
EMAIL_WRITER_OLLAMA_CONTEXT_LENGTH = 6144
EMAIL_WRITER_MAX_OUTPUT_TOKENS = 768
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
)
EMAIL_REVIEW_CHECKS = (
    ("factual_fidelity", "Fidelidade factual"),
    ("vacancy_alignment", "Aderência à vaga"),
    ("content_selection", "Seleção de conteúdo"),
    ("persuasive_quality", "Qualidade persuasiva"),
    ("cohesion_and_non_repetition", "Coesão e ausência de repetição"),
    ("identity_and_gender", "Identidade e gênero gramatical"),
    ("language_and_format", "Linguagem e formato"),
)


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


@dataclass(frozen=True, slots=True)
class AIEmailReview:
    approved: bool
    score: int
    issues: tuple[str, ...]
    feedback: str
    checks: tuple[AIEmailReviewCheck, ...] = ()

    @property
    def passed(self) -> bool:
        checks_passed = not self.checks or all(check.passed for check in self.checks)
        return self.approved and self.score >= EMAIL_REVIEW_MIN_SCORE and not self.issues and checks_passed


@dataclass(frozen=True, slots=True)
class AIEmailReviewAttempt:
    number: int
    email: AIEmailContent
    review: AIEmailReview


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
) -> AIEmailBrief:
    candidate_data = _candidate_data_for_email(candidate)
    evidence_catalog = _candidate_evidence_catalog(candidate_data)
    vacancy_catalog = _job_priority_catalog(job)
    if not evidence_catalog:
        raise AIEmailGenerationError("O perfil do candidato não contém evidências profissionais para o e-mail.")
    if not vacancy_catalog:
        raise AIEmailGenerationError("A vaga não contém prioridades que possam orientar o e-mail.")

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
            response_payload = chat_completion(
                _build_brief_messages(
                    evidence_catalog,
                    vacancy_catalog,
                    category=category,
                    focus_ids=focus_ids,
                    max_items=max_items,
                ),
                base_url=base_url or DEFAULT_OLLAMA_BASE_URL,
                model=resolved_model,
                response_format=_brief_schema(
                    vacancy_ids=focus_ids,
                    evidence_ids=tuple(item["id"] for item in evidence_catalog),
                    max_items=max_items,
                    allow_empty=True,
                ),
                context_length=EMAIL_OLLAMA_CONTEXT_LENGTH,
                request_timeout=request_timeout,
                **kwargs,
            )
        except OllamaError as exc:
            raise AIEmailGenerationError(str(exc)) from exc

        output_text = _extract_output_text(response_payload)
        _log_brief_output(output_text, category)
        try:
            generated = _parse_brief_output(output_text)
        except json.JSONDecodeError as exc:
            raise AIEmailGenerationError(
                "A resposta da IA não contém JSON válido para o mapa de aderência "
                f"na categoria '{category}'. Resposta bruta: {output_text.strip()}"
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
        response_payload = chat_completion(
            messages,
            base_url=base_url,
            model=model,
            response_format=_brief_validation_schema(),
            context_length=EMAIL_OLLAMA_CONTEXT_LENGTH,
            request_timeout=request_timeout,
            **kwargs,
        )
    except OllamaError as exc:
        raise AIEmailGenerationError(str(exc)) from exc

    output_text = _extract_output_text(response_payload)
    _log_brief_validation_output(output_text, match.vacancy_priority)
    try:
        generated = parse_strict_json_object(output_text)
    except json.JSONDecodeError as exc:
        raise AIEmailGenerationError(
            "A resposta da IA não contém JSON válido para validar uma aderência. "
            f"Resposta bruta: {output_text.strip()}"
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
    alignment_brief: AIEmailBrief | None = None,
    base_url: str | None = None,
    model: str | None = None,
    request_timeout: float = 120.0,
    opener=None,
) -> AIEmailContent:
    candidate_data = _candidate_data_for_email(candidate)
    resolved_model = (model or DEFAULT_OLLAMA_EMAIL_MODEL).strip()
    kwargs = {"opener": opener} if opener is not None else {}
    base_messages = _build_messages(
        candidate_data,
        job,
        review_feedback=review_feedback,
        previous_draft=previous_draft,
        alignment_brief=alignment_brief,
    )
    messages = base_messages
    last_error = ""
    last_output = ""

    for _ in range(EMAIL_WRITER_FORMAT_ATTEMPTS):
        try:
            response_payload = chat_completion(
                messages,
                base_url=base_url or DEFAULT_OLLAMA_BASE_URL,
                model=resolved_model,
                response_format="json",
                context_length=EMAIL_WRITER_OLLAMA_CONTEXT_LENGTH,
                max_output_tokens=EMAIL_WRITER_MAX_OUTPUT_TOKENS,
                request_timeout=request_timeout,
                **kwargs,
            )
        except OllamaError as exc:
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
        f"{EMAIL_WRITER_FORMAT_ATTEMPTS} tentativas. Último erro: {last_error}. "
        f"Resposta bruta: {last_output.strip()}"
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
            response_payload = chat_completion(
                messages,
                base_url=base_url or DEFAULT_OLLAMA_BASE_URL,
                model=resolved_model,
                response_format=_review_schema(),
                context_length=EMAIL_OLLAMA_CONTEXT_LENGTH,
                request_timeout=request_timeout,
                **kwargs,
            )
        except OllamaError as exc:
            raise AIEmailGenerationError(str(exc)) from exc

        last_output = _extract_output_text(response_payload)
        _log_review_output(last_output)
        try:
            generated = parse_strict_json_object(last_output)
            last_generated = generated
            return _apply_objective_review_checks(_review_from_dict(generated), email)
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
            return _apply_objective_review_checks(review, email)
        except AIEmailGenerationError:
            pass

    raise AIEmailGenerationError(
        "A IA não respeitou o contrato JSON da revisão após "
        f"{EMAIL_REVIEW_FORMAT_ATTEMPTS} tentativas. Último erro: {last_error}. "
        f"Resposta bruta: {last_output.strip()}"
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
) -> ReviewedAIEmailContent:
    brief = alignment_brief or generate_ai_email_brief(
        candidate,
        job,
        base_url=base_url,
        model=model,
        request_timeout=request_timeout,
        opener=opener,
    )
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
            alignment_brief=brief,
            base_url=base_url,
            model=email_model,
            request_timeout=request_timeout,
            opener=opener,
        )
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
        )
        attempt = AIEmailReviewAttempt(number=number, email=email, review=review)
        attempts.append(attempt)
        if review.passed:
            return ReviewedAIEmailContent(
                email=email,
                attempts=tuple(attempts),
                alignment_brief=brief,
            )
        feedback = _review_feedback_for_regeneration(review)
        previous_draft = email

    raise AIEmailReviewError(
        "A IA não gerou um e-mail aprovado pela revisão automática "
        f"após {len(attempts)} tentativa(s). Último feedback: {feedback}",
        tuple(attempts),
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
    review_feedback: str = "",
    previous_draft: AIEmailContent | None = None,
    alignment_brief: AIEmailBrief | None = None,
) -> list[dict[str, str]]:
    system_content = """
    Você é um redator sênior de e-mails de candidatura em português do Brasil. Escreva um texto específico, humano e seguro,
    cuja força venha da escolha de evidências concretas. Sua saída possui somente "subject" e "body".

    FONTE E RELEVÂNCIA
    - A vaga define o que importa. O brief de alinhamento define quais fatos do candidato têm relação comprovada com ela.
      Quando houver brief, use somente candidate_evidence e source_context para afirmações profissionais sobre o candidato.
    - O objeto vaga é a fonte factual para cargo, empresa, atividades e requisitos. Mencionar o cargo ou a empresa anunciada não
      é uma afirmação sobre o histórico do candidato e não exige candidate_evidence.
    - vacancy_priority explica por que a evidência é relevante, mas não prova que o candidato realizou a atividade da vaga.
      Nunca transforme uma tarefa futura, requisito ou tecnologia presente apenas na vaga em experiência passada.
    - Preserve o sentido factual de cada evidência. Não acrescente senioridade, domínio, duração, frequência, método, contexto,
      resultado, impacto ou responsabilidade que a fonte não declare.
    - Evidência com source_kind=skill permite afirmar conhecimento naquela habilidade, e nada além disso. Evidências com
      source_kind=experience_activity ou project_activity permitem descrever somente as ações e o escopo registrados.
    - Requisitos com barra, vírgula, "ou" ou "e/ou" contêm alternativas independentes. Evidência de PHP autoriza mencionar PHP,
      mas nunca Laravel; evidência de Node.js autoriza Node.js, mas não as outras alternativas da mesma frase.
    - Manifestar interesse, vontade ou intenção presente de aprender e crescer é linguagem legítima de candidatura, não uma
      alegação de experiência passada. Já afirmar facilidade, rapidez ou histórico de aprendizado exige um atributo declarado em
      atributos_profissionais_declarados ou outra evidência explícita.
    - Escolha os argumentos mais fortes do brief, com diversidade. Dê prioridade ao trabalho central da função e aos requisitos
      técnicos; inclua um diferencial quando ele trouxer informação convincente. Não faça inventário do currículo.

    UMA ÚNICA COMPOSIÇÃO
    - Escreva o conteúdo completo de body de uma vez, como uma única string. Ele deve começar exatamente com "Olá," e conter,
      depois da saudação, três parágrafos curtos separados por uma linha em branco. Não gere os parágrafos em campos separados.
    - Produza de 110 a 170 palavras. Planeje abertura, prova e convite antes de redigir para que uma ideia conduza à seguinte.
    - Primeiro parágrafo: manifeste interesse direto pela vaga e pela empresa e conecte a proposta concreta da oportunidade ao
      momento profissional do candidato. Não antecipe uma lista de tecnologias.
    - Segundo parágrafo: desenvolva um argumento integrado com quatro a seis aderências fortes e variadas, ligando entregas ou
      conhecimentos reais ao trabalho anunciado. Agrupe fatos relacionados com naturalidade, sem parecer uma lista.
    - Terceiro parágrafo: faça, em uma única frase, um convite natural para conversa ou entrevista. Não recapitule habilidades.
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

    Se houver feedback e rascunho anterior, reescreva o e-mail inteiro como uma nova composição. O feedback é uma recomendação do
    revisor, não uma nova fonte: ignore qualquer orientação que contradiga vaga, brief, source_context, ano_atual ou atributos
    declarados. Preserve argumentos factuais úteis e corrija os problemas reais sem criar fatos. Retorne somente JSON válido.
    """
    payload = {
        "objetivo": "Escrever o e-mail completo a partir dos melhores alinhamentos reais.",
        "cargo_para_email": _job_title_without_company(job),
        "genero_gramatical_candidato": candidate_data.get("grammatical_gender", ""),
        "ano_atual": date.today().year,
        "vaga": _job_data_for_email(job),
        "brief_de_alinhamento": alignment_brief.to_dict() if alignment_brief else None,
        "atributos_profissionais_declarados": candidate_data.get("soft_skills") or [],
        "feedback_da_revisao": review_feedback,
        "rascunho_anterior": (
            {"subject": previous_draft.subject, "body": previous_draft.body}
            if previous_draft
            else None
        ),
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
                "gênero informado e retorne somente subject e body."
            ),
        },
    ]


def _build_review_messages(
    candidate_data: dict,
    job: JobPosting,
    email: AIEmailContent,
    alignment_brief: AIEmailBrief | None = None,
) -> list[dict[str, str]]:
    system_content = f"""
    Você revisa e-mails de candidatura em português do Brasil. Avalie o texto como uma composição completa e não o reescreva.
    A vaga define relevância; o brief seleciona os argumentos mais relevantes; perfil_profissional_completo é a fonte factual de
    conferência sobre o candidato. Uma paráfrase fiel é válida. Só classifique como invenção uma afirmação profissional sobre o
    candidato que não exista nem no brief nem no perfil completo.

    REGRAS DE INTERPRETAÇÃO DAS FONTES
    - O objeto vaga é fonte válida para cargo, empresa, atividades e requisitos. Mencionar a empresa ou manifestar interesse na
      vaga não exige evidência no perfil e nunca é invenção factual.
    - candidate_evidence e source_context são fontes literais. Empresa, projeto, cargo e período presentes nessas fontes ou no
      perfil podem ser usados. Não descarte um fato explícito por achar que ele parece improvável.
    - Use ano_atual para datas: uma data de início explícita menor ou igual ao ano atual não é futura. Ser júnior ou iniciante não
      significa não possuir experiência anterior e não invalida "desde 2025" quando isso estiver nas fontes.
    - Requisitos separados por barra, vírgula, "ou" ou "e/ou" são alternativas. PHP no perfil comprova PHP, nunca Laravel. Não
      atribua ao candidato todas as alternativas listadas na vaga.
    - "Tenho interesse", "quero aprender", "tenho vontade de aprender" e equivalentes expressam intenção presente ou futura;
      não alegam experiência passada e são válidos em uma candidatura. Afirmações de facilidade ou rapidez para aprender são
      atributos e precisam existir no perfil.
    - Classifique clichês e exageros subjetivos em persuasive_quality, não como invenção factual. Antes de reprovar fidelidade,
      localize a afirmação exata nas duas fontes do candidato e só então conclua que ela está ausente.

    Preencha os {len(EMAIL_REVIEW_CHECKS)} controles do schema:
    - factual_fidelity: toda afirmação profissional está sustentada por candidate_evidence e source_context, sem elevar seu
      sentido; source_kind=skill comprova apenas conhecimento. Se alguma afirmação não tiver fonte no brief, este controle deve
      reprovar e o feedback deve mandar removê-la, nunca procurar uma justificativa indireta.
    - vacancy_alignment: o texto relaciona evidências às prioridades concretas da vaga e não apresenta tarefas futuras como
      experiência passada.
    - content_selection: o e-mail aproveita os argumentos mais fortes e variados disponíveis, cobre o trabalho central e
      requisitos relevantes e usa um diferencial quando houver um forte no brief; não inclui detalhes alheios à vaga. Avalie
      somente prioridades que tenham correspondência no brief. Omitir uma prioridade sem evidência é correto e nunca deve gerar
      pedido para o candidato alegar essa experiência.
    - persuasive_quality: os fatos tornam a candidatura convincente, sem adjetivos vazios, promessas ou frases genéricas que
      poderiam ser enviadas a qualquer empresa. Reprove variações de "alinhamento perfeito", "perfil ideal", "sólida
      experiência", "agregar valor", "ansioso", "ávido" e "me preparou"; peça uma formulação concreta baseada nas fontes.
    - cohesion_and_non_repetition: abertura, prova e convite formam uma progressão natural, e nenhuma evidência, tecnologia,
      atividade ou conclusão é repetida literal ou semanticamente entre parágrafos.
    - identity_and_gender: não há nome, placeholder, contato, despedida ou assinatura manual; toda referência ao candidato usa
      genero_gramatical_candidato e não há formas como "(a)" ou barras.
    - language_and_format: assunto e português estão corretos; body começa com "Olá,", possui três parágrafos depois da
      saudação, tem aproximadamente 110 a 170 palavras e termina com um convite de uma frase sem repetir qualificações.
      Para saudação, quantidade de parágrafos e palavras, use exclusivamente metricas_formato; não estime visualmente.

    Não exija que o e-mail mencione todas as correspondências. Exija seleção suficiente para representar a aderência real sem
    virar lista. Não reprove um fato existente apenas porque foi parafraseado. Quando reprovar, cite em issues o trecho concreto
    e explique em feedback como corrigi-lo usando as fontes. É proibido sugerir code review, pair programming, testes ou qualquer
    outra vivência apenas porque ela aparece na vaga; ela precisa existir no brief ou perfil. Não peça novas evidências no terceiro
    parágrafo, que é reservado ao convite final.

    approved só pode ser true quando todos os controles passarem, issues estiver vazio e score for de
    {EMAIL_REVIEW_MIN_SCORE} a 10. Qualquer controle reprovado exige approved=false, score no máximo 8 e ao menos uma issue.
    Retorne somente o JSON do schema, com textos em português do Brasil.
    """
    payload = {
        "objetivo": "Auditar fidelidade, aderência, persuasão e coesão do e-mail.",
        "cargo_para_email": _job_title_without_company(job),
        "genero_gramatical_candidato": candidate_data.get("grammatical_gender", ""),
        "ano_atual": date.today().year,
        "vaga": _job_data_for_email(job),
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
                "compare os parágrafos entre si. Respeite as métricas calculadas. Depois preencha todos os controles, sem expor "
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
        },
        "required": ["passed", "details"],
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
    if content.strip():
        print("[job-application] Resposta bruta da IA na geração do e-mail:", flush=True)
        print(content.strip(), flush=True)


def _log_brief_output(content: str, category: str) -> None:
    if content.strip():
        print(
            f"[job-application] Resposta bruta da IA no mapa de aderência do e-mail ({category}):",
            flush=True,
        )
        print(content.strip(), flush=True)


def _log_brief_validation_output(content: str, vacancy_priority: str) -> None:
    if content.strip():
        print(
            f"[job-application] Validação da aderência ({vacancy_priority}):",
            flush=True,
        )
        print(content.strip(), flush=True)


def _log_review_output(content: str) -> None:
    if content.strip():
        print("[job-application] Resposta bruta da IA na revisão do e-mail:", flush=True)
        print(content.strip(), flush=True)


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
    checks = _review_checks_from_dict(data.get("checks") or _legacy_review_checks_from_dict(data))
    approved = data.get("approved")
    score = data.get("score")
    issues = _review_issue_strings(data.get("issues"))
    feedback = data.get("feedback")
    if not isinstance(feedback, str):
        feedback = _review_feedback_from_issues(data.get("issues"))
    checks_rejected = any(not check.passed for check in checks)
    if not isinstance(approved, bool):
        if allow_safe_rejection_defaults and checks_rejected:
            approved = False
        else:
            raise AIEmailGenerationError("A revisão da IA retornou 'approved' inválido.")
    if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 10:
        if allow_safe_rejection_defaults and not approved:
            score = 0
        else:
            raise AIEmailGenerationError("A revisão da IA retornou 'score' fora do intervalo de 0 a 10.")
    if not isinstance(feedback, str):
        raise AIEmailGenerationError("A revisão da IA retornou 'feedback' inválido.")
    return AIEmailReview(
        approved=approved,
        score=score,
        issues=tuple(item.strip() for item in issues if item.strip()),
        feedback=feedback.strip(),
        checks=checks,
    )


def _apply_objective_review_checks(review: AIEmailReview, email: AIEmailContent) -> AIEmailReview:
    found = [
        label
        for pattern, label in EMAIL_DISALLOWED_EXPRESSION_PATTERNS
        if re.search(pattern, email.body, flags=re.IGNORECASE)
    ]
    if not found:
        return review

    expressions = ", ".join(f"'{item}'" for item in found)
    detail = (
        f"O corpo usa expressão genérica proibida: {expressions}. "
        "Substitua-a por uma formulação concreta sustentada pelo brief e pelo perfil."
    )
    checks = tuple(
        AIEmailReviewCheck(name=check.name, passed=False, details=detail)
        if check.name == "persuasive_quality"
        else check
        for check in review.checks
    )
    issue = f"persuasive_quality: {detail}"
    feedback = "\n".join(part for part in (review.feedback, detail) if part).strip()
    return AIEmailReview(
        approved=False,
        score=min(review.score, EMAIL_REVIEW_MIN_SCORE - 1),
        issues=(*review.issues, issue) if issue not in review.issues else review.issues,
        feedback=feedback,
        checks=checks,
    )


def _review_checks_from_dict(value) -> tuple[AIEmailReviewCheck, ...]:
    if not isinstance(value, dict):
        raise AIEmailGenerationError("A revisão da IA não retornou os controles obrigatórios.")
    checks: list[AIEmailReviewCheck] = []
    for name, _ in EMAIL_REVIEW_CHECKS:
        raw_check = value.get(name)
        if not isinstance(raw_check, dict):
            raise AIEmailGenerationError(f"A revisão da IA retornou o controle '{name}' inválido.")
        passed = raw_check.get("passed")
        details = raw_check.get("details")
        if not isinstance(passed, bool) or not isinstance(details, str):
            raise AIEmailGenerationError(f"A revisão da IA retornou o controle '{name}' inválido.")
        checks.append(AIEmailReviewCheck(name=name, passed=passed, details=details.strip()))
    return tuple(checks)


def _legacy_review_checks_from_dict(data: dict) -> dict:
    checks: dict[str, dict[str, object]] = {}
    raw_issues = data.get("issues")
    for name, label in EMAIL_REVIEW_CHECKS:
        passed = data.get(name)
        if not isinstance(passed, bool):
            continue
        details = _legacy_review_details(raw_issues, name)
        if not details:
            details = "Critério atendido." if passed else f"{label} reprovado."
        checks[name] = {"passed": passed, "details": details}
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


def _review_feedback_for_regeneration(review: AIEmailReview) -> str:
    pieces = list(review.issues)
    pieces.extend(
        f"{check.name}: {check.details}"
        for check in review.checks
        if not check.passed and check.details
    )
    if review.feedback:
        pieces.append(review.feedback)
    return "\n".join(f"- {piece}" for piece in pieces) or "Reescreva o e-mail com mais aderência e coesão."


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


def _job_data_for_email(job: JobPosting) -> dict:
    return {
        "title": job.title,
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
