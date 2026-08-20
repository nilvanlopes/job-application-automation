---
name: outlook-email-reply
description: Automação de respostas (Reply) e rascunhos de e-mail encadeados via Outlook Classic com assinatura visual HTML completa.
---

# Workflow de Resposta de E-mail (Outlook Email Reply)

Este skill define o padrão de execução para quando o usuário solicitar uma **resposta rápida**, **confirmação de entrevista** ou **acompanhamento (follow-up)** para qualquer e-mail recebido no Outlook, mantendo a conversa encadeada (thread oficial) e anexando a assinatura visual HTML completa sem distorções.

---

## 🛠️ Ferramenta Principal

A automação é executada através do script:
* **Script:** `scripts/reply_email.py`
* **Arquivo de Mensagem Padrão:** `reply.md`

---

## 📋 Modos de Uso e Comandos

### 1. Envio Direto via Arquivo Markdown (Recomendado)
Quando o usuário quiser enviar um texto personalizado (ex: confirmação de entrevista, agradecimento ou resposta a recrutador):
1. Escrever o conteúdo do e-mail no arquivo `reply.md`.
2. Executar o disparo automático:
   ```bash
   uv run python scripts/reply_email.py --search "<TermoDeBusca>" --body-file reply.md --send
   ```

### 2. Geração de Rascunho para Revisão (Draft Mode)
Para gerar o e-mail na thread, salvar nos *Rascunhos* e abrir a janela no Outlook para conferência visual:
```bash
uv run python scripts/reply_email.py --search "<TermoDeBusca>" --body-file reply.md
```

### 3. Envio Direto por Linha de Comando (Inline Text)
Para respostas curtas e rápidas:
```bash
uv run python scripts/reply_email.py --search "<TermoDeBusca>" --body "Olá! Confirmo o recebimento e o interesse. Fico à disposição!" --send
```

---

## 🔍 Parâmetros do Script (`scripts/reply_email.py`)

| Parâmetro | Descrição | Padrão |
| :--- | :--- | :--- |
| `--search` | Termo para localizar o e-mail na Caixa de Entrada (empresa, remetente ou assunto). | `"Colab"` |
| `--body` | Texto direto do corpo da resposta. | Texto padrão de entrevista |
| `--body-file` | Caminho para arquivo de texto/markdown com o corpo da mensagem. | `None` |
| `--recipient` | Força um e-mail de destinatário específico se necessário. | E-mail do remetente original |
| `--send` | Dispara o envio imediato e sincroniza com o servidor de e-mail. | Desativado (Salva Rascunho) |
| `--display` | Abre a janela do rascunho na tela do Outlook quando `--send` não estiver ativo. | `True` |

---

## ⚡ Regras de Execução para o Agente

1. **Identificação da Vaga/Recrutador:** Quando o usuário pedir para responder a um e-mail (ex: *"responda o e-mail da Empresa X confirmando o agendamento da entrevista"*):
   - Redigir o texto profissional em 1ª pessoa no arquivo `reply.md`.
   - Executar o comando apontando para `--search "<Empresa ou Remetente>"`.
2. **Preservação Visual da Assinatura:** O script injeta automaticamente o cartão HTML com foto, fundo geométrico dourado, contatos e redes sociais acima do histórico original da conversa.
3. **Confirmação:** Validar a saída do script (`CONFIRMED_IN_SENT_ITEMS` para envios ou `SAVED_DRAFT_SUCCESS` para rascunhos) e informar o status ao usuário.
