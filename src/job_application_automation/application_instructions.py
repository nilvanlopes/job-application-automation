from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .models import ApplicationInstruction, CandidateProfile, JobPosting


class ApplicationInstructionError(RuntimeError):
    def __init__(self, message: str, result: "ApplicationInstructionResult"):
        super().__init__(message)
        self.result = result


@dataclass(frozen=True, slots=True)
class FulfilledApplicationInstruction:
    instruction: ApplicationInstruction
    answer: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self.instruction)
        payload.update({"answer": self.answer, "source": self.source})
        return payload


@dataclass(frozen=True, slots=True)
class PendingApplicationInstruction:
    instruction: ApplicationInstruction
    reason: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self.instruction)
        payload["reason"] = self.reason
        return payload


@dataclass(frozen=True, slots=True)
class ApplicationInstructionResult:
    fulfilled: tuple[FulfilledApplicationInstruction, ...]
    pending: tuple[PendingApplicationInstruction, ...]

    @property
    def has_pending(self) -> bool:
        return bool(self.pending)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fulfilled": [item.to_dict() for item in self.fulfilled],
            "pending": [item.to_dict() for item in self.pending],
        }


def load_application_answers(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Arquivo de respostas da candidatura deve conter um objeto JSON.")
    custom = data.get("custom")
    if custom is not None and not isinstance(custom, dict):
        raise ValueError("Campo 'custom' do arquivo de respostas deve ser um objeto.")
    return data


def resolve_application_instructions(
    candidate: CandidateProfile,
    job: JobPosting,
    *,
    answers: dict[str, Any] | None = None,
) -> ApplicationInstructionResult:
    answers = answers or {}
    fulfilled: list[FulfilledApplicationInstruction] = []
    pending: list[PendingApplicationInstruction] = []
    for instruction in job.application_instructions:
        resolved = _resolve_instruction(candidate, instruction, answers)
        if resolved:
            answer, source = resolved
            fulfilled.append(
                FulfilledApplicationInstruction(
                    instruction=instruction,
                    answer=answer,
                    source=source,
                )
            )
        elif instruction.required:
            pending.append(
                PendingApplicationInstruction(
                    instruction=instruction,
                    reason=f"Resposta obrigatória ausente: {instruction.evidence_hint or instruction.text}",
                )
            )
    return ApplicationInstructionResult(tuple(fulfilled), tuple(pending))


def instructions_markdown(result: ApplicationInstructionResult) -> str:
    lines = ["# Instruções da candidatura", ""]
    if result.fulfilled:
        lines.extend(["## Cumpridas", ""])
        for item in result.fulfilled:
            lines.append(f"- {item.instruction.text}: {item.answer} ({item.source})")
        lines.append("")
    if result.pending:
        lines.extend(["## Pendentes", ""])
        for item in result.pending:
            lines.append(f"- {item.instruction.text}: {item.reason}")
        lines.append("")
    if not result.fulfilled and not result.pending:
        lines.append("- Nenhuma instrução explícita identificada.")
    return "\n".join(lines).rstrip() + "\n"


def instruction_block_text(result: ApplicationInstructionResult) -> str:
    if not result.fulfilled:
        return ""
    lines = ["Informações solicitadas para candidatura:"]
    lines.extend(f"- {item.answer}" for item in result.fulfilled)
    return "\n".join(lines)


def _resolve_instruction(
    candidate: CandidateProfile,
    instruction: ApplicationInstruction,
    answers: dict[str, Any],
) -> tuple[str, str] | None:
    direct = _custom_answer(instruction, answers)
    if direct:
        return direct, "application_answer_file"

    if instruction.kind == "resume_or_linkedin":
        if candidate.linkedin:
            return f"Currículo anexado em PDF; LinkedIn: {candidate.linkedin}", "profile"
        return "Currículo anexado em PDF.", "generated_artifact"

    if instruction.kind == "github_or_portfolio":
        links = [value for value in (candidate.github, candidate.website) if value]
        if links:
            return "GitHub/portfólio: " + " | ".join(links), "profile"
        return None

    if instruction.kind == "legacy_php_paragraph":
        answer = _legacy_php_answer(candidate)
        return (answer, "profile") if answer else None

    if instruction.kind == "availability_and_compensation":
        availability = _answer_value(answers, "availability")
        compensation = _answer_value(answers, "compensation")
        if availability and compensation:
            return (
                f"Disponibilidade semanal: {availability}. Valor pretendido: {compensation}.",
                "application_answer_file",
            )
        return None

    if instruction.kind == "active_contracts":
        active_contracts = _answer_value(answers, "active_contracts")
        if active_contracts:
            return f"Contratos ativos: {active_contracts}", "application_answer_file"
        return None

    return None


def _custom_answer(instruction: ApplicationInstruction, answers: dict[str, Any]) -> str:
    custom = answers.get("custom")
    if not isinstance(custom, dict):
        return ""
    exact = _answer_value(custom, instruction.text)
    if exact:
        return exact
    wanted = _normalized(instruction.text)
    for key, value in custom.items():
        if not isinstance(key, str):
            continue
        normalized_key = _normalized(key)
        if normalized_key and (normalized_key in wanted or wanted in normalized_key):
            answer = _string(value)
            if answer:
                return answer
    return ""


def _legacy_php_answer(candidate: CandidateProfile) -> str:
    for experience in candidate.experiences:
        context = " ".join(
            part
            for part in (experience.company, experience.role, experience.project)
            if part
        )
        for activity in experience.activities:
            text = f"{context}: {activity}".strip(": ")
            lowered = _normalized(text)
            if "php" in lowered and (
                "manutencao" in lowered
                or "manutencoes" in lowered
                or "evolucao" in lowered
                or "legado" in lowered
                or "correcoes" in lowered
                or "ajustes" in lowered
            ):
                return f"Sobre legado em PHP: {text}"
    return ""


def _answer_value(data: dict[str, Any], key: str) -> str:
    return _string(data.get(key))


def _string(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalized(value: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").casefold()
    return " ".join(re.findall(r"[a-z0-9]+", ascii_text))
