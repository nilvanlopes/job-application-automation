# Job Application Automation

Orquestrador Python que transforma uma vaga em uma candidatura personalizada. O projeto recebe texto ou imagem, extrai e estrutura a vaga com Ollama local, gera o e-mail, solicita ao `curriculum-optimizer` um currículo específico em PDF e, opcionalmente, envia tudo pelo Outlook Classic primeiro para revisão.

## Funcionamento atual

```text
texto | arquivo | imagem
          |
          v
 RapidOCR + ONNX, se imagem
          |
          v
 saneamento do texto extraído
          |
          v
 gera profile/candidate.json a partir do currículo padrão
          |
          v
 estruturação da vaga por IA via Ollama local
          |
          +----> profile/candidate.json
          +----> currículo base do Obsidian ou --resume-file
          |
          v
complemento do assunto e corpo do e-mail via Ollama local
 assunto final: Candidatura - <texto gerado pela IA>
          |
          v
revisão automática do e-mail via Ollama local
 reprovado: regenera com feedback; aprovado: segue fluxo
          |
          v
 curriculum-optimizer em Docker
          |
          v
 Markdown + HTML + PDF personalizados
          |
          v
 artefatos locais e, com --send, Outlook Classic COM para revisão
```

### Regras do fluxo

- Exatamente uma entrada deve ser fornecida: `--job-text`, `--job-file` ou `--job-image`.
- Imagens são processadas pelo RapidOCR com modelos ONNX instalados pelo próprio projeto. A LLM não recebe nem analisa a imagem.
- O texto resultante, inclusive quando fornecido diretamente, passa por uma chamada de IA com schema JSON estrito para preencher os dados relevantes da vaga.
- Antes da estruturação da vaga, o fluxo gera `profile/candidate.json` a partir do currículo padrão usando IA.
- O perfil do candidato é lido desse JSON gerado e a assinatura deixa de depender de valores hardcoded.
- O currículo padrão é `/mnt/c/Users/pyu/OneDrive/Documentos/Obsidian/dev/Curriculo.md`.
- `--resume-file` substitui o currículo padrão para aquela execução.
- `--recipient-email` define o destinatário final da vaga. Ele é salvo nos artefatos, mas não recebe o e-mail de revisão.
- O destinatário de revisão padrão é `pyuloko7@gmail.com`, configurável por `JOB_APPLICATION_REVIEW_EMAIL` ou `--review-recipient-email`.
- A estruturação da vaga, o assunto, o corpo do e-mail e a revisão automática usam Ollama local com JSON estruturado.
- O fluxo tenta subir o Ollama automaticamente quando o endpoint local não está disponível e o derruba ao final da execução, sem interferir se ele já estiver rodando.
- Por padrão, ele prefere o stack compartilhado em `/home/pyu/docker/ollama/docker-compose.yml` quando esse caminho existe, para reaproveitar o mesmo volume de modelos.
- O assunto final sempre começa com `Candidatura - `; o complemento do assunto e o corpo usam o perfil, o currículo base e a vaga já estruturada como contexto.
- A IA gera o corpo completo do e-mail em um único campo, incluindo saudação e todos os parágrafos; o script não escreve, concatena, reescreve nem corrige a prosa. Quando a revisão reprova, a IA recebe feedback e gera uma nova versão completa.
- A revisão automática também verifica coesão, repetição entre parágrafos e concordância com o gênero gramatical explícito do candidato. Ela aprova somente e-mails sem problemas bloqueantes e com score mínimo de 9.
- O PDF anexado é exatamente o PDF produzido pelo `curriculum-optimizer`.
- O envio de revisão só ocorre quando `--send` é informado.
- O envio final para a empresa é feito depois, pelo subcomando `send`, reutilizando os artefatos já revisados sem chamar IA ou optimizer novamente.
- `send --output-dir` bloqueia artefatos antigos ou reprovados que não tenham `email_review_approved: true` no manifesto.
- SMTP, Microsoft Graph e envio via navegador não fazem parte do projeto atual.

## Pré-requisitos

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- Docker com Compose
- `curriculum-optimizer` em `/home/pyu/docker/curriculum-optimizer`
- Serviço local `ollama` disponível em `http://localhost:11434`
- Modelos `qwen2.5:7b`, `qwen3.5:9b` e `qwen2.5:14b-instruct-q3_K_M` baixados no Ollama
- Outlook Classic configurado no Windows, apenas para `apply --send` e `send`
- O OCR não exige Tesseract, PowerShell, serviços externos ou outro programa instalado no host.
- Os modelos do RapidOCR e o ONNX Runtime são instalados por `uv sync`.

