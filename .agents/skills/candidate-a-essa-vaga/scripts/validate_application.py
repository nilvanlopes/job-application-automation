#!/usr/bin/env python3
"""Validate the portable skill's generated application package."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

FORBIDDEN = (
    "alinhamento perfeito",
    "perfil ideal",
    "sólida experiência",
    "agregar valor",
    "ansioso",
    "ansiosa",
    "ávido",
    "ávida",
    "me preparou",
    "desde o primeiro dia",
)


def body_words(text: str) -> int:
    text = re.sub(r"^\s*\*\*Assunto:\*\*.*?(?:\n|$)", "", text, count=1, flags=re.I)
    text = text.split("Atenciosamente,", 1)[0]
    return len(re.findall(r"\b[\wÀ-ÿ]+(?:[-'][\wÀ-ÿ]+)?\b", text, flags=re.UNICODE))


def validate(directory: Path) -> list[str]:
    errors: list[str] = []
    required = [
        "job_structured.json",
        "match_report.md",
        "Curriculo_Otimizado.md",
        "Curriculo_Otimizado.html",
        "recipient_verification.md",
        "application_manifest.json",
    ]
    for name in required:
        if not (directory / name).is_file():
            errors.append(f"missing:{name}")

    manifest_path = directory / "application_manifest.json"
    channel = "email"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"manifest-invalid:{exc}")
        else:
            channel = manifest.get("channel", "email")
            if manifest.get("sent") is not False:
                errors.append("manifest-sent-must-be-false")
            if manifest.get("delivery_mode") != "draft_only":
                errors.append("manifest-delivery-mode")
            if manifest.get("windows_shutdown", "not_attempted") not in {
                "requested",
                "unavailable",
                "not_attempted",
            }:
                errors.append("manifest-windows-shutdown")
            pdf_name = manifest.get("resume_pdf", "")
            if not pdf_name:
                errors.append("manifest-missing-resume-pdf")
            elif not (directory / pdf_name).is_file():
                errors.append(f"missing-pdf:{pdf_name}")

    if channel == "email":
        for name in ("cover_email.md", "cover_email.html", "email_review.md", "email_review.json"):
            if not (directory / name).is_file():
                errors.append(f"missing:{name}")
    elif channel != "whatsapp":
        errors.append(f"unsupported-channel:{channel}")

    email_path = directory / "cover_email.md"
    if email_path.exists():
        email = email_path.read_text(encoding="utf-8")
        words = body_words(email)
        if not 105 <= words <= 130:
            errors.append(f"email-word-count:{words}")
        if "Atenciosamente," not in email:
            errors.append("email-missing-closing")
        lowered = email.casefold()
        for term in FORBIDDEN:
            if term.casefold() in lowered:
                errors.append(f"forbidden:{term}")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    errors = validate(args.directory)
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        raise SystemExit(1)
    print("OK application package")


if __name__ == "__main__":
    main()
