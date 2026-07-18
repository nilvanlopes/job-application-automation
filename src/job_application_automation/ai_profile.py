from __future__ import annotations

import json
import re
from pathlib import Path

from .json_utils import parse_strict_json_object
from .models import (
    CandidateProfile,
    EducationEntry,
    ExperienceEntry,
    LanguageEntry,
    ProjectEntry,
)
from .ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_CONTEXT_LENGTH,
    DEFAULT_OLLAMA_MODEL,
    OllamaError,
    chat_completion,
)
from .paths import CANDIDATE_PROFILE_PATH
from .resume_reader import read_resume_text


class CandidateProfileGenerationError(RuntimeError):
    pass


PROFILE_OLLAMA_CONTEXT_LENGTH = DEFAULT_OLLAMA_CONTEXT_LENGTH

CORE_PROFILE_FIELDS = (
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
)
BACKGROUND_PROFILE_FIELDS = ("education", "languages", "soft_skills")
SKILLS_PROFILE_FIELDS = ("skills",)
EXPERIENCE_PROFILE_FIELDS = ("experiences", "highlights")
PROJECT_PROFILE_FIELDS = ("projects",)


def generate_candidate_profile(
    resume_path: Path,
    *,
    base_url: str | None = None,
    model: str | None = None,
    profile_path: Path = CANDIDATE_PROFILE_PATH,
    request_timeout: float = 180.0,
    opener=None,
) -> CandidateProfile:
    resume_text = read_resume_text(resume_path)
    grammatical_gender = _existing_grammatical_gender(profile_path)
    resolved_model = (model or DEFAULT_OLLAMA_MODEL).strip()
    kwargs = {}
    if opener is not None:
        kwargs["opener"] = opener
    def extract_part(
        stage: str,
        messages: list[dict[str, str]],
        fields: tuple[str, ...],
        response_schema: dict | None = None,
    ) -> dict:
        try:
            response_payload = chat_completion(
                messages,
                base_url=base_url or DEFAULT_OLLAMA_BASE_URL,
                model=resolved_model,
                response_format=response_schema or _schema_for(fields),
                context_length=PROFILE_OLLAMA_CONTEXT_LENGTH,
                request_timeout=request_timeout,
                **kwargs,
            )
        except OllamaError as exc:
            raise CandidateProfileGenerationError(str(exc)) from exc

        output_text = _extract_output_text(response_payload)
        _log_ai_output(output_text, stage)
        return _data_from_output(output_text, stage)

    profile_data: dict = {}
    profile_data.update(extract_part("dados centrais", _build_core_messages(resume_text), CORE_PROFILE_FIELDS))
    profile_data.update(
        extract_part("formação e idiomas", _build_background_messages(resume_text), BACKGROUND_PROFILE_FIELDS)
    )
    profile_data.update(
        extract_part(
            "experiências",
            _build_experience_messages(resume_text),
            EXPERIENCE_PROFILE_FIELDS,
        )
    )
    profile_data.update(
        extract_part(
            "projetos",
            _build_project_messages(resume_text),
            PROJECT_PROFILE_FIELDS,
            _project_schema(resume_text),
        )
    )
    skill_sources = (
        (
            "competências do resumo",
            _build_source_skills_messages(
                "resumo profissional",
                profile_data["summary"],
            ),
        ),
        (
            "competências declaradas",
            _build_declared_skills_messages(resume_text),
        ),
        (
            "competências das experiências",
            _build_source_skills_messages(
                "atividades das experiências",
                profile_data["experiences"],
            ),
        ),
        (
            "nomes técnicos das experiências",
            _build_named_skills_messages(
                "atividades das experiências",
                profile_data["experiences"],
            ),
        ),
        (
            "competências dos projetos",
            _build_source_skills_messages(
                "descrições dos projetos; ignore references para não inferir tecnologias",
                [
                    {"name": project["name"], "details": project["details"]}
                    for project in profile_data["projects"]
                ],
            ),
        ),
    )
    all_skills: list[str] = []
    for stage, messages in skill_sources:
        all_skills.extend(extract_part(stage, messages, SKILLS_PROFILE_FIELDS)["skills"])
    profile_data["skills"] = _unique_strings(all_skills)
    profile_data["grammatical_gender"] = grammatical_gender

    candidate = _candidate_from_json(profile_data)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        json.dumps(candidate.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return candidate


def _build_core_messages(resume_text: str) -> list[dict[str, str]]:
    system_content = """
    Extraia somente identificação, cargo, resumo, contatos e localização do currículo. O currículo é a única fonte.
    Não invente, complete, estime, corrija ou deduza valores. Use string vazia ou lista vazia quando não houver fonte explícita.

    - Copie nome, e-mail, telefone e URLs caractere por caractere.
    - "title" deve copiar o cargo da experiência profissional mais recente. Se houver cargo no currículo, não deixe vazio.
    - Se existir uma seção de resumo profissional, copie seu conteúdo fielmente em "summary" sem acrescentar qualificadores.
    - Em "location", extraia apenas cidade e estado explicitamente presentes, omitindo rua, número e bairro.

    Retorne somente o JSON exigido pelo schema.
    """
    return [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "objetivo": "Extrair dados centrais sem inferências.",
                    "curriculo_original": resume_text,
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "user",
            "content": (
                "Retorne os dados solicitados. Confira nome, contatos e URLs caractere por caractere e copie o cargo "
                "da experiência mais recente em title."
            ),
        },
    ]


