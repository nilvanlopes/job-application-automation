# Job Application Automation

Orquestrador Python que transforma uma vaga em uma candidatura personalizada. Ele extrai a vaga, gera e revisa o e-mail com fallback entre providers de IA, chama o `curriculum-optimizer` com o mesmo currículo original e, opcionalmente, envia uma cópia para revisão pelo Outlook Classic.

## Fluxo

```text
texto | arquivo | imagem da vaga
          |
          v
extração e estruturação da vaga
          |
          +----> mesmo --resume-file para profile, e-mail e optimizer
          |
          v
e-mail escrito e revisado por IA
          |
          v
curriculum-optimizer: currículo original -> base em cache -> PDF otimizado
          |
          v
artefatos locais -> revisão humana -> envio final sem regeneração
```

Regras principais:

- use exatamente uma entrada: `--job-text`, `--job-file` ou `--job-image`;
- `--resume-file` aceita MD, TXT, HTML, HTM e PDF com texto extraível;
- a mesma fonte alimenta o profile, o contexto do e-mail e o optimizer;
- PDF somente escaneado precisa passar por OCR antes;
- `apply --send` envia a cópia de revisão, por padrão para `pyuloko7@gmail.com`;
- `send --output-dir` envia os artefatos aprovados à empresa sem IA, OCR ou optimizer;
- o PDF do optimizer é o único currículo copiado e anexado;
- o provider do job app segue `JOB_APPLICATION_PROVIDERS_ORDER`, salvo quando `--provider` é informado;
- `.env` do optimizer define o provider do optimizer, salvo quando `--optimizer-provider` é informado.

## Instalação

Requisitos: Python 3.11+, `uv`, Docker Compose se usar Ollama gerenciado, credenciais dos providers remotos escolhidos e Outlook Classic para envios.

```bash
uv sync
```

Variáveis úteis:

```env
OUTLOOK_COM_SENDER_EMAIL="nilvanlopes@outlook.com"
JOB_APPLICATION_REVIEW_EMAIL="pyuloko7@gmail.com"
JOB_APPLICATION_DEFAULT_RESUME="/caminho/curriculo.md"
JOB_APPLICATION_OPTIMIZER_ROOT="/home/pyu/docker/curriculum-optimizer"
JOB_APPLICATION_PROVIDERS_ORDER="gemini,openrouter,ollama"
GOOGLE_API_KEY=""
GOOGLE_MODEL="gemini-3.5-flash"
OPENROUTER_API_KEY=""
OPENROUTER_MODEL="nvidia/nemotron-3-super-120b-a12b:free"
JOB_APPLICATION_OLLAMA_BASE_URL="http://localhost:11434/api"
JOB_APPLICATION_OLLAMA_MODEL="qwen2.5:7b"
JOB_APPLICATION_OLLAMA_EMAIL_ANALYSIS_MODEL="qwen3.5:9b"
JOB_APPLICATION_OLLAMA_EMAIL_MODEL="qwen3.5:9b"
JOB_APPLICATION_OLLAMA_MANAGE_SERVICE="true"
JOB_APPLICATION_OLLAMA_SHUTDOWN_WHEN_DONE="true"
```

O job app usa `JOB_APPLICATION_PROVIDERS_ORDER` para não vazar `PROVIDERS_ORDER` para o `curriculum-optimizer`. A ordem padrão é `gemini,openrouter,ollama`: providers sem env obrigatório são pulados; falhas de HTTP, rede, quota, resposta vazia, truncamento ou JSON inválido marcam o provider como indisponível pelo restante da execução e a mesma chamada segue no próximo provider. Use `--provider` quando quiser tentar somente um provider, sem fallback.

Providers aceitos no job app: `gemini`, `openrouter`, `openai`, `anthropic`, `claude` como alias de `anthropic`, `lmstudio` e `ollama`. OpenRouter exige modelo com `:free`.