Instale o projeto localmente:

```bash
uv sync
```

Variáveis úteis em `.env` ou no ambiente:

```bash
OUTLOOK_COM_SENDER_EMAIL="nilvanlopes@outlook.com"
JOB_APPLICATION_REVIEW_EMAIL="pyuloko7@gmail.com"
JOB_APPLICATION_DEFAULT_RESUME="/caminho/curriculo.md"
JOB_APPLICATION_OPTIMIZER_ROOT="/caminho/curriculum-optimizer"
JOB_APPLICATION_OPTIMIZER_TEMPLATE="/caminho/curriculum-optimizer/src/templates/base-curriculum.html"
JOB_APPLICATION_OLLAMA_BASE_URL="http://localhost:11434/api"
JOB_APPLICATION_OLLAMA_MODEL="qwen2.5:7b"
JOB_APPLICATION_OLLAMA_EMAIL_ANALYSIS_MODEL="qwen3.5:9b"
JOB_APPLICATION_OLLAMA_EMAIL_MODEL="qwen2.5:14b-instruct-q3_K_M"
JOB_APPLICATION_OLLAMA_COMPOSE_FILE="/home/pyu/docker/job-application-automation/docker-compose.ollama.yml"
JOB_APPLICATION_OLLAMA_VOLUME="ollama_ollama-data"
JOB_APPLICATION_OLLAMA_MANAGE_SERVICE="true"
JOB_APPLICATION_OLLAMA_SHUTDOWN_WHEN_DONE="true"
JOB_APPLICATION_OLLAMA_STARTUP_TIMEOUT_SECONDS="180"
JOB_APPLICATION_OLLAMA_POLL_INTERVAL_SECONDS="2"
AI_PROVIDER="lmstudio"
LMSTUDIO_BASE_URL="http://host.docker.internal:11434/v1"
LMSTUDIO_MODEL="qwen2.5:7b"
LMSTUDIO_API_KEY="ollama"
```

O modelo padrão `qwen2.5:7b` também faz a revisão estruturada do e-mail. O mapeamento semântico de aderências usa `qwen3.5:9b`, e `qwen2.5:14b-instruct-q3_K_M` escreve o texto final.

### Subir o Ollama local

```bash
docker compose -f docker-compose.ollama.yml up -d
docker compose -f docker-compose.ollama.yml exec ollama ollama pull qwen2.5:7b
docker compose -f docker-compose.ollama.yml exec ollama ollama pull qwen3.5:9b
docker compose -f docker-compose.ollama.yml exec ollama ollama pull qwen2.5:14b-instruct-q3_K_M
curl http://localhost:11434/api/tags
```

Se `JOB_APPLICATION_OLLAMA_MANAGE_SERVICE=true`, o próprio fluxo faz esse controle automaticamente:

- Se `http://localhost:11434/api/tags` responder, ele reutiliza o Ollama já ativo.
- Se o endpoint não responder, ele executa `docker compose -f <compose-file> up -d ollama`.
- Se algum modelo configurado não existir, ele executa `docker compose -f <compose-file> exec -T ollama ollama pull <model>`.
- No fim da execução, se o container tiver sido iniciado pelo fluxo, ele executa `docker compose -f <compose-file> down`.

## Uso do CLI

Após `uv sync`, use o comando instalado:

```bash
uv run job-application-automation --help
```

Também é possível executar o módulo diretamente:

```bash
PYTHONPATH=src uv run python -m job_application_automation --help
```

### Entrada por texto

```bash
uv run job-application-automation \
  --job-text "Vaga para Desenvolvedor Python. Enviar currículo para vagas@empresa.com"
```

### Entrada por arquivo

```bash
uv run job-application-automation --job-file input/vaga.txt
```

### Entrada por imagem

```bash
uv run job-application-automation --job-image input/vaga.png
```

Nesse caso, o projeto carrega o RapidOCR e seus modelos ONNX diretamente do ambiente Python gerenciado pelo `uv`. O texto extraído segue para a etapa de estruturação por IA.

### Currículo ou destinatário explícitos