def _build_background_messages(resume_text: str) -> list[dict[str, str]]:
    system_content = """
    Extraia somente formação, idiomas e soft skills do currículo. O currículo é a única fonte.
    Não invente, complete, estime nem deduza valores.

    FORMAÇÃO
    - Crie uma entrada para cada linha da seção de formação, na mesma ordem.
    - O primeiro ano de uma linha vai para "started_at". Um ano sozinho não prova conclusão nem data final.
    - Copie palavras de estado como "cursando", "em andamento", "interrompido" ou "concluído" para "status",
      preservando o texto da linha. Nunca coloque o status em "notes".
    - "status", "level" e "ended_at" só podem conter valores declarados literalmente naquela linha.
      Se a linha não declarar um desses valores, o campo correspondente deve ser "".
    - Exemplo genérico: "2022 - Curso X, Instituição Y" resulta em started_at "2022", status "", level "",
      ended_at "" e notes "".
    - Nunca converta ausência de status em conclusão, formação, diploma ou equivalente.

    IDIOMAS E SOFT SKILLS
    - Inclua todos os itens da seção de idiomas, inclusive idioma nativo, com nível e observações explícitas.
    - Copie cada item da seção de soft skills em um item separado, sem resumir e sem movê-lo para education.

    Retorne somente o JSON exigido pelo schema.
    """
    return [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "objetivo": "Extrair formação, todos os idiomas e todas as soft skills sem inferências.",
                    "curriculo_original": resume_text,
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "user",
            "content": (
                "Retorne somente education, languages e soft_skills. Antes de responder, confirme que cada status "
                "está no campo status, que linhas sem status explícito continuam vazias e que nenhum idioma foi omitido."
            ),
        },
    ]


def _build_declared_skills_messages(resume_text: str) -> list[dict[str, str]]:
    system_content = """
    Extraia todas as competências declaradas no resumo profissional, nas seções de habilidades técnicas e outras habilidades
    técnicas, e nos nomes de formações ou cursos. Não analise experiências e projetos nesta etapa.

    - Inclua somente competência explicitamente nomeada ou diretamente demonstrada por uma ação descrita.
    - Não deduza uma tecnologia a partir de outra.
    - Cada item deve conter exatamente uma competência curta. Nunca agrupe tecnologias, ferramentas, plataformas ou práticas
      distintas com vírgula, barra, ponto e vírgula ou conjunção; produza um item separado para cada uma.
    - Quando uma linha citar várias tecnologias, plataformas ou práticas, separe cada uma em seu próprio item.
    - Para tecnologias, ferramentas, frameworks, serviços e plataformas nomeados, copie somente o nome, sem prefixos como
      "Tecnologia", "Uso de" ou "Conhecimento em".
    - Remova duplicatas e unifique apenas variações inequívocas de grafia.
    - Não inclua soft skills, traços pessoais, contatos, formação ou nomes de empresa.
    - Não descarte ferramentas de desenvolvimento, design, infraestrutura, administração ou práticas por parecerem
      irrelevantes para uma vaga; o perfil será reutilizado.

    Faça uma segunda varredura silenciosa das seções declarativas antes de responder e confirme que cada termo técnico de
    cada linha aparece como um item próprio. Um item que ainda una duas competências com "e" deve ser dividido.
    Retorne somente o JSON com "skills".
    """
    return [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "objetivo": "Extrair integralmente as competências declaradas em itens atômicos.",
                    "curriculo_original": resume_text,
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "user",
            "content": (
                "Retorne somente skills. Confira linha por linha as seções declarativas e separe qualquer item que ainda "
                "contenha mais de uma competência."
            ),
        },
    ]


