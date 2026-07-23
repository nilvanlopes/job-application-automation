from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from job_application_automation.delivery_audit import audit_send_artifacts
from job_application_automation.outlook_com_mailer import send_outlook_com_email


def test_audit_send_artifacts_marks_legacy_local_sent_as_needs_resend(tmp_path):
    output = tmp_path / "pace-tech"
    output.mkdir()
    (output / "application_manifest.json").write_text(
        json.dumps(
            {
                "subject": "Candidatura - Desenvolvedor FullStack",
                "final_recipient_email": "contato@pacetech.com.br",
            }
        ),
        encoding="utf-8",
    )
    result_path = output / "final_send_result.json"
    result_path.write_text(
        json.dumps(
            {
                "recipient_email": "contato@pacetech.com.br",
                "subject": "Candidatura - Desenvolvedor FullStack",
                "status": "sent",
                "outbox_matches": 0,
                "sent_matches": 2,
                "raw_output": "SENT_MATCHES=2",
            }
        ),
        encoding="utf-8",
    )

    results = audit_send_artifacts(
        tmp_path,
        now=datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc),
    )

    assert len(results) == 1
    assert results[0].verification_status == "local_only"
    assert results[0].server_confirmed is False
    assert results[0].needs_resend is True
    updated = json.loads(result_path.read_text(encoding="utf-8"))
    assert updated["status"] == "submitted_local"
    assert updated["verification_status"] == "local_only"
    assert updated["needs_resend"] is True
    assert json.loads((output / "delivery_audit.json").read_text(encoding="utf-8"))[
        "recipient_email"
    ] == "contato@pacetech.com.br"
    assert (tmp_path / "send_delivery_audit.json").exists()


def test_audit_send_artifacts_preserves_server_confirmed_result(tmp_path):
    output = tmp_path / "confirmed"
    output.mkdir()
    (output / "application_manifest.json").write_text("{}", encoding="utf-8")
    (output / "final_send_result.json").write_text(
        json.dumps(
            {
                "recipient_email": "rh@example.com",
                "subject": "Candidatura - Python",
                "status": "sent",
                "sent_matches": 1,
                "server_confirmed": True,
                "delivery_verification_source": "outlook_server",
            }
        ),
        encoding="utf-8",
    )

    result = audit_send_artifacts(tmp_path, write=False)[0]

    assert result.verification_status == "server_confirmed"
    assert result.needs_resend is False


def test_outlook_com_mailer_reports_local_submission_not_server_send(tmp_path):
    html = tmp_path / "email.html"
    html.write_text("<html>Email</html>", encoding="utf-8")
    captured = {}

    def runner(command, **kwargs):
        captured["command"] = command
        return SimpleNamespace(
            returncode=0,
            stdout=(
                "SENT_COM_MAIL to=rh@example.com from=nilvanlopes@outlook.com "
                "subject=Candidatura\nOUTLOOK_SYNC_STARTED name=All Accounts\n"
                "OUTBOX_MATCHES=0\nSENT_MATCHES=1\n"
            ),
            stderr="",
        )

    result = send_outlook_com_email(
        recipient_email="rh@example.com",
        subject="Candidatura",
        html_path=html,
        runner=runner,
    )

    assert result.status == "submitted_local"
    assert result.delivery_verification_source == "outlook_com_local"
    assert result.server_confirmed is False
    assert result.verification_status == "local_only"
    assert "SyncObjects" in captured["command"][-1]
    assert "OUTLOOK_SYNC_STARTED" in captured["command"][-1]
