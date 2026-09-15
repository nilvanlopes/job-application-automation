#!/usr/bin/env python3
"""Count the email body while excluding subject and visual signature."""
from __future__ import annotations

import argparse
import re
from pathlib import Path


def count_words(text: str) -> int:
    body = text.strip()
    body = re.sub(r"^\s*\*\*Assunto:\*\*.*?(?:\n|$)", "", body, count=1, flags=re.IGNORECASE)
    body = body.split("Atenciosamente,", 1)[0]
    return len(re.findall(r"\b[\wÀ-ÿ]+(?:[-'][\wÀ-ÿ]+)?\b", body, flags=re.UNICODE))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    total = count_words(args.file.read_text(encoding="utf-8"))
    print(total)
    raise SystemExit(0 if 105 <= total <= 130 else 1)


if __name__ == "__main__":
    main()
