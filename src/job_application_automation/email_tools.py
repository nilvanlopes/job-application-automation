from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .models import EmailVerificationResult


_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}$"
)
_DISPOSABLE_DOMAINS = {
    "mailinator.com",
    "10minutemail.com",
    "guerrillamail.com",
    "yopmail.com",
}


@dataclass(slots=True)
class _DnsResult:
    mx_valid: Optional[bool]
    checker: str


def verify_email_address(email: str) -> EmailVerificationResult:
    normalized = email.strip()
    reasons: list[str] = []
    syntax_valid = bool(_EMAIL_RE.match(normalized))
    checker = "stdlib-regex"
    mx_valid: Optional[bool] = None
    deliverable: Optional[bool] = None

    if not syntax_valid:
        reasons.append("invalid email syntax")
        return EmailVerificationResult(
            email=email,
            normalized_email=normalized,
            syntax_valid=False,
            mx_valid=None,
            deliverable=False,
            reasons=reasons,
            checker=checker,
        )

    domain = normalized.rsplit("@", 1)[-1].lower()
    if domain in _DISPOSABLE_DOMAINS:
        reasons.append("disposable email domain")

    dns_result = _check_mx(domain)
    mx_valid = dns_result.mx_valid
    checker = dns_result.checker

    if mx_valid is False:
        reasons.append("domain has no MX records")
        deliverable = False
    elif mx_valid is None:
        reasons.append("MX lookup unavailable; falling back to syntax-only check")
        deliverable = None
    else:
        deliverable = syntax_valid and not any(
            reason == "disposable email domain" for reason in reasons
        )


    return EmailVerificationResult(
        email=email,
        normalized_email=normalized,
        syntax_valid=syntax_valid,
        mx_valid=mx_valid,
        deliverable=deliverable,
        reasons=reasons,
        checker=checker,
    )


def format_verification_markdown(result: EmailVerificationResult) -> str:
    reasons = "; ".join(result.reasons) if result.reasons else "none"
    return (
        "# Recipient Email Verification\n\n"
        f"- Email: {result.normalized_email}\n"
        f"- Syntax valid: {result.syntax_valid}\n"
        f"- MX valid: {result.mx_valid}\n"
        f"- Deliverable: {result.deliverable}\n"
        f"- Checker: {result.checker}\n"
        f"- Reasons: {reasons}\n"
    )


def _check_mx(domain: str) -> _DnsResult:
    try:
        import dns.resolver  # type: ignore
    except Exception:
        return _DnsResult(mx_valid=None, checker="stdlib-regex")

    try:
        answers = dns.resolver.resolve(domain, "MX")
        has_mx = any(True for _ in answers)
        return _DnsResult(mx_valid=has_mx, checker="dnspython")
    except Exception:
        return _DnsResult(mx_valid=False, checker="dnspython")
