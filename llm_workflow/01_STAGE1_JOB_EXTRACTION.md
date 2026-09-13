# Etapa 1: Extração e Estruturação da Vaga (Job Extraction & Parsing)

Este prompt executa a **Etapa 1** do workflow LLM: recebe o anúncio bruto de uma vaga (texto ou transcrição OCR de imagem/post) e extrai um objeto JSON rigorosamente higienizado e validado.

---

## 🎯 Instruções de Execução

Forneça o prompt abaixo para a LLM, preenchendo o bloco `[TEXTO BRUTO DA VAGA]`.

---

```markdown
Você é um extrator especialista em vagas de emprego em português do Brasil. Analise o anúncio da vaga fornecido abaixo, corrija eventuais ruídos evidentes de OCR e extraia os dados estruturados conforme as regras rígidas a seguir:

### REGRAS RIGOROSAS DE EXTRAÇÃO:
1. **NÃO INVENTE INFORMAÇÕES:** Use string vazia `""` ou lista vazia `[]` quando a informação não estiver presente no anúncio.
2. **CARGO LIMPO (`title`):** O campo `title` será usado diretamente como o título profissional no currículo do candidato.
   - Deve conter APENAS a denominação limpa do cargo (Exemplo correto: `"Desenvolvedor Full Stack"`, `"Desenvolvedor Backend Java"`).
   - Remova chamadas como *"Vaga para"*, *"Contrata-se"*, *"Temos vaga"*, nome da empresa, cidade, estado, modalidade (*"PJ"*, *"CLT"*, *"Remoto"*), urgência ou instruções de envio.
3. **EMPRESA (`company`):** Extraia apenas se o nome da empresa contratante ou do autor/recrutador estiver mencionado no texto.
4. **MODALIDADE E CONTRATO (`location` e `contract_type`):** Identifique se é 100% Remoto, Híbrido ou Presencial, e se a contratação é PJ, CLT ou Estágio.
5. **CONTATOS (`recipient_email` e `recipient_phone`):** Capture o e-mail de envio e/ou número de WhatsApp/telefone informado para candidatura.
6. **INSTRUÇÕES DE CANDIDATURA (`application_instructions`):** Extraia exigências específicas tais como: assunto obrigatório do e-mail, mensagem de identificação no WhatsApp (ex: `"Vaga DEV – Mibbers"`), link de portfólio/GitHub/LinkedIn exigido, formato do currículo em PDF, pretensão salarial solicitada ou perguntas específicas.
7. **EVIDÊNCIAS (`title_evidence` e `company_evidence`):** Cite os trechos exatos do texto que comprovam a extração do cargo e da empresa.

---

### ENTRADA: ANÚNCIO DA VAGA

```
[TEXTO BRUTO DA VAGA]
```

---

### SAÍDA ESPERADA

Gere a resposta contendo exclusivamente o código JSON válido no formato a seguir:

```json
{
  "title": "<Cargo Limpo Extraído>",
  "company": "<Nome da Empresa ou ''>",
  "location": "<Localização / Modalidade (ex: 100% Remoto)>",
  "contract_type": "<PJ / CLT / Estágio>",
  "required_skills": [
    "<Requisito Obrigatório 1>",
    "<Requisito Obrigatório 2>"
  ],
  "desired_skills": [
    "<Diferencial 1>",
    "<Diferencial 2>"
  ],
  "responsibilities": [
    "<Responsabilidade 1>",
    "<Responsabilidade 2>"
  ],
  "recipient_email": "<E-mail de envio capturado ou ''>",
  "recipient_phone": "<WhatsApp / Telefone capturado ou ''>",
  "requested_email_subject": "<Assunto oficial exigido pela vaga ou ''>",
  "application_instructions": [
    "<Instrução / Pergunta Obrigatória 1>",
    "<Instrução / Pergunta Obrigatória 2>"
  ],
  "title_evidence": "<Trecho literal do texto comprovando o cargo>",
  "company_evidence": "<Trecho literal do texto comprovando a empresa>"
}
```
```
