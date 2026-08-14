# LLM-Only Job Application Workflow (Sem Código)

Este repositório contém o **Workflow 100% via LLM** para automação de candidaturas de emprego. Ele replica com precisão toda a lógica do orquestrador em Python, permitindo executar o processo completo **sem utilizar código**, usando apenas prompts estruturados em qualquer modelo de linguagem (ChatGPT, Claude, Gemini, DeepSeek, Ollama, OpenRouter, etc.).

---

## 🎯 Objetivo

Transformar um anúncio de vaga e o currículo original de um candidato nos seguintes **6 artefatos finais**:

1. `job_structured.json` – Dados extraídos e higienizados da vaga (cargo limpo, empresa, requisitos, instruções, contato).
2. `match_report.md` – Análise de aderência, pontos fortes e equivalências entre o currículo e a vaga.
3. `Curriculo_Otimizado.md` – Versão adaptada do currículo priorizando palavras-chave e relevância para a vaga (sem inventar experiências).
4. `cover_email.md` / `cover_email.html` – E-mail de apresentação persuasivo, direto (105 a 130 palavras) e sem clichês.
5. `email_review.md` – Relatório de revisão factual e de qualidade do e-mail gerado (nota 9 a 10).
6. `recipient_verification.md` e `application_answers.md` – Destinatário final validado e respostas para perguntas específicas da candidatura.

---

## 🚀 Como Utilizar

Você possui **duas formas** de executar este workflow:

### Modo A: Execução em Prompt Único (Recomendado para rapidez)

Ideal para uso direto no ChatGPT, Claude Web, Gemini ou qualquer chat com IA.

