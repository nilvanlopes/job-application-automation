from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DeliveryAuditResult:
    output_dir: str
    recipient_email: str
    subject: str
    claimed_status: str
    sent_matches: int
    delivery_verification_source: str
    server_confirmed: bool
    verification_status: str
    needs_resend: bool
    verified_at: str
    reason: str


def audit_send_artifacts(
    output_root: Path,
    *,
    now: datetime | None = None,
    write: bool = True,
) -> list[DeliveryAuditResult]:
    verified_at = (now or datetime.now(timezone.utc)).isoformat()
    results = [
        _audit_result_file(path, verified_at=verified_at, write=write)
        for path in sorted(Path(output_root).glob("**/final_send_result.json"))
    ]
    if write:
        report_path = Path(output_root) / "send_delivery_audit.json"
        report_path.write_text(
            json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return results


def _audit_result_file(
    result_path: Path,
    *,
    verified_at: str,
    write: bool,
) -> DeliveryAuditResult:
    output_dir = result_path.parent
    result_data = _load_json(result_path)
    manifest = _load_json(output_dir / "application_manifest.json")
    recipient = _string(result_data, "recipient_email") or _string(manifest, "final_recipient_email")
    subject = _string(result_data, "subject") or _string(manifest, "subject")
    claimed_status = _string(result_data, "status")
    sent_matches = _int(result_data, "sent_matches")

    server_confirmed = result_data.get("server_confirmed") is True
    verification_source = _string(result_data, "delivery_verification_source")
    if server_confirmed:
        verification_status = "server_confirmed"
        needs_resend = False
        reason = "Envio já marcado como confirmado no servidor."
        verification_source = verification_source or "server"
    elif _looks_like_local_submission(claimed_status, sent_matches):
        verification_status = "local_only"
        needs_resend = True
        reason = (
            "Artefato antigo ou local do Outlook COM: encontrou item local, "
            "mas não há confirmação server-side."
        )
        verification_source = verification_source or "outlook_com_local"
    else:
        verification_status = "not_found"
        needs_resend = True
        reason = "Nenhuma confirmação server-side foi registrada."
        verification_source = verification_source or "none"

    audit = DeliveryAuditResult(
        output_dir=str(output_dir),
        recipient_email=recipient,
        subject=subject,
        claimed_status=claimed_status,
        sent_matches=sent_matches,
        delivery_verification_source=verification_source,
        server_confirmed=server_confirmed,
        verification_status=verification_status,
        needs_resend=needs_resend,
        verified_at=verified_at,
        reason=reason,
    )
    if write:
        _write_audit_files(result_path, result_data, audit)
    return audit


def _write_audit_files(
    result_path: Path,
    result_data: dict,
    audit: DeliveryAuditResult,
) -> None:
    result_data.update(
        {
            "delivery_verification_source": audit.delivery_verification_source,
            "server_confirmed": audit.server_confirmed,
            "verification_status": audit.verification_status,
            "needs_resend": audit.needs_resend,
            "verified_at": audit.verified_at,
            "verification_reason": audit.reason,
        }
    )
    if result_data.get("status") == "sent" and audit.verification_status == "local_only":
        result_data["status"] = "submitted_local"
    result_path.write_text(json.dumps(result_data, ensure_ascii=False, indent=2), encoding="utf-8")
    audit_path = result_path.parent / "delivery_audit.json"
    audit_path.write_text(json.dumps(asdict(audit), ensure_ascii=False, indent=2), encoding="utf-8")


def _looks_like_local_submission(claimed_status: str, sent_matches: int) -> bool:
    return claimed_status in {"sent", "submitted_local"} or sent_matches > 0


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _string(data: dict, key: str) -> str:
    value = data.get(key)
    return value.strip() if isinstance(value, str) else ""


def _int(data: dict, key: str) -> int:
    value = data.get(key)
    return value if isinstance(value, int) else 0
