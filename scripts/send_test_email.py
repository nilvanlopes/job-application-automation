from pathlib import Path
from job_application_automation.signature import SignatureProfile, build_signature_html
from job_application_automation.outlook_com_mailer import send_outlook_com_email, OutlookComConfig

# 1. Montar o texto do email de teste
body_paragraphs = """
<p style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#111111;line-height:1.5;">Olá,</p>
<p style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#111111;line-height:1.5;">Este é um e-mail de teste automático enviado pelo backend do Outlook para validar a renderização da assinatura oficial.</p>
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

test_html_path = Path("output/test_email_signature.html").resolve()
test_html_path.parent.mkdir(parents=True, exist_ok=True)
test_html_path.write_text(full_html, encoding="utf-8")

recipient = "pyuloko7@gmail.com"
subject = "Teste de Assinatura Automática - Nilvan Lopes"

print(f"Disparando envio para {recipient} via Outlook COM...")

try:
    result = send_outlook_com_email(
        recipient_email=recipient,
        subject=subject,
        html_path=test_html_path,
        config=OutlookComConfig(sender_email="nilvanlopes@outlook.com"),
    )
    print("✅ SUCESSO NO ENVIO!")
    print(f"Status: {result.status}")
    print(f"Outbox matches: {result.outbox_matches}")
    print(f"Sent matches: {result.sent_matches}")
except Exception as e:
    print(f"❌ ERRO NO ENVIO: {e}")