```bash
uv run job-application-automation \
  --job-file input/vaga.txt \
  --resume-file input/curriculo-alternativo.md \
  --recipient-email recrutamento@empresa.com
```

### Envio para revisão

```bash
uv run job-application-automation apply \
  --job-file input/vaga.txt \
  --recipient-email recrutamento@empresa.com \
  --send
```

Esse comando gera e revisa o e-mail com IA, salva todos os artefatos, salva o e-mail final da vaga como destinatário final e envia uma cópia para revisão humana em `pyuloko7@gmail.com`.

### Envio final aprovado

```bash
uv run job-application-automation send \
  --output-dir output/opecsis-escritorio-contabil-inteligente-programador-php-laravel/
```

O envio final usa `application_manifest.json`, `cover_email.html` e o PDF salvo no diretório. O manifesto precisa ter revisão automática aprovada. Se o e-mail final não estiver nos artefatos, informe `--recipient-email`.

### Opções

| Opção | Função |
|---|---|
| `apply` | Subcomando para gerar candidatura. A forma antiga sem subcomando continua funcionando como `apply`. |
| `send` | Subcomando para enviar artefatos existentes sem regenerar candidatura. |
| `--job-text TEXT` | Usa o texto informado como vaga. |
| `--job-file PATH` | Lê a vaga de um arquivo UTF-8. |
| `--job-image PATH` | Executa OCR local sobre uma imagem. |
| `--recipient-email EMAIL` | No `apply`, define o destinatário final salvo nos artefatos. No `send`, sobrescreve o destinatário final. |
| `--review-recipient-email EMAIL` | Destinatário da revisão no `apply --send`; padrão `JOB_APPLICATION_REVIEW_EMAIL` ou `pyuloko7@gmail.com`. |
| `--resume-file PATH` | Usa outro currículo base. |
| `--output-dir PATH` | Define o diretório exato da execução. Deve ainda não existir. |
| `--send` | No `apply`, envia a candidatura gerada para revisão. |
| `--sender-email EMAIL` | Define a conta remetente do Outlook. |
| `--optimizer-output-name NAME` | Define o nome interno da saída no optimizer. |

## Organização das saídas

Sem `--output-dir`, a pasta padrão é:

```text
output/<empresa>-<cargo>/
```

Se ela já existir, o nome recebe um timestamp:

```text
output/<empresa>-<cargo>-YYYYMMDD-HHMMSS/
```

Exemplo de saída:

```text
output/opecsis-escritorio-contabil-inteligente-programador-php-laravel/
├── Currículo_Nilvan_Lopes_Programador_PHP_Laravel.pdf
├── application_manifest.json
├── cover_email.html
├── cover_email.md
├── email_review.json
├── email_review.md
├── job_extracted.md
├── job_structured.json
├── job_summary.md
├── match_report.md
├── recipient_verification.md
├── resume_optimized.html
└── resume_optimized.md
```

### Significado dos artefatos

- `job_extracted.md`: texto saneado usado pelo fluxo.
- `job_structured.json`: cargo, empresa, local, contato, requisitos, diferenciais e benefícios.
- `profile/candidate.json`: perfil do candidato gerado por IA a partir do currículo padrão e sobrescrito a cada execução. A extração percorre o currículo inteiro, consolida competências em itens individuais e preserva experiências, projetos, idiomas e soft skills em campos estruturados. O campo manual `grammatical_gender` não é inferido do nome ou do currículo e é preservado entre regenerações para orientar somente a concordância do texto.
- `job_summary.md`: candidato, cargo, destinatário real/efetivo e resumo de aderência.
- `match_report.md`: requisitos atendidos, parciais e lacunas detectadas.
- `recipient_verification.md`: resultado da validação sintática e MX, quando há destinatário.
- `application_manifest.json`: assunto, destinatário de revisão, destinatário final, status da revisão automática e arquivos usados no envio aprovado.
- `cover_email.md`: assunto, corpo e assinatura em texto.
- `cover_email.html`: versão enviada pelo Outlook.
- `email_review.json`: histórico estruturado das tentativas de geração e revisão do e-mail.
- `email_review.md`: relatório legível da revisão automática.
- `resume_optimized.md` e `resume_optimized.html`: cópias das saídas do optimizer.
- `Currículo_Nilvan_Lopes_<Cargo>.pdf`: PDF original do optimizer e único anexo enviado.

## Integração com o Curriculum Optimizer

O adaptador grava temporariamente no optimizer:

