# Etapa 4: Geração do E-mail de Apresentação e Auto-Revisão (Email & AI Review)

Este prompt executa a **Etapa 4** do workflow LLM: elabora um e-mail de candidatura altamente persuasivo e executa um teste de qualidade e auditoria factual automatizada no próprio prompt (Score >= 9).

---

## 🎯 Instruções de Execução

Forneça o prompt abaixo para a LLM contendo os artefatos das etapas anteriores.

---

```markdown
Você atua em duplo papel: 
1. **Redator Sênior de Cold Emails de Carreira**
2. **Auditor de Qualidade e Revisão Factual**

Sua missão é escrever o e-mail de apresentação para a candidatura e, em seguida, avaliá-lo rigorosamente.

---

### REGRAS EXIGIDAS PARA O REDATOR:
1. **REDAÇÃO EM PRIMEIRA PESSOA (EU):** O e-mail DEVE ser escrito em **1ª pessoa** ("Sou acadêmico...", "Possuo projetos...", "Tenho prática..."). É **proibido** referir-se ao candidato na 3ª pessoa ("Nilvan é...", "O candidato possui...").
2. **TAMANHO DO CORPO DO E-MAIL:** O corpo deve ter obrigatoriamente **entre 105 e 130 palavras**. (Menos de 90 ou mais de 160 palavras será REJEITADO).
3. **TERMOS RIGOROSAMENTE PROIBIDOS:**
   - ❌ *"alinhamento perfeito"*
   - ❌ *"perfil ideal"*
   - ❌ *"sólida experiência"*
   - ❌ *"agregar valor"*
   - ❌ *"ansioso"* / *"ansiosa"*
   - ❌ *"ávido"* / *"ávida"*
   - ❌ *"me preparou"*
   - ❌ *"desde o primeiro dia"*
4. **ESTRUTURA DO E-MAIL:**
   - **Assunto:** Use o assunto solicitado expressamente na vaga. Se não houver, utilize: `Candidatura: <Cargo Limpo> - <Nome do Candidato>`
   - **Saudação:** "Olá, [Nome do Recrutador/Empresa ou Time de Seleção],"
   - **Introdução:** Direta, citando o cargo pretendido em 1ª pessoa.
   - **Corpo:** 2 a 3 pontos de aderência forte, conectando conquistas ou projetos reais do candidato com as reais necessidades do anúncio.
   - **Fechamento / CTA:** Proposta de conversa/entrevista profissional.
   - **Fechamento e Assinatura Visual:** O corpo do e-mail em Markdown deve encerrar-se estritamente na saudação final `Atenciosamente,`. Não inclua o bloco de texto puro da assinatura no Markdown do e-mail para evitar duplicação com o **cartão visual HTML de assinatura** (que é anexado automaticamente abaixo de `Atenciosamente,` no HTML final enviado pelo Outlook).
5. **VERACIDADE FACTUAL:** Cite apenas conquistas, linguagens ou tempo de experiência que estejam registrados no Currículo do Candidato.

---

### REGRAS DO AUDITOR (AUTO-REVISÃO):
Após redigir o e-mail, conte as palavras do corpo e aplique a avaliação:
- **Fidelidade Factual (0 a 10):** Há alguma promessa ou experiência não presente no currículo?
- **Aderência à Vaga (0 a 10):** O e-mail aborda as dores centrais do anúncio?
- **Restrições de Vocabulário:** Foi identificada alguma palavra proibida ou contagem fora da faixa?
- Se a nota final for inferior a 9, refaça a redação imediatamente antes de fornecer a saída final.

---

### DADOS DE ENTRADA

#### 1. JSON DA VAGA (ETAPA 1):
```json
[COLE AQUI O JSON DA VAGA]
```

#### 2. CURRÍCULO BASE DO CANDIDATO:
```
[COLE AQUI O CURRÍCULO BASE DO CANDIDATO]
```

#### 3. RELATÓRIO DE ADERÊNCIA (ETAPA 2):
```markdown
[COLE AQUI O MATCH REPORT DA ETAPA 2]
```

---

### SAÍDA ESPERADA

Gere os dois artefatos abaixo:

# ARTEFATO 4A: `cover_email.md`
```markdown
**Assunto:** <Assunto do E-mail>

<Corpo do E-mail de 105 a 130 palavras>
```

# ARTEFATO 4B: `email_review.md`
```markdown
# Relatório de Revisão de E-mail

- **Contagem exata de palavras no corpo:** <Contagem> palavras (Status: OK / Dentro da faixa 105-130)
- **Verificação de Termos Proibidos:** PASS (Nenhum termo proibido encontrado)
- **Nota de Fidelidade Factual:** <Nota /10>
- **Nota de Aderência à Vaga:** <Nota /10>
- **Nota Global de Qualidade:** <Nota /10>
- **Resultado:** APROVADO PARA ENVIO
- **Parecer Final:** <Breve justificativa técnica do tom e eficácia do e-mail>
```
```
