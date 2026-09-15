#!/usr/bin/env python3
"""Build a safe wa.me URL without sending a WhatsApp message."""
from __future__ import annotations

import argparse
import re
from urllib.parse import quote


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("00"):
        digits = digits[2:]
    if not digits:
        raise ValueError("telefone sem dígitos")
    return digits


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phone")
    parser.add_argument("message")
    args = parser.parse_args()
    phone = normalize_phone(args.phone)
    print(f"https://wa.me/{phone}?text={quote(args.message, safe='')}")


if __name__ == "__main__":
    main()