```text
/home/pyu/docker/curriculum-optimizer/input/job.txt
/home/pyu/docker/curriculum-optimizer/input/base-curriculum.html
```

E executa o equivalente a:

```bash
docker compose -f docker-compose.yml run --rm optimizer \
  generate \
  --job-file /app/input/job.txt \
  --role "<cargo>" \
  --output-name "<empresa-cargo>" \
  --formats pdf,html,markdown \
  --template /app/input/base-curriculum.html
```

O fluxo injeta defaults para o provider local antes de chamar o container:

```text
AI_PROVIDER=lmstudio
LMSTUDIO_BASE_URL=http://host.docker.internal:11434/v1
LMSTUDIO_MODEL=qwen2.5:7b
LMSTUDIO_API_KEY=ollama
```

A execução usa o pipeline original do optimizer (análise, seleção, montagem iterativa e validação ATS) e só é aceita quando ele produz `output/<nome>-gupy.txt`, `.html` e `.pdf`. O `--resume-file` continua fornecendo contexto ao e-mail; o optimizer usa seu template HTML canônico.

## Organização do repositório

```text
job-application-automation/
├── profile/
│   └── candidate.json          # Perfil estruturado do candidato
├── src/job_application_automation/
│   ├── cli.py                  # Argumentos e interface de terminal
│   ├── workflow.py             # Orquestração completa
│   ├── models.py               # Perfil, vaga e modelos de saída
│   ├── ocr.py                  # RapidOCR embarcado com ONNX Runtime
│   ├── ai_job.py               # Estruturação da vaga por IA e schema estrito
│   ├── ai_email.py             # Corpo do e-mail via Ollama
│   ├── pipeline.py             # Match, assunto, HTML e relatórios
│   ├── optimizer.py            # Contrato Docker com curriculum-optimizer
│   ├── outlook_com_mailer.py   # Envio e verificação no Outlook Classic
│   ├── email_tools.py          # Validação sintática e MX
│   └── signature.py            # Assinatura textual e HTML
├── tests/                      # Testes unitários e do fluxo integrado
├── pyproject.toml
└── uv.lock
```

### Responsabilidades

- `cli.py` resolve somente entrada e opções; a lógica principal não fica nele.
- `workflow.py` define `ApplicationRequest`, executa as etapas e retorna `ApplicationResult`.
- `ocr.py` extrai texto de imagens sem depender de programas do sistema.
- `ai_job.py` interpreta o texto extraído e devolve um `JobPosting` estruturado.
- `models.py` saneia o texto e fornece o parser determinístico da vaga.
- `optimizer.py` valida o contrato externo e copia os arquivos finais.
- `outlook_com_mailer.py` envia e confirma a mensagem em Outbox/Itens Enviados.

## Uso como API Python

```python
from job_application_automation.workflow import ApplicationRequest, run_application

result = run_application(
    ApplicationRequest(
        job_text="Vaga para Desenvolvedor Python...",
        recipient_email="recrutamento@empresa.com",
        send=True,
    )
)

print(result.subject)
print(result.output_dir)
print(result.optimized_resume.pdf_path)
```

## Falhas esperadas

- Entrada ausente ou mais de uma origem: erro do `argparse`.
- Imagem inexistente, inválida ou não reconhecida pelo RapidOCR: execução interrompida com erro do OCR integrado.
- Resposta inválida ou com texto extra na estruturação da vaga por IA: a execução falha; falhas de rede, autenticação ou recusa explícita também interrompem o fluxo.
- Currículo base inexistente: execução interrompida antes das chamadas externas.
- Envio final por `send` sem destinatário salvo ou informado: execução interrompida pedindo `--recipient-email`.
- Ollama fora do ar, sem modelo baixado ou retornando JSON inválido: execução interrompida com erro explícito e resposta bruta no log.
- Optimizer ausente, com erro ou sem alguma das três saídas: execução interrompida.
- `--output-dir` já existente: execução interrompida para evitar sobrescrita.
- Verificação COM inconclusiva: não reenvie automaticamente; confira os Itens Enviados do Outlook.

## Testes

Execute:

```bash
uv run --with pytest pytest -q
```

A suíte cobre OCR embarcado, estruturação da vaga por IA, geração e revisão do e-mail, relatórios, contrato Docker, cópia do PDF do optimizer, envio de revisão, bloqueio de envio final sem revisão aprovada e organização das saídas.
