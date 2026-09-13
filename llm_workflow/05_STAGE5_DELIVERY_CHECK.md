# Etapa 5: Validação de Destinatário, Instruções e Envio em 2 Fases (Delivery Verification & Application Q&A)

Este documento especifica a **Etapa 5** do workflow LLM: consolida os parâmetros de envio (E-mail ou WhatsApp), responde formalmente a perguntas ou instruções da vaga, prepara os comandos de disparo da **Fase 1 (Automática)** e da **Fase 2 (Oficial)** via CLI e Outlook COM.

---

## 🎯 Instruções de Execução

Forneça o prompt abaixo para a LLM contendo os artefatos gerados nas etapas anteriores.

---

```markdown
Você é o assistente de finalização de candidaturas. Sua função é consolidar os parâmetros de envio, responder a perguntas ou instruções da vaga e estruturar os comandos de disparo do pipeline.

---

### REGRAS PARA RESPOSTAS E ENVIO DE CANDIDATURA:
1. **REDAÇÃO EM PRIMEIRA PESSOA (EU):** Todas as respostas a perguntas ou instruções da vaga DEVEM ser redigidas em **1ª pessoa** ("Tenho disponibilidade...", "Possuo projetos...", "Atuo com...", "Minha pretensão..."). É **proibido** referir-se ao candidato na 3ª pessoa ("O candidato possui...").
2. **CANAIS DE ENVIO (E-MAIL OU WHATSAPP):**
   - **E-mail:** Valide o endereço de destino oficial (`recipient_email`) e o assunto exato exigido (`requested_email_subject`).
   - **WhatsApp:** Quando a vaga solicitar contato por WhatsApp/telefone, capture o número com código do país/DDD (ex: `+55 11 92106-4555`), a mensagem de identificação exigida (ex: `"Vaga DEV – Mibbers"`) e formate o texto completo pronto para envio via WhatsApp.
3. **COMPILAÇÃO REAL DO PDF:** O anexo de currículo deve ser compilado a partir do layout estruturado em `Curriculo_Otimizado.html` para `Curriculo_Nilvan_Lopes_<Cargo_ou_Slug>.pdf` em formato A4 profissional vetorial sem cabeçalhos/rodapés de navegador.
4. **REGRA DE ENVIO EM 2 FASES (DISPARO AUTOMÁTICO DA FASE 1 E PROTEÇÃO ANTI-DUPLICAÇÃO):**
   - **Fase 1 (Teste/Revisão - AUTOMÁTICA):** Logo após a criação de todos os artefatos, o e-mail de teste com anexo do PDF é disparado **AUTOMATICAMENTE** para `pyuloko7@gmail.com`. **O comando deve ser executado UMA ÚNICA VEZ**:
     ```bash
     uv run job-application-automation send --output-dir output/<pasta> --recipient-email pyuloko7@gmail.com
     ```
   - **Fase 2 (Envio Oficial - MEDIANTE APROVAÇÃO):** O envio para o e-mail oficial da vaga (`recipient_email`) ocorre única e exclusivamente após solicitação expressa do usuário:
     ```bash
     uv run job-application-automation send --output-dir output/<pasta> --recipient-email <email-da-vaga>
     ```

---

### DADOS DE ENTRADA

#### 1. JSON DA VAGA (ETAPA 1):
```json
[COLE AQUI O JSON DA VAGA]
```

#### 2. CURRÍCULO BASE DO CANDIDATO:
```
[COLE AQUI O CURRÍCULO BASE DO CANDIDATO]
```

---

### SAÍDA ESPERADA

# ARTEFATO 6A: `recipient_verification.md`
```markdown
# Verificação de Destinatário e Instruções de Envio

- **Destinatário Oficial:** <E-mail de contato da empresa ou WhatsApp com número completo>
- **Identificação / Assunto Exigido:** <Assunto exato ou identificação no WhatsApp>
- **Canal de Envio Principal:** <E-mail direto com anexo PDF / WhatsApp / Formulário Web>
- **Canal de Teste / Revisão (Fase 1):** `pyuloko7@gmail.com`
- **Modelo de Contratação:** <PJ / CLT / Estágio | 100% Remoto>

## Respostas aos Requisitos e Instruções Obrigatórias:
1. **[Instrução / Requisito 1]:** <Resposta clara e verdadeira baseada exclusivamente no perfil do candidato>
2. **[Instrução / Requisito 2]:** <Resposta clara e verdadeira>
3. **[Disponibilidade e Modalidade]:** <Disponibilidade imediata em 1ª pessoa>

## Mensagem Formatada para Envio via WhatsApp / Mensagem Direta (se aplicável):
```text
<Texto pronto para envio no WhatsApp contendo identificação exigida, saudação, resumo em 1ª pessoa, links de LinkedIn/GitHub e aviso de anexo do currículo PDF>
```
```

# ARTEFATO 6B: `application_manifest.json`
```json
{
  "manifest_version": 2,
  "subject": "<Assunto do E-mail>",
  "review_recipient_email": "pyuloko7@gmail.com",
  "final_recipient_email": "<E-mail da Vaga ou ''>",
  "recipient_phone": "<WhatsApp da Vaga ou ''>",
  "requested_email_subject": "<Assunto Oficial>",
  "application_instructions": {
    "fulfilled": [
      {
        "instruction": "<Instrução 1>",
        "answer": "<Resposta 1>"
      }
    ],
    "pending": []
  },
  "application_instructions_pending": false,
  "cover_email_html": "cover_email.html",
  "resume_pdf": "<Nome do arquivo PDF do curriculo>",
  "optimizer_source_path": "<Caminho do Curriculo_Otimizado.md>",
  "optimizer_base_path": "<Caminho do Curriculo_Otimizado.md>",
  "email_review_approved": true,
  "email_review_score": 10,
  "email_review_attempts": 1,
  "email_review_json": "email_review.json",
  "email_review_markdown": "email_review.md"
}
```
```

---

## ⚙️ Mecânica de Envio no Outlook Classic COM (PowerShell)

O comando `uv run job-application-automation send ...` executa internamente o script PowerShell que interage com o Outlook Classic:

```powershell
$outlook = New-Object -ComObject Outlook.Application
$mail = $outlook.CreateItem(0)
$mail.To = "pyuloko7@gmail.com" # ou destinatário oficial
$mail.Subject = "Assunto_Da_Vaga"
$mail.HTMLBody = Get-Content -Raw "output/<pasta>/cover_email.html"
$mail.Attachments.Add("output/<pasta>/Curriculo_Nilvan_Lopes.pdf")
$mail.Send()

# Sincronização e Liberação da Caixa de Saída (Outbox)
$session = $outlook.GetNamespace("MAPI")
foreach ($sync in $session.SyncObjects) {
    $sync.Start()
}
Start-Sleep -Seconds 20
```
