# Artefatos e manifesto

## Arquivos

O pacote completo contém:

```text
job_extracted.md
job_summary.md
job_structured.json
match_report.md
Curriculo_Otimizado.md
Curriculo_Otimizado.html
Curriculo_Nilvan_Lopes_<cargo>.pdf
cover_email.md
cover_email.html
email_review.md
email_review.json
recipient_verification.md
application_manifest.json
```

## Manifesto mínimo

```json
{
  "manifest_version": 3,
  "delivery_mode": "draft_only",
  "channel": "email|whatsapp",
  "curriculum_source_url": "",
  "final_recipient_email": "",
  "recipient_phone": "",
  "draft_created": false,
  "sent": false,
  "windows_shutdown": "requested|unavailable|not_attempted",
  "regeneration_count": 0,
  "email_review_approved": false,
  "model_trace": [],
  "artifacts": []
}
```

`sent` deve permanecer `false` nesta skill. `draft_created` só pode ser `true` depois que a ação do app confirmar a criação do rascunho. `model_trace` registra papel, modelo solicitado, modelo usado e se houve fallback.

## Gate final

Antes de criar o rascunho ou o link WhatsApp, confirme:

- JSON válido;
- destinatário ou telefone extraído literalmente;
- PDF existente, não vazio e legível;
- e-mail entre 105 e 130 palavras;
- ausência dos termos proibidos;
- preservação das seções e bullets;
- revisão factual aprovada;
- canal coerente com a instrução da vaga.
