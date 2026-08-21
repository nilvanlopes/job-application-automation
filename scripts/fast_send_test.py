import subprocess
from pathlib import Path
from job_application_automation.signature import SignatureProfile, build_signature_html
from job_application_automation.outlook_com_mailer import _to_windows_path, _ps_quote

# 1. Montar o texto do email
body_paragraphs = """
<p style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#111111;line-height:1.5;">Olá,</p>
<p style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#111111;line-height:1.5;">Este é o teste de validação do envio automático com a assinatura oficial com fundo geométrico dourado.</p>
<p style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#111111;line-height:1.5;margin-bottom:16px;">Atenciosamente,</p>
"""

# 2. Gerar a assinatura
profile = SignatureProfile(
    name="Nilvan Lopes",
    role="Desenvolvedor FullStack",
    phone="(63) 99223-0471",
    email="nilvanlopes@outlook.com",
    website="https://nilvanlopes.com",
    linkedin="https://www.linkedin.com/in/nilvanlopes",
    github="https://github.com/nilvanlopes",
    whatsapp="https://wa.me/5563992230471",
)
sig_html = build_signature_html(profile)
full_html = f"<html><body style='font-family:Arial,Helvetica,sans-serif;color:#111111;'>{body_paragraphs}{sig_html}</body></html>"

test_html_path = Path("output/fast_test_email.html").resolve()
test_html_path.parent.mkdir(parents=True, exist_ok=True)
test_html_path.write_text(full_html, encoding="utf-8")

windows_html_path = _to_windows_path(test_html_path)
sender_email = _ps_quote("nilvanlopes@outlook.com")
recipient_email = _ps_quote("pyuloko7@gmail.com")
subject = _ps_quote("Teste de Assinatura Automática - Nilvan Lopes")

ps_code = f"""
$ErrorActionPreference = "Stop";
$outlook = New-Object -ComObject Outlook.Application;
$session = $outlook.Session;

$account = $session.Accounts | Where-Object {{ $_.SmtpAddress -eq {sender_email} }} | Select-Object -First 1;
if (-not $account) {{
    $account = $session.Accounts.Item(1);
}}

$html = Get-Content '{windows_html_path}' -Raw -Encoding UTF8;
$mail = $outlook.CreateItem(0);
$mail.SendUsingAccount = $account;
$mail.To = {recipient_email};
$mail.Subject = {subject};
$mail.HTMLBody = $html;
$mail.Send();

Write-Host "ENVIADO_COM_SUCESSO para {recipient_email}";

# Disparar envio da Caixa de Saida imediatamente
try {{
    for($i = 1; $i -le $session.SyncObjects.Count; $i++) {{
        try {{
            $s = $session.SyncObjects.Item($i);
            $s.Start();
        }} catch {{}}
    }}
}} catch {{}}
"""

print("Enviando e-mail de teste agora...")
cmd = ["powershell.exe", "-NoProfile", "-Command", ps_code]
try:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    print("✅ Concluído!")
except Exception as e:
    print("ERRO:", e)