def _build_source_skills_messages(source_name: str, source_data) -> list[dict[str, str]]:
    system_content = """
    Extraia todas as competências técnicas e práticas profissionais presentes na fonte exclusiva recebida.
    Não use conhecimento externo nem acrescente fatos de outras partes do currículo.

    - Analise cada frase e item da fonte sem pular conteúdo.
    - Inclua tecnologias, linguagens, frameworks, bibliotecas, plataformas, ferramentas, integrações, métodos e práticas
      explicitamente nomeados ou diretamente demonstrados pelas ações.
    - Para cada tecnologia, ferramenta, framework, biblioteca, serviço ou plataforma nomeada, inclua um item separado
      contendo somente seu nome como escrito na fonte. Não use prefixos como "Tecnologia", "Uso de" ou "Conhecimento em".
    - Uma prática pode gerar outro item além do nome técnico, mas nunca substitua o nome técnico isolado por uma frase genérica.
    - Nunca acrescente alias, nome anterior, empresa relacionada ou explicação entre parênteses que não esteja na fonte.
    - Cada item deve conter exatamente uma competência curta. Separe toda enumeração em itens individuais.
    - Se uma ação mencionar duas plataformas, integrações ou práticas ligadas por "e", crie um item para cada uma.
    - Não copie uma frase inteira quando um nome curto e factual da competência preserva a evidência.
    - Não deduza tecnologias ausentes, não inclua soft skills e não descarte competências por relevância presumida.
    - Quando a fonte contiver references, não deduza competências a partir de nomes de repositório, domínio ou caminho.
    - O tipo de produto ou página não comprova a tecnologia usada; extraia uma tecnologia somente quando seu nome estiver escrito.
    - Preserve qualificadores técnicos nomeados. Não reduza uma prática executada com tecnologia explícita a uma prática genérica.
    - Remova apenas duplicatas inequívocas dentro desta saída.

    Antes de responder, percorra novamente toda a fonte e confirme que todos os termos técnicos e práticas explícitas foram
    representados. Retorne somente o JSON com "skills".
    """
    return [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "objetivo": "Extrair integralmente competências desta única fonte em itens atômicos.",
                    "nome_da_fonte": source_name,
                    "fonte_exclusiva": source_data,
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "user",
            "content": (
                "Retorne somente skills. Faça a cobertura completa da fonte exclusiva e divida qualquer item que una "
                "tecnologias, plataformas ou práticas distintas."
            ),
        },
    ]


def _build_named_skills_messages(source_name: str, source_data) -> list[dict[str, str]]:
    system_content = """
    Copie todos os nomes técnicos literais presentes na fonte exclusiva. Esta etapa não interpreta práticas; ela cria
    um inventário exato de linguagens, frameworks, bibliotecas, ferramentas, serviços, APIs, plataformas, padrões e métodos nomeados.

    - Cada item deve conter exatamente um nome técnico curto, preservando sua grafia na fonte.
    - Um nome técnico composto continua sendo um único item.
    - Examine todas as frases e copie também nomes que aparecem depois de palavras como "com", "utilizando", "via" ou "API".
    - Separe enumerações em itens individuais.
    - Não generalize, não traduza, não acrescente alias, não infira stack pelo tipo de produto e não crie nomes ausentes.
    - Ignore nomes de empresa, projeto, domínio, caminho e repository reference.

    Retorne somente o JSON com "skills".
    """
    return [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "objetivo": "Inventariar todos os nomes técnicos literais desta fonte.",
                    "nome_da_fonte": source_name,
                    "fonte_exclusiva": source_data,
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "user",
            "content": (
                "Retorne somente skills. Releia cada frase e confirme que todo nome técnico explícito foi copiado "
                "em seu próprio item, sem aliases ou explicações."
            ),
        },
    ]


