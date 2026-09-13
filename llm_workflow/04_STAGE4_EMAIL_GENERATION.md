# Etapa 4: Geração do E-mail de Apresentação, HTML e Auto-Revisão (Email, HTML & AI Review)

Este documento especifica a **Etapa 4** do workflow LLM: elabora um e-mail de candidatura altamente persuasivo (105 a 130 palavras), compila o `cover_email.html` com o cartão visual de assinatura e executa a auto-revisão de qualidade e fidelidade factual (Score >= 9).

---

## 🎯 Instruções de Execução

Forneça o prompt abaixo para a LLM contendo os artefatos das etapas anteriores.

---

```markdown
Você atua em duplo papel: 
1. **Redator Sênior de Cold Emails de Carreira e Apresentação Profissional**
2. **Auditor de Qualidade e Revisão Factual**

Sua missão é escrever o e-mail de apresentação para a candidatura, estruturar o HTML final com assinatura visual e, em seguida, avaliá-lo rigorosamente.

---

### REGRAS EXIGIDAS PARA O REDATOR:
1. **REDAÇÃO EM PRIMEIRA PESSOA (EU):** O e-mail DEVE ser escrito em **1ª pessoa** ("Sou desenvolvedor...", "Possuo projetos...", "Tenho prática...", "Atuei...", "Desenvolvi..."). É **estritamente proibido** referir-se ao candidato na 3ª pessoa ("Nilvan é...", "O candidato possui...").
2. **TAMANHO DO CORPO DO E-MAIL:** O corpo deve ter obrigatoriamente **entre 105 e 130 palavras**. (Contagens fora dessa faixa serão REJEITADAS).
3. **TERMOS RIGOROSAMENTE PROIBIDOS (NUNCA USAR):**
   - ❌ *"alinhamento perfeito"*
   - ❌ *"perfil ideal"*
   - ❌ *"sólida experiência"*
   - ❌ *"agregar valor"*
   - ❌ *"ansioso"* / *"ansiosa"*
   - ❌ *"ávido"* / *"ávida"*
   - ❌ *"me preparou"*
   - ❌ *"desde o primeiro dia"*
4. **ESTRUTURA DO E-MAIL:**
   - **Assunto:** Use o assunto solicitado expressamente na vaga (ex: `"Vaga DEV – Mibbers"`, `"Vaga_Estágio_Dev_FITECLabs"`). Se não houver, utilize: `Candidatura: <Cargo Limpo> - <Nome do Candidato>`
   - **Saudação:** "Olá, [Nome do Recrutador/Fundador ou Equipe da Empresa],"
   - **Introdução:** Direta, citando o cargo pretendido em 1ª pessoa e modalidade (100% Remoto).
   - **Corpo:** 2 a 3 pontos de aderência forte, conectando conquistas e tecnologias reais (React, Next.js, Node/NestJS, integrações de APIs, gateways Asaas, bancos SQL, Git) com as reais necessidades do anúncio.
   - **Fechamento / CTA:** Proposta profissional para agendamento de conversa/entrevista e menção ao anexo do currículo em PDF.
   - **Fechamento e Assinatura Visual:** O corpo do e-mail em Markdown deve encerrar-se estritamente na saudação final `Atenciosamente,`. Não inclua o bloco de texto puro da assinatura no Markdown do e-mail para evitar duplicação com o **cartão visual HTML de assinatura** (que é anexado automaticamente abaixo de `Atenciosamente,` no HTML final enviado pelo Outlook).
5. **VERACIDADE FACTUAL:** Cite apenas conquistas, linguagens ou tempo de experiência que estejam registrados no Currículo do Candidato.

---

### REGRAS DO AUDITOR (AUTO-REVISÃO):
Após redigir o e-mail, conte as palavras do corpo e aplique a avaliação:
- **Contagem Exata de Palavras:** Deve estar na faixa de 105 a 130 palavras.
- **Fidelidade Factual (0 a 10):** Há alguma promessa ou experiência não presente no currículo? (Nota esperada: 10/10)
- **Aderência à Vaga (0 a 10):** O e-mail aborda as dores centrais do anúncio? (Nota esperada: 10/10)
- **Restrições de Vocabulário:** Foi identificada alguma palavra proibida ou uso de 3ª pessoa?
- Se a nota final for inferior a 9 ou houver qualquer violação, refaça a redação imediatamente antes de fornecer a saída final.

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

Gere os artefatos abaixo:

# ARTEFATO 4A: `cover_email.md`
```markdown
**Assunto:** <Assunto do E-mail>

<Corpo do E-mail de 105 a 130 palavras encerrando em:>

Atenciosamente,
```

# ARTEFATO 4B: `cover_email.html`
```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
</head>
<body style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#111111;line-height:1.5;">
<p><Parágrafo 1 de saudação e apresentação></p>
<p><Parágrafo 2 de aderência técnica e conquistas reais></p>
<p><Parágrafo 3 de CTA e menção ao anexo PDF></p>
<p style="margin-bottom:16px;">Atenciosamente,</p>

