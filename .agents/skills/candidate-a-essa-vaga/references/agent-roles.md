# Papéis de execução

## Planejador: Luna Max

Entrada: vaga bruta, currículo completo e instruções do usuário.

Saída interna:

- matriz de fatos do currículo com evidência textual;
- dados da vaga ainda não confirmados;
- requisitos obrigatórios, diferenciais e responsabilidades;
- canal de candidatura e destinatário, somente quando declarados;
- riscos factuais e critérios de bloqueio;
- sequência dos agentes executores.

O planejador não escreve o e-mail final nem inventa respostas. Ele deve marcar dados ausentes como desconhecidos.

## Executores: Luna Medium

Execute em ordem e passe os artefatos estruturados ao papel seguinte:

1. `extractor`: produz `job_structured.json`, `job_extracted.md` e `job_summary.md`.
2. `matcher`: produz `match_report.md` em primeira pessoa e lista gaps honestos.
3. `resume-editor`: produz `Curriculo_Otimizado.md` e `Curriculo_Otimizado.html`, preservando seções e bullets.
4. `message-editor`: produz e-mail ou mensagem WhatsApp conforme o canal literal da vaga.
5. `pdf-renderer`: transforma o HTML em PDF A4 real e verifica que o arquivo abre e tem conteúdo.
6. `reviewer`: produz `email_review.md`, `email_review.json`, `recipient_verification.md` e atualiza o manifesto.

Cada executor só pode usar fatos presentes no currículo, na vaga ou nas instruções explícitas do usuário. O revisor rejeita qualquer artefato que não consiga rastrear a uma fonte.

## Fallback

Se a superfície não tiver subagentes, mantenha os mesmos papéis como passagens separadas. Cada passagem recebe apenas os artefatos necessários e deve devolver arquivos nomeados, não uma promessa textual de que os arquivos foram criados.