def _build_experience_messages(resume_text: str) -> list[dict[str, str]]:
    system_content = """
    Extraia todas as experiências profissionais do currículo como evidências estruturadas.
    O currículo é a única fonte. Não invente, resuma em excesso nem deduplique entre empresas.

    EXPERIÊNCIAS
    - Crie uma entrada para cada experiência profissional, na mesma ordem do currículo.
    - Copie company, role, project e datas somente quando estiverem explícitos.
    - Um hífen que apenas separa o ano do nome da empresa não é uma data de término. Use "ended_at": "" quando não
      houver uma segunda data ou término explicitamente informado.
    - Em "activities", preserve uma entrada para cada bullet da experiência, na mesma ordem e com redação fiel.
    - Atividades iguais ou parecidas em empresas diferentes devem permanecer em ambas as experiências.

    HIGHLIGHTS
    - Selecione evidências concretas entre as atividades extraídas, preservando o sentido e sem criar impacto.
    - Inclua evidências de mais de uma experiência quando existirem fatos fortes em empresas diferentes.

    Antes de responder, conte silenciosamente os bullets de cada experiência e confira se as quantidades e a ordem foram
    preservadas. Retorne somente experiences e highlights.
    """
    return [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "objetivo": "Preservar integralmente as evidências das experiências.",
                    "curriculo_original": resume_text,
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "user",
            "content": (
                "Retorne somente experiences e highlights. Confirme que nenhuma atividade foi removida por ser parecida "
                "com outra atividade de uma empresa diferente."
            ),
        },
    ]


def _build_project_messages(resume_text: str) -> list[dict[str, str]]:
    system_content = """
    Extraia somente os itens explicitamente listados na seção de projetos do currículo. O currículo é a única fonte.

    - Crie exatamente uma entrada por projeto, na mesma ordem, sem misturar descrições.
    - Somente um item numerado ou de primeiro nível cria uma entrada em projects. Bullets indentados abaixo dele são details
      e references do mesmo projeto; nunca transforme esses subitens em projetos separados.
    - Em "details", crie um item para cada ação ou frase descritiva do projeto, sem incluir referências, parênteses de origem
      ou conteúdo entre crases.
    - Cada item de details deve ter no máximo 60 caracteres. Divida descrições longas em vários fatos curtos sem perder conteúdo.
    - Quando uma linha tiver o formato "ação: referência", details deve conter somente a ação antes dos dois-pontos;
      o conteúdo depois dos dois-pontos deve aparecer somente em references.
    - Em "references", copie caractere por caractere todos os textos entre crases presentes no título ou nos bullets do projeto.
    - Não transforme referências em URLs completas. Não adicione protocolo, domínio, caminho, barra, palavra ou letra.
    - Compare cada referência gerada com o texto original duas vezes antes de responder.
    - Não extraia categorias de habilidades, experiências ou cursos como projetos.

    Retorne somente o JSON com "projects".
    """
    return [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "objetivo": "Copiar todos os projetos e suas referências sem normalização.",
                    "curriculo_original": resume_text,
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "user",
            "content": (
                "Retorne somente projects. Confira a quantidade de itens e compare caractere por caractere cada reference "
                "com o currículo antes de responder."
            ),
        },
    ]


