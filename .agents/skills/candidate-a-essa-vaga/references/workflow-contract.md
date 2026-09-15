# Contrato do workflow móvel

## Etapa 0: currículo

O currículo é sempre obtido pelo link fornecido na solicitação. Registre a URL no manifesto sem expor tokens de query. Não use `/mnt/c`, OneDrive local, Obsidian local ou `curriculo_base.md` local como fonte implícita.

## Etapa 1: vaga

Extraia somente o que estiver no anúncio: cargo limpo, empresa, modalidade, contrato, requisitos, diferenciais, responsabilidades, e-mail, telefone, assunto solicitado e instruções. Use string vazia ou lista vazia para ausência. Preserve evidências literais de cargo e empresa.

## Etapa 2: aderência

Relacione cada requisito a uma evidência do currículo. Escreva em primeira pessoa. Liste lacunas sem transformar competências correlatas em experiência inexistente.

## Etapa 3: currículo e PDF

Adapte a ordem e o destaque para a vaga, mas mantenha todas as seções, experiências, links e bullets do currículo de entrada. Gere HTML A4 e PDF real. O PDF deve ser anexável e legível antes da entrega.

## Etapa 4: mensagem

Para e-mail, gere corpo de 105 a 130 palavras, assunto literal quando solicitado, `cover_email.md`, `cover_email.html` e revisão factual. O Markdown deve terminar em `Atenciosamente,`; a assinatura visual fica somente no HTML.

Para WhatsApp, gere saudação, identificação exigida, pontos factuais de aderência, indicação do PDF e links relevantes. Não gere e-mail se a vaga indicar WhatsApp como canal principal.

## Etapa 5: entrega

Para e-mail, crie um único rascunho para o destinatário oficial, com PDF anexado, se o app conectado oferecer ação de rascunho. Nunca execute envio.

Para WhatsApp, anexe o PDF e produza texto e link `wa.me`. Nunca abra uma ação de envio.

Depois da entrega, aguarde feedback. Só `corrigir` com feedback explícito pode criar uma nova versão.

Quando todos os gates forem aprovados, execute a política de desligamento do Windows descrita no `SKILL.md`. O estado deve registrar se o desligamento foi solicitado ou se o controle do Windows não estava disponível.