1. Abra o arquivo [`00_MASTER_SINGLE_PROMPT.md`](file:///home/pyu/docker/job-application-automation/llm_workflow/00_MASTER_SINGLE_PROMPT.md).
2. Copie o prompt mestre completo.
3. Cole o prompt no seu LLM preferido, anexando/preenchendo os blocos com o seu **Currículo Base** e a **Descrição da Vaga**.
4. A IA gerará todos os artefatos estruturados em uma única resposta.

---

## Modo B: Execução Etapa por Etapa (Maior precisão e controle)

Ideal para pipelines de agentes (LangChain, Flowise, n8n, Dify) ou quando você deseja revisar o resultado de cada etapa antes de avançar.

| Etapa | Arquivo de Prompt | Função |
| :--- | :--- | :--- |
| **01** | [`01_STAGE1_JOB_EXTRACTION.md`](file:///home/pyu/docker/job-application-automation/llm_workflow/01_STAGE1_JOB_EXTRACTION.md) | Extrai dados da vaga, limpa o título profissional, identifica a empresa e contato. |
| **02** | [`02_STAGE2_MATCH_ANALYSIS.md`](file:///home/pyu/docker/job-application-automation/llm_workflow/02_STAGE2_MATCH_ANALYSIS.md) | Realiza o cruzamento de competências e gera o relatório de aderência (`match_report.md`). |
| **03** | [`03_STAGE3_RESUME_OPTIMIZATION.md`](file:///home/pyu/docker/job-application-automation/llm_workflow/03_STAGE3_RESUME_OPTIMIZATION.md) | Reescreve o currículo com foco nas palavras-chave da vaga, mantendo a verdade dos fatos. |
| **04** | [`04_STAGE4_EMAIL_GENERATION.md`](file:///home/pyu/docker/job-application-automation/llm_workflow/04_STAGE4_EMAIL_GENERATION.md) | Gera o e-mail curto (105–130 palavras) + faz o auto-critério de revisão factual (nota >= 9). |
| **05** | [`05_STAGE5_DELIVERY_CHECK.md`](file:///home/pyu/docker/job-application-automation/llm_workflow/05_STAGE5_DELIVERY_CHECK.md) | Valida o e-mail de envio final, assunto obrigatório e gera respostas para perguntas da vaga. |

---

## 📐 Regras de Qualidade Guardadas nos Prompts

- **Fidelidade Factual Rígida:** A IA **nunca** inventa empresas, tecnologias, datas, graduações ou certificações não presentes no currículo original.
- **Redação em Primeira Pessoa (EU):** Toda a redação do currículo, resumos, e-mail e respostas de candidatura DEVE ser em **1ª pessoa** ("Sou acadêmico...", "Possuo projetos...", "Tenho prática..."). É **proibido** referir-se ao candidato na 3ª pessoa ("Nilvan possui...", "O candidato é...").
- **Cargo Limpo (Title):** Remoção de frases como "Vaga para", "Contrata-se", "Urgente", nomes de cidade ou benefícios. Mantém-se apenas o cargo técnico (ex: `Desenvolvedor Fullstack React/Node.js`).
- **Métricas e Estrutura do E-mail:**
  - Tamanho exato do corpo: **105 a 130 palavras**.
  - Termos proibidos: *"alinhamento perfeito"*, *"perfil ideal"*, *"sólida experiência"*, *"agregar valor"*, *"ansioso/ansiosa"*, *"ávido"*, *"me preparou"*, *"desde o primeiro dia"*.
  - Gênero fixo masculino (sem marcações neutras como `(a)` ou `/o`).
  - **Assinatura Visual Sem Repetição de Texto:** O e-mail em Markdown encerra-se estritamente na saudação final `Atenciosamente,`. O cartão visual HTML de assinatura é inserido imediatamente a seguir no e-mail final enviado pelo Outlook, evitando duplicação de texto.
  - **Nomenclatura e Compilação Real do Anexo PDF:** O arquivo de currículo anexado deve ser compilado como um PDF real completo (`Curriculo - <nome-do-candidato> - <vaga>.pdf`), proibindo o uso de arquivos mock ou em branco.
  - **Regra de Envio em 2 Fases (Execução Automática da Fase 1 e Proteção Anti-Duplicação):**
    - **Fase 1 (Teste/Revisão - AUTOMÁTICA):** O e-mail de teste com anexo do currículo PDF é disparado **AUTOMATICAMENTE** para `pyuloko7@gmail.com` logo após a geração de todos os artefatos. O comando deve ser executado **EXATAMENTE UMA ÚNICA VEZ** (sem chamadas concorrentes ou loops).
    - **Fase 2 (Envio Oficial - MEDIANTE APROVAÇÃO):** Mediante solicitação expressa do usuário, o e-mail oficial é disparado para o destinatário da vaga (`recipient_email`).
    - **Comandos de Disparo (CLI/Terminal):**
      ```bash
      # Fase 1 (Automática):
      uv run job-application-automation send --output-dir output/<empresa>-<cargo> --recipient-email pyuloko7@gmail.com

      # Fase 2 (Após Aprovação do Usuário):
      uv run job-application-automation send --output-dir output/<empresa>-<cargo> --recipient-email <email-da-vaga>
      ```
    - **Garantia de Sincronia no Outlook COM:** O disparo em segundo plano itera por todos os `SyncObjects` (`$session.SyncObjects`) e aguarda o tempo de sincronização de 20s para garantir o envio imediato da Caixa de Saída (*Outbox*).
- **Preservação Obrigatória de Conteúdo (Currículo):**
  - A IA **nunca** remove seções inteiras do currículo original (Soft Skills, Outras Habilidades Técnicas, Projetos Pessoais).
  - Todos os bullet points das experiências profissionais são reformulados, mas **nunca omitidos**.
  - Reordenar seções para priorizar relevância é permitido; apagar conteúdo é proibido.
- **Estrutura de Pastas de Saída:** Quando salvar localmente os artefatos, crie a pasta `output/<empresa>-<cargo>/`.

---

## 📄 Currículo de Entrada (Base ou Personalizado)

- **Currículo Padrão:** O arquivo [`curriculo_base.md`](file:///home/pyu/docker/job-application-automation/llm_workflow/templates/curriculo_base.md) (espelhado de `/mnt/c/Users/pyu/OneDrive/Documentos/Obsidian/dev/Curriculo.md`) contém o currículo original completo do candidato e é usado por padrão quando nenhum arquivo alternativo é informado.
- **Currículo Personalizado Informado pelo Usuário:** Quando o usuário fornecer um arquivo de currículo alternativo (ex: `curriculo_nilvan_lopes.pdf`, `.md` ou `.txt`), o workflow deve **extrair seu texto e utilizá-lo como o currículo base**, passando-o obrigatoriamente pela reescrita da Etapa 3 (`Curriculo_Otimizado.md`) e compilando o novo PDF otimizado antes do envio.

> **Para vagas de suporte:** complemente o currículo com informações de perfil do candidato (experiências em suporte presencial/remoto, hardware, redes, ITIL, Google Workspace, Windows Enterprise, etc.).

---

## 📑 Geração de PDF ATS-Friendly (Padrão Curriculum Optimizer)

O `Curriculo_Otimizado.md` gerado pela Etapa 3 precisa ser convertido em PDF para envio. 

### Padrão de Nomenclatura do PDF:
O arquivo PDF do currículo gerado deve ser obrigatoriamente nomeado no padrão: **`Curriculo - <nome-do-candidato> - <vaga>.pdf`** (ou no formato slugified `nilvan-lopes-desenvolvedor-java-junior.pdf`).
Exemplo: `Curriculo - Nilvan Lopes - Desenvolvedor Java Júnior.pdf` (ou `nilvan-lopes-desenvolvedor-java-junior.pdf`).

### Opção A: Curriculum Optimizer (Docker) — Recomendado
O projeto [`curriculum-optimizer`](file:///home/pyu/docker/curriculum-optimizer) gera PDFs com layout profissional e **100% compatíveis com ATS** (texto totalmente extraível por parsers como `pypdf`).

```bash
# O pipeline de código já integra automaticamente:
python -m job_application_automation apply --job-file vaga.txt
```

### Opção B: Pandoc (Simples e rápido)
```bash
pandoc Curriculo_Otimizado.md -o "Curriculo - <nome-do-candidato> - <vaga>.pdf" \
  --pdf-engine=xelatex \
  -V geometry:margin=2cm \
  -V mainfont="DejaVu Sans"
```

### Opção C: Google Docs / Word
1. Cole o conteúdo do `.md` no Google Docs
2. Ajuste a formatação
3. Exporte como PDF (`Arquivo > Fazer download > PDF`) nomeando como `<empresa>-<cargo>.pdf`

> **Dica ATS:** Evite tabelas complexas, imagens de texto, e colunas múltiplas. O layout mais simples e linear é o mais seguro para sistemas ATS.

---

## 📂 Estrutura da Pasta `llm_workflow`

```text
llm_workflow/
├── README.md                          # Guia do Workflow LLM
├── 00_MASTER_SINGLE_PROMPT.md         # Prompt Orquestrador Único (Tudo em um)
├── 01_STAGE1_JOB_EXTRACTION.md        # Prompt Etapa 1: Extração da vaga
├── 02_STAGE2_MATCH_ANALYSIS.md        # Prompt Etapa 2: Relatório de Aderência
├── 03_STAGE3_RESUME_OPTIMIZATION.md   # Prompt Etapa 3: Otimização do Currículo
├── 04_STAGE4_EMAIL_GENERATION.md      # Prompt Etapa 4: E-mail e Auto-revisão
├── 05_STAGE5_DELIVERY_CHECK.md        # Prompt Etapa 5: Validação de Envio e Q&A
└── templates/
    ├── candidate_profile_template.json # Modelo JSON do Candidato
    ├── curriculo_base.md              # Currículo original completo (referência fixa)
    └── job_input_template.md          # Modelo Markdown de Entrada da Vaga
```