<!-- Cartão Visual de Assinatura HTML Sem Repetição de Texto -->
<div class="nl-signature-wrap" style="width:100%; max-width:600px; font-family:Arial,Helvetica,sans-serif;">
  <table cellpadding="0" cellspacing="0" border="0" role="presentation" width="600"
         background="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/background.png"
         class="nl-signature-card"
         style="width:100%; max-width:600px; min-height:200px; border-collapse:separate; border-spacing:0; border-radius:12px; overflow:hidden; border-bottom:6px solid #d4af37; background-color:#0d0d0d; background-image:url('https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/background.png'); background-repeat:no-repeat; background-size:cover; background-position:center center;">
    <tr>
      <td valign="top" class="nl-signature-pad" style="padding:15px 30px 18px 18px;">
        <table cellpadding="0" cellspacing="0" border="0" role="presentation" width="100%" style="width:100%; border-collapse:collapse;">
          <tr>
            <td valign="middle" width="58%" style="width:58%; padding-right:12px;">
              <img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/nilvan-lopes.png" width="229" height="61" alt="Nilvan Lopes" class="nl-signature-name" style="display:block; width:229px; max-width:100%; height:auto; border:0; outline:none;">
              <table cellpadding="0" cellspacing="0" border="0" role="presentation" style="margin-top:8px;">
                <tr>
                  <td style="padding:0 0 5px 0; font-size:12.5px; line-height:14px; color:#ffffff; opacity:0.90;">
                    <span style="color:#d4af37; font-weight:700;">T:</span>
                    <a href="tel:+5563992230471" style="color:#ffffff; text-decoration:none;">+55 (63) 99223-0471</a>
                  </td>
                </tr>
                <tr>
                  <td style="padding:0 0 5px 0; font-size:12.5px; line-height:14px; color:#ffffff; opacity:0.90;">
                    <span style="color:#d4af37; font-weight:700;">E:</span>
                    <a href="mailto:nilvanlopes@outlook.com" style="color:#ffffff; text-decoration:none;">nilvanlopes@outlook.com</a>
                  </td>
                </tr>
              </table>
            </td>
            <td valign="middle" width="42%" style="width:42%; text-align:right;">
              <table cellpadding="0" cellspacing="0" border="0" role="presentation" style="display:inline-table; margin-left:auto; border-collapse:collapse;">
                <tr>
                  <td align="right" style="padding-bottom:10px; line-height:0; font-size:0;">
                    <img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/eu.png" width="84" height="84" alt="Foto" class="nl-signature-photo" style="display:block; width:84px; height:84px; border-radius:999px; border:3px solid #d4af37; background:#111; margin-left:auto;">
                  </td>
                </tr>
                <tr>
                  <td align="right" class="nl-signature-icons" style="padding-top:12px; line-height:0; font-size:0;">
                    <a href="https://www.linkedin.com/in/nilvanlopes" target="_blank" style="text-decoration:none; margin-left:10px; display:inline-block;"><img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/linkedin.png" width="18" height="18" alt="LinkedIn" style="display:block; border:0;"></a>
                    <a href="https://github.com/nilvanlopes" target="_blank" style="text-decoration:none; margin-left:10px; display:inline-block;"><img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/github.png" width="18" height="18" alt="GitHub" style="display:block; border:0;"></a>
                    <a href="https://wa.me/5563992230471" target="_blank" style="text-decoration:none; margin-left:10px; display:inline-block;"><img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/whatsapp.png" width="18" height="18" alt="WhatsApp" style="display:block; border:0;"></a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</div>
</body>
</html>
```

# ARTEFATO 4C: `email_review.md`
```markdown
# Relatório de Revisão do E-mail (AI Review)

- **Contagem de Palavras no Corpo:** <Número exato> palavras (critério exigido: 105 a 130 palavras -> **APROVADO**)
- **Verificação de Fidelidade Factual (0 a 10):** 10/10 (Todas as competências citadas constam no perfil do candidato)
- **Verificação de Aderência à Vaga (0 a 10):** 10/10 (Foco direto nos requisitos técnicos e operacionais do anúncio)
- **Ausência de Termos Proibidos:** PASS (Nenhum termo proibido foi utilizado)
- **Tom e Pessoa Gramatical:** PASS (Redação em 1ª pessoa, gênero masculino)
- **Aprovação Final:** **APROVADO (Nota 10/10)**
- **Parecer:** <Breve parecer de qualidade e persuasão do e-mail>
```
```

---

## 💻 Comandos CLI para Geração e Envio de E-mail

### 1. Geração de Candidatura Completa (CLI):
```bash
uv run job-application-automation apply \
  --job-file <caminho/vaga.txt> \
  --output-dir output/<empresa>-<cargo>
```

### 2. Disparo do E-mail Gerado (Fase 1 - Teste/Revisão):
```bash
uv run job-application-automation send \
  --output-dir output/<empresa>-<cargo> \
  --recipient-email pyuloko7@gmail.com
```

### 3. Disparo Oficial (Fase 2 - Após Aprovação):
```bash
uv run job-application-automation send \
  --output-dir output/<empresa>-<cargo> \
  --recipient-email <email-oficial-da-vaga>
```
