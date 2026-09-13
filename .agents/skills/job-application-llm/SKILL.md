---
name: job-application-llm
description: Workflow 100% LLM para automação de candidaturas, compilação de currículo PDF e disparo automático em 2 fases via Outlook ou WhatsApp.
---

# Workflow de Candidatura LLM (Job Application Automation)

Este skill define o padrão rigoroso de execução para quando o usuário solicitar uma candidatura utilizando `/llm-workflow` ou comandos correlatos.

## ⚡ Regra de Ouro: Execução Automática da Fase 1

### 🔄 Passo 0: Sincronização Inicial do Currículo do Obsidian
- Antes de iniciar a candidatura, o arquivo de currículo mais recente do Obsidian (`/mnt/c/Users/pyu/OneDrive/Documentos/Obsidian/dev/Curriculo.md`) deve ser lido/sincronizado para atualizar a base local [`llm_workflow/templates/curriculo_base.md`](file:///home/pyu/docker/job-application-automation/llm_workflow/templates/curriculo_base.md):
  ```bash
  cp "/mnt/c/Users/pyu/OneDrive/Documentos/Obsidian/dev/Curriculo.md" "llm_workflow/templates/curriculo_base.md"
  ```
- **Currículo Alternativo Informado pelo Usuário:** Caso o usuário forneça um arquivo específico no prompt (PDF, Markdown, TXT ou caminho local), o conteúdo desse arquivo DEVE ser extraído/lido e utilizado como a base para a otimização daquela vaga específica.

---

### 📋 Etapas do Workflow de Execução Imediata:
1. **Extração da Vaga:** Criar `job_structured.json` higienizado com cargo técnico limpo (`title`), empresa (`company`), localização/modalidade (100% Remoto), tipo de contrato (PJ/CLT/Estágio), requisitos, diferenciais, responsabilidades e canais de contato (`recipient_email` e `recipient_phone`).
2. **Análise de Aderência:** Criar `match_report.md` cruzando os requisitos com o currículo de entrada em 1ª pessoa estrita ("Possuo...", "Atuei..."), com mapeamento de pontos fortes, lacunas honestas e palavras-chave ATS.
3. **Otimização do Currículo:** Criar `Curriculo_Otimizado.md` em **1ª pessoa (EU)** a partir do currículo de entrada, adaptando para as palavras-chave da vaga e **PRESERVANDO 100% DAS SEÇÕES E BULLET POINTS ORIGINAIS** (incluindo Soft Skills, Outras Habilidades Técnicas, Projetos Pessoais, Formação e Certificações).
4. **Redação do E-mail e Apresentação:** Criar `cover_email.md` e `cover_email.html` com **estritamente 105 a 130 palavras**, 1ª pessoa, sem termos proibidos (*"alinhamento perfeito"*, *"perfil ideal"*, *"sólida experiência"*, *"agregar valor"*, *"ansioso/ansiosa"*, *"ávido"*, *"me preparou"*, *"desde o primeiro dia"*) e com o cartão visual de assinatura HTML sem duplicação de texto.
5. **Auto-Revisão:** Criar `email_review.md` e `email_review.json` com nota >= 9/10 (esperado 10/10) e validação factual.
6. **Destinatário, Manifesto e WhatsApp:** Criar `recipient_verification.md` e `application_manifest.json`. Se o canal for WhatsApp/mensagem direta, disponibilizar a mensagem completa formatada pronta para envio.
7. **Diagramação e Compilação do PDF Real:** Criar `Curriculo_Otimizado.html` com layout A4 e compilar o `Curriculo_Nilvan_Lopes_<Cargo_ou_Slug>.pdf` via `scripts/compile_pdf.py` (ou Edge Headless via PowerShell):
   ```bash
   uv run python scripts/compile_pdf.py --output-dir output/<pasta>
   ```
8. **Disparo Automático da Fase 1 (Teste / Revisão):**
   - Executar **AUTOMATICAMENTE** e **UMA ÚNICA VEZ** o comando de envio para `pyuloko7@gmail.com`:
     ```bash
     uv run job-application-automation send --output-dir output/<pasta> --recipient-email pyuloko7@gmail.com
     ```
   - **PROTEÇÃO CONTRA DUPLICAÇÃO:** O comando `send` deve ser disparado exatamente uma única vez por etapa. Nunca execute chamadas paralelas ou em loop para o mesmo envio.

---

## 🛑 Fase 2: Envio Oficial para a Vaga

- A **Fase 2** (envio para o e-mail oficial da vaga/empresa) **NUNCA** é executada automaticamente.
- O agente deve apresentar o resumo da Fase 1 e aguardar a solicitação expressa do usuário para disparar a Fase 2:
  ```bash
  uv run job-application-automation send --output-dir output/<pasta> --recipient-email <email-da-vaga>
  ```
- No caso de envio por WhatsApp/contato direto, disponibilizar o texto de apresentação formatado e instruções para anexo do PDF.
