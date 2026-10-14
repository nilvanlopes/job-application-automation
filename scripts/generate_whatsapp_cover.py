import urllib.parse
from pathlib import Path

phone = "5563999818368"
recipient_formatted = "+55 (63) 99981-8368"
company = "ProVarejo Distribuidora"
role = "Desenvolvedor de Soluções em Programação e IA"
email = "rhdistribuidora18@gmail.com"

msg = f"""Olá! Tudo bem?

Me chamo Nilvan Lopes, sou desenvolvedor FullStack com formação em Machine Learning e experiência prática em automatização de processos, integração de APIs e inteligência artificial aplicada.

Vi a oportunidade na {company} para {role} e gostaria de me candidatar. Atuo com React, Node.js, NestJS, Python, Docker, PostgreSQL e integrações diversas (APIs REST, WhatsApp API, gateways de pagamento).

Acabei de enviar meu currículo completo em PDF por e-mail para {email}.

🔗 LinkedIn: https://www.linkedin.com/in/nilvanlopes/
💻 GitHub: https://github.com/nilvanlopes

Estou à disposição para uma conversa!

Atenciosamente,
Nilvan Lopes
(63) 99223-0471"""

encoded_msg = urllib.parse.quote(msg)
wa_link = f"https://wa.me/{phone}?text={encoded_msg}"

output_dir = Path("output/provarejo-distribuidora-desenvolvedor-ia")
output_md = output_dir / "whatsapp_cover.md"

md_content = f"""# Mensagem e Link de Candidatura via WhatsApp

- **Empresa:** {company}
- **Vaga:** {role}
- **Número do WhatsApp:** {recipient_formatted} (`{phone}`)
- **Link Direto (Clique para abrir a conversa já preenchida):**
  👉 [Abrir conversa no WhatsApp]({wa_link})

---

## 📱 Texto da Mensagem (Copiar e Colar)

```text
{msg}
```

---

## 🔗 Link Direto (wa.me)
```text
{wa_link}
```
"""

output_md.write_text(md_content, encoding="utf-8")
print(f"Generated {output_md}")
