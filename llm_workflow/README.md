# LLM Job Application Workflow (Fluxo Sequencial em 5 Etapas)

Este repositório contém o **Workflow de Candidaturas de Emprego acionado via LLM**. Ele executa o processo completo de automação em etapas modulares, integrando a sincronização com o Obsidian, geração de inteligência textual, diagramação HTML, compilação de PDF vetorial via Edge Headless (PowerShell) e disparo automático via Outlook Classic COM.

---

## 🔄 Passo Inicial: Sincronização do Currículo do Obsidian (Passo 0)

Antes de executar qualquer candidatura, o workflow sincroniza automaticamente o arquivo de currículo do Obsidian (`Curriculo.md`) para o modelo local `curriculo_base.md`:

```bash
# Sincronizar a versão mais recente do Obsidian para o currículo base
cp "/mnt/c/Users/pyu/OneDrive/Documentos/Obsidian/dev/Curriculo.md" "llm_workflow/templates/curriculo_base.md"
```

---

## 🎯 Estrutura das 5 Etapas Sequenciais do Workflow

| Etapa | Arquivo de Especificação | Função e Artefatos Gerados |
| :--- | :--- | :--- |
| **00** | **Pré-requisito (Sincronização)** | Sincroniza `/mnt/c/Users/pyu/OneDrive/Documentos/Obsidian/dev/Curriculo.md` para `llm_workflow/templates/curriculo_base.md`. |
| **01** | [`01_STAGE1_JOB_EXTRACTION.md`](file:///home/pyu/docker/job-application-automation/llm_workflow/01_STAGE1_JOB_EXTRACTION.md) | Extrai dados da vaga, limpa o título profissional (`title`), captura empresa, modalidade/contrato, e-mail e WhatsApp. Gera `job_structured.json`. |
| **02** | [`02_STAGE2_MATCH_ANALYSIS.md`](file:///home/pyu/docker/job-application-automation/llm_workflow/02_STAGE2_MATCH_ANALYSIS.md) | Realiza o cruzamento de competências em 1ª pessoa estrita ("Possuo...", "Atuei..."), identifica gaps e palavras-chave. Gera `match_report.md`. |
| **03** | [`03_STAGE3_RESUME_OPTIMIZATION.md`](file:///home/pyu/docker/job-application-automation/llm_workflow/03_STAGE3_RESUME_OPTIMIZATION.md) | Reescreve o currículo em 1ª pessoa **preservando 100% das seções e bullet points**, gera `Curriculo_Otimizado.html` e compila o `Curriculo_Nilvan_Lopes_<Cargo>.pdf` via PowerShell/Edge. |
| **04** | [`04_STAGE4_EMAIL_GENERATION.md`](file:///home/pyu/docker/job-application-automation/llm_workflow/04_STAGE4_EMAIL_GENERATION.md) | Redige o e-mail (estritamente 105–130 palavras, sem clichês), gera `cover_email.html` com o cartão visual de assinatura HTML e auto-revisão `email_review.md` (nota 10/10). |
| **05** | [`05_STAGE5_DELIVERY_CHECK.md`](file:///home/pyu/docker/job-application-automation/llm_workflow/05_STAGE5_DELIVERY_CHECK.md) | Valida destinatário/canal (E-mail ou WhatsApp), gera `application_manifest.json`, `recipient_verification.md` e executa os comandos de envio. |

---

## 📐 Regras de Ouro e Restrições Invioláveis

1. **Fidelidade Factual Absoluta:** A IA **nunca** inventa empresas, tecnologias, datas, graduações ou certificações não presentes no currículo original do candidato.
2. **Redação em Primeira Pessoa (EU):** Toda a redação do currículo, resumos, e-mail e respostas de candidatura DEVE ser em **1ª pessoa** ("Sou desenvolvedor...", "Possuo projetos...", "Tenho prática...", "Atuei..."). É **estritamente proibido** referir-se ao candidato na 3ª pessoa.
3. **Higienização do Cargo (`title`):** Remove chamadas como "Vaga para", "Contrata-se", "Urgente", nomes de cidade, empresa ou benefícios. Mantém apenas o cargo técnico limpo (ex: `Desenvolvedor Full Stack`).
4. **Métricas e Vocabulário do E-mail:**
   - Tamanho exato do corpo: **105 a 130 palavras**.
   - Termos proibidos: *"alinhamento perfeito"*, *"perfil ideal"*, *"sólida experiência"*, *"agregar valor"*, *"ansioso/ansiosa"*, *"ávido"*, *"me preparou"*, *"desde o primeiro dia"*.
   - Gênero gramatical masculino ("Desenvolvedor"), sem uso de barras como `(a)` ou `/o`.
   - **Assinatura Visual Sem Repetição de Texto:** O Markdown encerra-se em `Atenciosamente,` e o **cartão visual HTML de assinatura** é inserido imediatamente a seguir no HTML final.
5. **Preservação Obrigatória de Conteúdo no Currículo:**
   - A IA **nunca** remove seções inteiras do currículo original (Soft Skills, Outras Habilidades Técnicas, Projetos Pessoais, Formação, Certificações).
   - Todos os bullet points das experiências profissionais são preservados (manter deploys, integrações de pagamento Asaas, WhatsApp API, React Context, etc.).
   - Reordenar seções para priorizar relevância é permitido; deletar conteúdo é proibido.
6. **Suporte a Canais (E-mail e WhatsApp):**
   - E-mail direto com anexo PDF e assunto exigido pela vaga.
   - WhatsApp / Mensagem direta: gera o texto completo formatado com saudação, pontos de match e indicação de anexo PDF.

---

## 💻 Comandos Técnicos de Execução

### 1. Sincronização do Currículo do Obsidian:
```bash
cp "/mnt/c/Users/pyu/OneDrive/Documentos/Obsidian/dev/Curriculo.md" "llm_workflow/templates/curriculo_base.md"
```

### 2. Compilação do PDF Real (PowerShell / Edge Headless):
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
$pdf = 'C:\Users\pyu\OneDrive\Documentos\Obsidian\dev\Curriculo_Nilvan_Lopes_Desenvolvedor_Full_Stack.pdf'

& $browser --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf-no-header --run-all-compositor-stages-before-draw --print-to-pdf=$pdf $html
Start-Sleep -Seconds 2
if (Test-Path $pdf) { Write-Host 'PDF_SUCCESS' }
"
```

### 3. Disparo Automático da Fase 1 (Teste / Revisão - UMA ÚNICA VEZ):
```bash
uv run job-application-automation send --output-dir output/<empresa>-<cargo> --recipient-email pyuloko7@gmail.com
```

### 4. Disparo da Fase 2 (Envio Oficial - SOMENTE APÓS APROVAÇÃO):
```bash
uv run job-application-automation send --output-dir output/<empresa>-<cargo> --recipient-email <email-oficial-da-vaga>
```

---

## 📂 Estrutura da Pasta `llm_workflow`

```text
llm_workflow/
├── README.md                          # Guia e Documentação Central
├── 01_STAGE1_JOB_EXTRACTION.md        # Prompt Etapa 1: Extração da vaga
├── 02_STAGE2_MATCH_ANALYSIS.md        # Prompt Etapa 2: Relatório de Aderência
├── 03_STAGE3_RESUME_OPTIMIZATION.md   # Prompt Etapa 3: Otimização do Currículo e PDF
├── 04_STAGE4_EMAIL_GENERATION.md      # Prompt Etapa 4: E-mail, HTML e Auto-revisão
├── 05_STAGE5_DELIVERY_CHECK.md        # Prompt Etapa 5: Validação de Envio, WhatsApp e Q&A
└── templates/
    ├── candidate_profile_template.json # Modelo JSON do Candidato
    ├── curriculo_base.md              # Currículo original completo (sincronizado do Obsidian)
    └── job_input_template.md          # Modelo Markdown de Entrada da Vaga
```