O provider do `curriculum-optimizer` é separado. Configure-o no `.env` do optimizer ou use `--optimizer-provider`; essa opção não altera a IA usada pelo job app.

## Uso

Texto ou arquivo:

```bash
uv run job-application-automation apply \
  --job-file input/vaga.txt \
  --resume-file input/curriculo.pdf
```

Imagem, provider específico e envio para revisão:

```bash
uv run job-application-automation apply \
  --job-image input/vaga.png \
  --resume-file input/curriculo.md \
  --provider gemini \
  --optimizer-provider ollama \
  --send
```

Fallback padrão Gemini -> OpenRouter -> Ollama:

```bash
JOB_APPLICATION_PROVIDERS_ORDER="gemini,openrouter,ollama" \
uv run job-application-automation apply \
  --job-file input/vaga.txt \
  --resume-file input/curriculo.md
```

Forçar somente Ollama no job app:

```bash
uv run job-application-automation apply \
  --job-text "Vaga Python. Enviar para vagas@example.com" \
  --provider ollama
```

Não informe `--recipient-email` no primeiro `apply --send` automático apenas
porque a vaga contém um e-mail. Esse envio é a cópia de revisão para
`JOB_APPLICATION_REVIEW_EMAIL` ou `pyuloko7@gmail.com`. O envio final acontece
depois com `send --output-dir`, usando o destinatário capturado nos artefatos ou
um `--recipient-email` informado explicitamente nesse comando final.

Envio final aprovado:

```bash
uv run job-application-automation send \
  --output-dir output/empresa-cargo
```

Opções de `apply`:

| Opção | Função |
|---|---|
| `--job-text`, `--job-file`, `--job-image` | Origem exclusiva da vaga. |
| `--resume-file PATH` | Currículo original alternativo para todo o fluxo. |
| `--recipient-email EMAIL` | Destinatário final salvo no manifesto; use no `apply` só quando quiser sobrescrever explicitamente o contato capturado. |
| `--review-recipient-email EMAIL` | Destinatário da revisão. |
| `--output-dir PATH` | Diretório novo da execução. |
| `--send` | Envia a cópia para revisão. |
| `--sender-email EMAIL` | Conta do Outlook. |
| `--provider PROVIDER` | Override do provider de IA do job app; quando informado, não usa fallback. |
| `--optimizer-output-name NAME` | Nome interno do PDF no optimizer. |
| `--optimizer-provider PROVIDER` | Override opcional de `--provider` no optimizer; não altera a IA do job app. |

## Integração com o optimizer

O adaptador preserva extensão e bytes da fonte em:

```text
curriculum-optimizer/input/original-curriculum.<ext>
```

E executa o equivalente a:

```bash
docker compose -f docker-compose.yml run --build --rm -T optimizer \
  generate \
  --job-file /app/input/job.txt \
  --curriculum-file /app/input/original-curriculum.<ext> \
  --role "<cargo>" \
  --output-name "<empresa-cargo>"
```

`--formats` é omitido para usar o default PDF. O adaptador exige apenas o PDF final, `input/base-curriculum.html` e `input/base-curriculum.meta.json` válidos.

## Artefatos

```text
output/<empresa>-<cargo>/
├── Currículo_Nilvan_Lopes_<Cargo>.pdf
├── application_manifest.json
├── cover_email.html
├── cover_email.md
├── email_review.json
├── email_review.md
├── job_extracted.md
├── job_structured.json
├── job_summary.md
├── match_report.md
└── recipient_verification.md
```

Não há mais `resume_optimized.md` nem `resume_optimized.html`.

O manifesto versão 2 registra caminho e SHA-256 do currículo original, do base gerado e de `base-curriculum.meta.json`, além do conteúdo dos metadados de cache. O subcomando `send` continua aceitando manifestos versão 1.

## Testes

```bash
uv run --with pytest pytest -q
```

A suíte cobre leitores de currículo, contrato Docker, proveniência, manifesto v2, envio de revisão e compatibilidade do envio final com artefatos versão 1.
