from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence, Any


@dataclass(slots=True)
class OutlookComConfig:
    sender_email: str = "nilvanlopes@outlook.com"
    powershell_executable: str = "powershell.exe"
    verify_delay_seconds: int = 5


@dataclass(slots=True)
class OutlookComSendResult:
    recipient_email: str
    subject: str
    status: str
    outbox_matches: int
    sent_matches: int
    raw_output: str


class OutlookComSendError(RuntimeError):
    pass


def send_outlook_com_email(
    *,
    recipient_email: str,
    subject: str,
    html_path: str | Path,
    attachment_paths: Sequence[str | Path] | None = None,
    config: OutlookComConfig | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> OutlookComSendResult:
    config = config or OutlookComConfig()
    html_path = Path(html_path)
    if not recipient_email.strip():
        raise OutlookComSendError("recipient_email is required")
    if not html_path.exists():
        raise OutlookComSendError(f"HTML body file not found: {html_path}")
    attachments = [Path(path) for path in (attachment_paths or [])]
    for attachment in attachments:
        if not attachment.exists():
            raise OutlookComSendError(f"Attachment file not found: {attachment}")

    command = [
        config.powershell_executable,
        "-NoProfile",
        "-Command",
        _build_powershell_script(
            sender_email=config.sender_email,
            recipient_email=recipient_email,
            subject=subject,
            html_path=_to_windows_path(html_path),
            attachment_paths=[_to_windows_path(path) for path in attachments],
            verify_delay_seconds=config.verify_delay_seconds,
        ),
    ]
    completed = runner(command, capture_output=True, text=True, timeout=180)
    stdout = getattr(completed, "stdout", "") or ""
    stderr = getattr(completed, "stderr", "") or ""
    returncode = getattr(completed, "returncode", 0)
    raw = stdout + (f"\nSTDERR:\n{stderr}" if stderr else "")
    if returncode != 0:
        raise OutlookComSendError(raw.strip() or f"PowerShell exited with {returncode}")

    outbox_matches = _extract_count(stdout, "OUTBOX_MATCHES")
    sent_matches = _extract_count(stdout, "SENT_MATCHES")
    status = "sent" if outbox_matches == 0 and sent_matches >= 1 else "unknown"
    if status != "sent":
        raise OutlookComSendError(f"Outlook COM send was not verified: {raw}")

    return OutlookComSendResult(
        recipient_email=recipient_email,
        subject=subject,
        status=status,
        outbox_matches=outbox_matches,
        sent_matches=sent_matches,
        raw_output=raw,
    )


def _build_powershell_script(*, sender_email: str, recipient_email: str, subject: str, html_path: str, attachment_paths: Sequence[str], verify_delay_seconds: int) -> str:
    sender = _ps_quote(sender_email)
    recipient = _ps_quote(recipient_email)
    quoted_subject = _ps_quote(subject)
    quoted_html_path = _ps_quote(html_path)
    attachment_lines = "\n".join(
        f"[void]$mail.Attachments.Add({_ps_quote(path)});" for path in attachment_paths
    )
    return f"""
$ErrorActionPreference="Stop";
$outlook = New-Object -ComObject Outlook.Application;
$session = $outlook.Session;
$account = $session.Accounts | Where-Object {{ $_.SmtpAddress -eq {sender} }} | Select-Object -First 1;
if(-not $account){{ throw "Outlook account not found: {sender_email}" }};
$html = Get-Content {quoted_html_path} -Raw -Encoding UTF8;
$mail = $outlook.CreateItem(0);
$mail.SendUsingAccount = $account;
$mail.To = {recipient};
$mail.Subject = {quoted_subject};
$mail.HTMLBody = $html;
{attachment_lines}
$mail.Send();
Write-Host "SENT_COM_MAIL to={recipient_email} from=$($account.SmtpAddress) subject={subject}";
Start-Sleep -Seconds {verify_delay_seconds};
$outbox = $session.GetDefaultFolder(4);
$sent = $session.GetDefaultFolder(5);
$outboxMatches = @($outbox.Items | Where-Object {{ $_.To -like "*{recipient_email}*" -and $_.Subject -eq {quoted_subject} }});
$sentItems = $sent.Items;
$sentItems.Sort("[SentOn]", $true);
$sentMatches = @();
foreach($item in $sentItems){{
  if($sentMatches.Count -ge 3){{ break }};
  try {{ if($item.To -like "*{recipient_email}*" -and $item.Subject -eq {quoted_subject}){{ $sentMatches += $item }} }} catch {{}}
}}
Write-Host "OUTBOX_MATCHES=$($outboxMatches.Count)";
Write-Host "SENT_MATCHES=$($sentMatches.Count)";
foreach($m in $sentMatches){{ Write-Host "SENT_ITEM SentOn=$($m.SentOn) To=$($m.To) Subject=$($m.Subject)" }};
""".strip()


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _to_windows_path(path: Path) -> str:
    resolved = path.resolve()
    text = str(resolved)
    if text.startswith("/mnt/") and len(text) > 6:
        drive = text[5]
        rest = text[7:].replace("/", "\\")
        return f"{drive.upper()}:\\{rest}"
    return "\\\\wsl.localhost\\Ubuntu" + text.replace("/", "\\")


def _extract_count(output: str, key: str) -> int:
    match = re.search(rf"{re.escape(key)}=(\d+)", output)
    return int(match.group(1)) if match else 0