def _schema() -> dict:
    string_list = {"type": "array", "items": {"type": "string"}}
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "title": {
                "type": "string",
                "description": "Cargo atual ou mais recente explicitamente informado no currículo.",
            },
            "skills": {
                "type": "array",
                "items": {
                    "type": "string",
                    "maxLength": 80,
                    "pattern": "^[^,;()]+$",
                },
                "description": (
                    "Lista global, completa e sem duplicatas. Cada item contém exatamente uma competência "
                    "encontrada em qualquer seção do currículo; itens nunca agrupam competências distintas."
                ),
            },
            "education": {
                "type": "array",
                "description": "Todas as formações, cursos, bootcamps e certificações presentes no currículo.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "institution": {"type": "string"},
                        "status": {
                            "type": "string",
                            "description": "Status literal da linha ou string vazia; nunca inferido pelo ano.",
                        },
                        "level": {
                            "type": "string",
                            "description": "Nível literal da linha ou string vazia.",
                        },
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
            "summary": {
                "type": "string",
                "description": "Síntese factual da trajetória e atuação presentes no currículo inteiro.",
            },
            "email": {"type": "string"},
            "phone": {"type": "string"},
            "website": {"type": "string"},
            "github": {"type": "string"},
            "linkedin": {"type": "string"},
            "whatsapp": {"type": "string"},
            "highlights": {
                **string_list,
                "description": "Evidências profissionais concretas e contextualizadas extraídas de experiências e projetos.",
            },
            "experiences": {
                "type": "array",
                "description": "Uma entrada para cada experiência profissional, sem omissões.",
                "items": {
                    "type": "object",
                    "properties": {
                        "company": {"type": "string"},
                        "role": {"type": "string"},
                        "project": {"type": "string"},
                        "started_at": {"type": "string"},
                        "ended_at": {"type": "string"},
                        "activities": {
                            **string_list,
                            "description": "Uma entrada por atividade, entrega, responsabilidade ou resultado distinto.",
                        },
                    },
                    "required": [
                        "company",
                        "role",
                        "project",
                        "started_at",
                        "ended_at",
                        "activities",
                    ],
                    "additionalProperties": False,
                },
            },
            "projects": {
                "type": "array",
                "description": "Uma entrada para cada projeto apresentado no currículo, sem omissões.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "details": {
                            "type": "array",
                            "items": {"type": "string", "maxLength": 60},
                            "description": "Ações e descrições factuais, sem referências ou conteúdo entre crases.",
                        },
                        "references": {
                            **string_list,
                            "description": "Referências copiadas exatamente do bloco do projeto, sem normalização.",
                        },
                    },
                    "required": ["name", "details", "references"],
                    "additionalProperties": False,
                },
            },
            "languages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "proficiency": {"type": "string"},
                        "notes": {"type": "string"},
                    },
                    "required": ["name", "proficiency", "notes"],
                    "additionalProperties": False,
                },
            },
            "soft_skills": {
                **string_list,
                "description": "Uma habilidade comportamental explicitamente declarada por item.",
            },
            "location": {
                "type": "string",
                "description": "Somente cidade, estado ou localidade profissional explícita, sem endereço detalhado.",
            },
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
            "experiences",
            "projects",
            "languages",
            "soft_skills",
            "location",
        ],
        "additionalProperties": False,
    }


def _schema_for(fields: tuple[str, ...]) -> dict:
    schema = _schema()
    properties = schema["properties"]
    schema["properties"] = {field: properties[field] for field in fields}
    schema["required"] = list(fields)
    return schema


def _project_schema(resume_text: str) -> dict:
    schema = _schema_for(PROJECT_PROFILE_FIELDS)
    references = _unique_strings(re.findall(r"`([^`\n]+)`", resume_text))
    if references:
        project_properties = schema["properties"]["projects"]["items"]["properties"]
        project_properties["references"]["items"] = {
            "type": "string",
            "enum": references,
        }
    return schema


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


def _data_from_output(output_text: str, stage: str) -> dict:
    try:
        return parse_strict_json_object(output_text)
    except json.JSONDecodeError as exc:
        raise CandidateProfileGenerationError(
            f"A IA não retornou JSON válido na {stage} do perfil do candidato. "
            f"Resposta bruta: {output_text.strip()}"
        ) from exc


def _log_ai_output(content: str, stage: str) -> None:
    print(
        f"[job-application] Resposta bruta da IA no profile do candidato ({stage}):",
        flush=True,
    )
    print(content.strip(), flush=True)


def _candidate_from_json(data: dict) -> CandidateProfile:
    return CandidateProfile(
        name=_string(data.get("name")),
        title=_string(data.get("title")),
        grammatical_gender=_string(data.get("grammatical_gender")),
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
        experiences=[
            entry if isinstance(entry, ExperienceEntry) else ExperienceEntry(**entry)
            for entry in (data.get("experiences") or [])
        ],
        projects=[
            entry if isinstance(entry, ProjectEntry) else ProjectEntry(**entry)
            for entry in (data.get("projects") or [])
        ],
        languages=[
            entry if isinstance(entry, LanguageEntry) else LanguageEntry(**entry)
            for entry in (data.get("languages") or [])
        ],
        soft_skills=_strings(data.get("soft_skills")),
        location=_string(data.get("location")),
    )


def _existing_grammatical_gender(profile_path: Path) -> str:
    if not profile_path.exists():
        return ""
    try:
        existing_data = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(existing_data, dict):
        return ""
    return _string(existing_data.get("grammatical_gender"))


def _string(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _strings(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _unique_strings(values: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for item in _strings(values):
        key = item.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique
