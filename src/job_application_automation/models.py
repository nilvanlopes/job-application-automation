from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, List, Optional

from .paths import CANDIDATE_PROFILE_PATH


@dataclass(slots=True)
class EducationEntry:
    name: str
    institution: str = ""
    status: str = ""
    level: str = ""
    started_at: str = ""
    ended_at: str = ""
    notes: str = ""


@dataclass(slots=True)
class ExperienceEntry:
    company: str
    role: str = ""
    project: str = ""
    started_at: str = ""
    ended_at: str = ""
    activities: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)


EXPERIENCE_ENTRY_FIELDS = {"company", "role", "project", "started_at", "ended_at", "activities", "skills"}


def normalize_experience_entry_data(entry: dict[str, Any]) -> dict[str, Any]:
    data = dict(entry)
    dates = data.pop("dates", None)
    if dates and not data.get("started_at") and not data.get("ended_at"):
        if isinstance(dates, str):
            data["started_at"] = dates
        elif isinstance(dates, (list, tuple)):
            values = [str(item).strip() for item in dates if str(item).strip()]
            if values:
                data["started_at"] = values[0]
            if len(values) > 1:
                data["ended_at"] = values[1]
    if "activities" in data and not isinstance(data["activities"], list):
        data["activities"] = [str(data["activities"])] if str(data["activities"]).strip() else []
    if "skills" in data and not isinstance(data["skills"], list):
        data["skills"] = [str(data["skills"])] if str(data["skills"]).strip() else []
    return {key: value for key, value in data.items() if key in EXPERIENCE_ENTRY_FIELDS}


@dataclass(slots=True)
class ProjectEntry:
    name: str
    details: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)


@dataclass(slots=True)
class LanguageEntry:
    name: str
    proficiency: str = ""
    notes: str = ""


@dataclass(slots=True)
class CandidateProfile:
    name: str
    title: str
    grammatical_gender: str = ""
    skills: List[str] = field(default_factory=list)
    education: List[EducationEntry] = field(default_factory=list)
    summary: str = ""
    email: str = ""
    phone: str = ""
    website: str = ""
    github: str = ""
    linkedin: str = ""
    whatsapp: str = ""
    highlights: List[str] = field(default_factory=list)
    experiences: List[ExperienceEntry] = field(default_factory=list)
    projects: List[ProjectEntry] = field(default_factory=list)
    languages: List[LanguageEntry] = field(default_factory=list)
    soft_skills: List[str] = field(default_factory=list)
    location: str = ""

    @classmethod
    def default(cls) -> "CandidateProfile":
        if not CANDIDATE_PROFILE_PATH.exists():
            raise FileNotFoundError(f"Perfil do candidato não encontrado: {CANDIDATE_PROFILE_PATH}")
        return cls.from_file(CANDIDATE_PROFILE_PATH)

    @classmethod
    def from_file(cls, path: str | Path) -> "CandidateProfile":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data["education"] = [
            entry if isinstance(entry, EducationEntry) else EducationEntry(**entry)
            for entry in (data.get("education") or [])
        ]
        data["experiences"] = [
            entry if isinstance(entry, ExperienceEntry) else ExperienceEntry(**normalize_experience_entry_data(entry))
            for entry in (data.get("experiences") or [])
        ]
        projects: list[ProjectEntry] = []
        for entry in data.get("projects") or []:
            if isinstance(entry, ProjectEntry):
                projects.append(entry)
                continue
            project_data = dict(entry)
            if "details" not in project_data and "description" in project_data:
                description = project_data.pop("description")
                project_data["details"] = [description] if description else []
            if "references" not in project_data and "links" in project_data:
                project_data["references"] = project_data.pop("links")
            projects.append(ProjectEntry(**project_data))
        data["projects"] = projects
        data["languages"] = [
            entry if isinstance(entry, LanguageEntry) else LanguageEntry(**entry)
            for entry in (data.get("languages") or [])
        ]
        data["soft_skills"] = data.get("soft_skills") or []
        return cls(**data)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ApplicationInstruction:
    text: str
    kind: str = "custom"
    required: bool = True
    evidence_hint: str = ""


@dataclass(slots=True)
class JobPosting:
    raw_text: str
    title: str
    keywords: List[str] = field(default_factory=list)
    company: str = ""
    location: str = ""
    work_model: str = ""
    contact_email: str = ""
    contact_whatsapp: str = ""
    description: str = ""
    requirements: List[str] = field(default_factory=list)
    nice_to_have: List[str] = field(default_factory=list)
    benefits: List[str] = field(default_factory=list)
    requested_email_subject: str = ""
    application_instructions: List[ApplicationInstruction] = field(default_factory=list)

    @classmethod
    def from_text(cls, text: str) -> "JobPosting":
        raw_text = _sanitize_job_text(text)
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        title = _extract_title(lines)
        company = _extract_prefixed_value(raw_text, r"Empresa\s*:\s*(.+)")
        location = _extract_prefixed_value(raw_text, r"Local\s*:\s*(.+)")
        work_model = _extract_prefixed_value(
            raw_text,
            r"(?:Modelo de trabalho|Modelo)\s*:\s*(.+)",
        )
        contact_email = _extract_email(raw_text)
        contact_whatsapp = _extract_whatsapp(raw_text)
        requirements = _extract_section_items(raw_text, "REQUISITOS", ("DIFERENCIAIS", "BENEFÍCIOS", "BENEFICIOS"))
        nice_to_have = _extract_section_items(raw_text, "DIFERENCIAIS", ("BENEFÍCIOS", "BENEFICIOS"))
        benefits = _extract_section_items(raw_text, "BENEFÍCIOS", ("Enviar currículo", "Empresa:")) or _extract_section_items(raw_text, "BENEFICIOS", ("Enviar currículo", "Empresa:"))
        description = _extract_description(raw_text)
        keywords = _extract_keywords(raw_text)
        requested_email_subject = _extract_requested_email_subject(raw_text)
        application_instructions = _extract_application_instructions(raw_text)
        return cls(
            raw_text=raw_text,
            title=title,
            keywords=keywords,
            company=company,
            location=location,
            work_model=work_model,
            contact_email=contact_email,
            contact_whatsapp=contact_whatsapp,
            description=description,
            requirements=requirements,
            nice_to_have=nice_to_have,
            benefits=benefits,
            requested_email_subject=requested_email_subject,
            application_instructions=application_instructions,
        )

    def to_dict(self) -> dict:
        return asdict(self)


def _sanitize_job_text(text: str) -> str:
    """Remove screenshot/social-network UI noise before parsing a vacancy.

    Story/WhatsApp/Instagram screenshots often OCR the profile name and time
    before the actual poster text. Those tokens must never become the job title
    or email subject.
    """
    cleaned = text.strip()
    vacancy_match = re.search(r"\bVAGA\s+DE\s+EMPREGO\s*:", cleaned, flags=re.IGNORECASE)
    if vacancy_match:
        cleaned = cleaned[vacancy_match.start() :]
    else:
        vacancy_match = re.search(r"(?im)^\s*(?:[^\w\s]+)?\s*Vaga\s+[^\n\r]+", cleaned)
        if vacancy_match:
            cleaned = cleaned[vacancy_match.start() :]

    noise_patterns = [
        r"\bResponder\b.*$",
        r"\b(Instagram|Facebook|Stories?)\b.*$",
        r"^\s*Jo[aã]o\s+Marcelo\s+Socio\s*-?\s*Ontem\s+\d{1,2}[:.,]\d{2}\s*",
    ]
    for pattern in noise_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.MULTILINE)

    # OCR sometimes keeps bullet sections on one long line; normalize the most
    # important headings/bullets so section extraction is not fooled.
    cleaned = re.sub(r"\s+(DESCRI[ÇC][ÃA]O\s+DA\s+VAGA\s*:)", r"\n\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(REQUISITOS|DIFERENCIAIS|BENEF[ÍI1l]CIOS)\b", r"\n\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(Enviar\s+curr[íi]culo\s+para\s+)", r"\n\1", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("•", "\n- ")
    cleaned = re.sub(r"\bPHPinit\b", "PHPUnit", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bGitHUb\b", "GitHub", cleaned)
    cleaned = re.sub(r"\bBENEF[ÍI1l]ClOS\b", "BENEFÍCIOS", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:8{2,}\s*){2,}\b", "", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    # Restore newlines around headings and list markers after whitespace collapse.
    cleaned = re.sub(r"\s+(Local\s*:)", r"\n\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(Modelo\s*:)", r"\n\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(Modalidade\s*:)", r"\n\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(Modelo\s+de\s+trabalho\s*:)", r"\n\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(DESCRI[ÇC][ÃA]O\s+DA\s+VAGA\s*:)", r"\n\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(REQUISITOS|DIFERENCIAIS|BENEF[ÍI]CIOS)\b", r"\n\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(Enviar\s+curr[íi]culo\s+para\s+)", r"\n\1", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _extract_title(lines: list[str]) -> str:
    if not lines:
        return "Vaga sem título"
    first = re.sub(
        r"^vaga\s+(?:de\s+emprego\s*:\s*)?",
        "",
        lines[0],
        flags=re.IGNORECASE,
    ).strip()
    if (
        len(lines) > 1
        and not re.match(r"^(requisitos|diferenciais|benef[íi]cios|descri[çc][ãa]o)\b", lines[1], re.IGNORECASE)
        and re.search(r"php|laravel|python|react|vue|java|javascript|node", lines[1], re.IGNORECASE)
        and len(lines[1].split()) <= 4
    ):
        first = f"{first} {lines[1].strip()}"
    return _format_job_title(first)


def _format_job_title(title: str) -> str:
    title = " ".join(title.split())
    title = re.sub(r"(?<=[a-zá-ú])(?=[A-ZÁ-Ú])", " ", title)
    if title.isupper() or sum(1 for c in title if c.isupper()) > max(8, len(title) // 2):
        title = title.title()
    replacements = {
        "Php": "PHP",
        "Laravel": "Laravel",
        "Javascript": "JavaScript",
        "Vue.Js": "Vue.js",
        "Node.Js": "Node.js",
        " / ": " / ",
    }
    for old, new in replacements.items():
        title = title.replace(old, new)
    return title.strip() or "Vaga sem título"


def _extract_prefixed_value(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ""


def _extract_email(text: str) -> str:
    match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    if not match:
        return ""
    email = match.group(0)
    email = re.sub(r"(?:com|br|net|org)como$", lambda found: found.group(0)[:-4], email)
    local, separator, domain = email.partition("@")
    prefix_match = re.search(r"para([A-Za-z0-9._%+-]+)$", local, flags=re.IGNORECASE)
    if separator and prefix_match:
        email = f"{prefix_match.group(1)}@{domain}"
    return email


def _extract_whatsapp(text: str) -> str:
    match = re.search(r"Whatsapp\s+([0-9 .()\-+]+)", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _extract_requested_email_subject(text: str) -> str:
    match = re.search(
        r"assunto\s+[\"“”']([^\"“”']+)[\"“”']",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1).strip(" :.-") if match else ""


def _extract_application_instructions(text: str) -> list[ApplicationInstruction]:
    section = _extract_application_section(text)
    if not section:
        return []
    instructions: list[ApplicationInstruction] = []
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^(?:[-•]|\d+[.)])\s*", "", line).strip()
        if not line or is_resume_delivery_instruction(line) or re.search(r"com\s+o\s+assunto", line, flags=re.IGNORECASE):
            continue
        kind = _classify_application_instruction(line)
        instructions.append(
            ApplicationInstruction(
                text=line,
                kind=kind,
                required=True,
                evidence_hint=_instruction_evidence_hint(kind),
            )
        )
    return _dedupe_application_instructions(instructions)


def is_resume_delivery_instruction(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:interessad[oa]s?[,\s:;-]*)?"
            r"(?:envie(?:m)?|encaminhe(?:m)?|mande(?:m)?)\s+"
            r"(?:seu|o|um)?\s*curr[ií]culo\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def _extract_application_section(text: str) -> str:
    match = re.search(
        r"(?:Como\s+se\s+candidatar|Para\s+se\s+candidatar|Candidatura)\s*:?\s*(.+)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    section = match.group(1)
    stop_match = re.search(
        r"\n\s*(?:Candidaturas\s+sem|Observa[çc][aã]o|Importante)\b",
        section,
        flags=re.IGNORECASE,
    )
    if stop_match:
        section = section[: stop_match.start()]
    return section.strip()


def _classify_application_instruction(text: str) -> str:
    value = text.casefold()
    if "github" in value or "portf" in value:
        return "github_or_portfolio"
    if "linkedin" in value or "curr" in value:
        return "resume_or_linkedin"
    if "php" in value and ("legado" in value or "mant" in value):
        return "legacy_php_paragraph"
    if "disponibilidade" in value or "valor" in value or "hora" in value or "semanal" in value:
        return "availability_and_compensation"
    if "contrato" in value and ("ativo" in value or "tempo" in value or "ocup" in value):
        return "active_contracts"
    return "custom"


def _instruction_evidence_hint(kind: str) -> str:
    return {
        "github_or_portfolio": "github, website ou projetos do perfil",
        "resume_or_linkedin": "currículo anexado e linkedin do perfil",
        "legacy_php_paragraph": "experiências com PHP, manutenção e sistemas legados",
        "availability_and_compensation": "resposta explícita do candidato",
        "active_contracts": "resposta explícita do candidato",
    }.get(kind, "resposta explícita do candidato")


def _dedupe_application_instructions(
    instructions: list[ApplicationInstruction],
) -> list[ApplicationInstruction]:
    unique: list[ApplicationInstruction] = []
    seen: set[tuple[str, str]] = set()
    for instruction in instructions:
        key = (instruction.kind, instruction.text.casefold())
        if key in seen:
            continue
        seen.add(key)
        unique.append(instruction)
    return unique


def _extract_description(text: str) -> str:
    match = re.search(r"DESCRIÇÃO DA VAGA:\s*(.+?)(?:\n\s*REQUISITOS\b|$)", text, flags=re.IGNORECASE | re.DOTALL)
    return " ".join(match.group(1).split()) if match else ""


def _extract_section_items(text: str, heading: str, stop_headings: tuple[str, ...]) -> list[str]:
    stop_pattern = "|".join(re.escape(stop) for stop in stop_headings)
    pattern = rf"{re.escape(heading)}\s*(.+?)(?:\n\s*(?:{stop_pattern})\b|$)"
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return []
    body = match.group(1)
    items: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[-•]\s*", "", line).strip()
        if line:
            items.append(line)
    return items


@dataclass(slots=True)
class EmailVerificationResult:
    email: str
    normalized_email: str
    syntax_valid: bool
    mx_valid: Optional[bool]
    deliverable: Optional[bool]
    reasons: List[str] = field(default_factory=list)
    checker: str = "stdlib"


@dataclass(slots=True)
class EmailDraft:
    subject: str
    text: str
    html: str
    verification: Optional[EmailVerificationResult] = None


@dataclass(slots=True)
class ApplicationDraft:
    email_subject: str
    resume_markdown: str
    email_markdown: str
    email_html: str
    summary_markdown: str
    verification_markdown: str = ""
    job_extracted_markdown: str = ""
    match_report_markdown: str = ""
    job_structured: dict = field(default_factory=dict)


def _extract_keywords(text: str) -> List[str]:
    common = [
        "php",
        "laravel",
        "python",
        "javascript",
        "vue.js",
        "vue",
        "react",
        "django",
        "fastapi",
        "automation",
        "sql",
        "mysql",
        "postgresql",
        "api",
        "apis restful",
        "github",
        "git",
        "aws",
        "docker",
        "testing",
        "phpunit",
        "ci/cd",
        "scrum",
        "kanban",
    ]
    lower = text.lower()
    found: list[str] = []
    for keyword in common:
        if keyword in lower and keyword not in found:
            found.append(keyword)
    return found
