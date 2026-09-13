---
description: Workflow usado para realizar o processo completo de candidatura a vagas (5 etapas, PDF real e envio em 2 fases)
---

# Workflow de Candidatura a Vagas via LLM

Ao receber uma solicitação de candidatura (seja texto bruto, link ou print/imagem via OCR), siga **rigorosamente a ordem das etapas** descritas abaixo, executando todos os passos técnicos sem omitir nenhum detalhe.

---

## 🔄 Passo 0 (Inicial / Obrigatório): Sincronização do Currículo do Obsidian
Antes de processar qualquer vaga, garanta que o currículo base está 100% atualizado com as últimas edições do Obsidian:
- Verificar se existe `/mnt/c/Users/pyu/OneDrive/Documentos/Obsidian/dev/Curriculo.md`.
- Copiar/sincronizar seu conteúdo para [`llm_workflow/templates/curriculo_base.md`](file:///home/pyu/docker/job-application-automation/llm_workflow/templates/curriculo_base.md):
  ```bash
  cp "/mnt/c/Users/pyu/OneDrive/Documentos/Obsidian/dev/Curriculo.md" "llm_workflow/templates/curriculo_base.md"
  ```

---

## 📌 Ordem de Execução Sequencial das 5 Etapas:

### 1️⃣ Etapa 1: Extração e Higienização da Vaga (`01_STAGE1_JOB_EXTRACTION.md`)
- Extrair os dados estruturados da vaga para `output/<empresa>-<cargo>/job_structured.json`.
- **Higienização do Cargo (`title`):** Nome limpo da função técnica (ex: `"Desenvolvedor Full Stack"`, `"Estagiário em Desenvolvimento Java"`).
- **Canais de Contato:** Capturar `recipient_email` (E-mail) e/ou `recipient_phone` (WhatsApp/Telefone).
- Capturar `contract_type` (PJ/CLT/Estágio), modalidade (100% Remoto/Híbrido) e instruções/perguntas obrigatórias.

### 2️⃣ Etapa 2: Relatório de Aderência (`02_STAGE2_MATCH_ANALYSIS.md`)
- Cruzar as exigências da vaga com o currículo base em `output/<empresa>-<cargo>/match_report.md`.
- **Redação em 1ª Pessoa Estrita (EU):** "Possuo experiência...", "Atuei com...", "Desenvolvi...".
- Mapear pontos fortes, diferenciais (SaaS, gateways Asaas, APIs REST, SQL, Git), lacunas honestas e palavras-chave ATS.

### 3️⃣ Etapa 3: Otimização do Currículo e Compilação do PDF (`03_STAGE3_RESUME_OPTIMIZATION.md`)
- **Preservação Obrigatória de Conteúdo:** NUNCA remover seções inteiras (Soft Skills, Outras Habilidades Técnicas, Projetos Pessoais, Formação, Certificações) e preservar TODOS os bullet points originais.
- Gerar `output/<empresa>-<cargo>/Curriculo_Otimizado.md` e `output/<empresa>-<cargo>/Curriculo_Otimizado.html` com layout A4 portrait.
- **Compilação do PDF Real (PowerShell + Edge Headless):**
  ```powershell
  powershell.exe -NoProfile -Command "
  $browsers = @(
      'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
      'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
      'C:\Program Files\Google\Chrome\Application\chrome.exe'
  )
  $browser = $null
  foreach ($b in $browsers) { if (Test-Path $b) { $browser = $b; break } }
  if (-not $browser) { $browser = (Get-Command msedge.exe -ErrorAction SilentlyContinue).Source }

  $html = 'C:\Users\pyu\OneDrive\Documentos\Obsidian\dev\Curriculo_Otimizado.html'
  $pdf = 'C:\Users\pyu\OneDrive\Documentos\Obsidian\dev\Curriculo_Nilvan_Lopes_<Cargo>.pdf'

  & $browser --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf-no-header --run-all-compositor-stages-before-draw --print-to-pdf=$pdf $html
  Start-Sleep -Seconds 2
  if (Test-Path $pdf) { Write-Host 'PDF_SUCCESS' }
  "
  ```
- Copiar o PDF resultante para `output/<empresa>-<cargo>/Curriculo_Nilvan_Lopes_<Cargo>.pdf`.

### 4️⃣ Etapa 4: Geração do E-mail, HTML e Auto-Revisão (`04_STAGE4_EMAIL_GENERATION.md`)
- Gerar `cover_email.md` com **estritamente entre 105 e 130 palavras**, 1ª pessoa, sem termos proibidos (*"alinhamento perfeito"*, *"perfil ideal"*, *"sólida experiência"*, *"agregar valor"*, etc.) e encerrando estritamente em `Atenciosamente,`.
- Gerar `cover_email.html` com o **cartão visual HTML de assinatura completo** (banner escuro, detalhes dourados, links de WhatsApp/LinkedIn/GitHub, foto circular e contatos).
- Gerar `email_review.md` e `email_review.json` com auditoria factual (nota 10/10).

### 5️⃣ Etapa 5: Validação de Destinatário, WhatsApp e Envio em 2 Fases (`05_STAGE5_DELIVERY_CHECK.md`)
- Gerar `recipient_verification.md` e `application_manifest.json`.
- Se o canal for WhatsApp, disponibilizar o texto de apresentação formatado pronto para envio.
- **Disparo da Fase 1 (Teste / Revisão - AUTOMÁTICO e UMA ÚNICA VEZ):**
  ```bash
  uv run job-application-automation send --output-dir output/<empresa>-<cargo> --recipient-email pyuloko7@gmail.com
  ```
- **Apresentar os Artefatos ao Usuário e Aguardar Aprovação para a Fase 2 (Envio Oficial):**
  ```bash
  uv run job-application-automation send --output-dir output/<empresa>-<cargo> --recipient-email <email-da-vaga>
  ```
