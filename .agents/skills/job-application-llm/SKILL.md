---
name: job-application-llm
description: Workflow 100% LLM para automação de candidaturas, compilação de currículo PDF e disparo automático em 2 fases via Outlook.
---

# Workflow de Candidatura LLM (Job Application Automation)

Este skill define o padrão de execução para quando o usuário solicitar uma candidatura utilizando `llmworkflow`.

## ⚡ Regra de Ouro: Execução Automática da Fase 1

### 📄 Resolução do Currículo de Entrada:
- **Currículo Informado pelo Usuário:** Caso o usuário forneça um arquivo de currículo específico (PDF, Markdown, TXT ou caminho local), o conteúdo desse arquivo DEVE ser extraído/lido e utilizado como o currículo base para a reescrita/otimização da vaga. O arquivo fornecido NUNCA deve ser apenas copiado cegamente: ele deve passar pelo processo de otimização em 1ª pessoa (`Curriculo_Otimizado.md`), gerando o PDF customizado correspondente.
- **Currículo Padrão:** Caso o usuário não especifique nenhum currículo alternativo, utiliza-se o `curriculo_base.md` padrão do repositório.

### 📋 Etapas do Workflow de Execução Imediata:
1. **Extração da Vaga:** Criar `job_structured.json` higienizado com cargo técnico limpo, empresa, requisitos e contato.
2. **Análise de Aderência:** Criar `match_report.md` cruzando os requisitos com o currículo de entrada (informado ou padrão).
3. **Otimização do Currículo:** Criar `Curriculo_Otimizado.md` em **1ª pessoa (EU)** a partir do currículo de entrada, adaptando para as palavras-chave da vaga e preservando 100% das seções e bullet points.
4. **Redação do E-mail:** Criar `cover_email.md` e `cover_email.html` com **estritamente 105 a 130 palavras**, 1ª pessoa, sem termos proibidos ("alinhamento perfeito", "perfil ideal", "sólida experiência", etc.) e com o cartão visual de assinatura HTML.
5. **Auto-Revisão:** Criar `email_review.md` com nota >= 9/10 e validação factual.
6. **Destinatário e Manifesto:** Criar `recipient_verification.md` e `application_manifest.json`.
7. **Compilação do PDF:** Compilar o `Curriculo_Otimizado.md` em formato PDF real (`Curriculo - Nilvan Lopes - <cargo>.pdf` ou slug correspondente) para ser anexado.
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
