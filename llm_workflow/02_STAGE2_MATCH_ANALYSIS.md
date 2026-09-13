# Etapa 2: Análise de Aderência e Relatório de Match (Profile Match & Gap Analysis)

Este prompt executa a **Etapa 2** do workflow LLM: cruza os dados extraídos da vaga com o currículo do candidato para gerar um relatório detalhado de correspondência (`match_report.md`).

---

## 🎯 Instruções de Execução

Forneça o prompt abaixo para a LLM, incluindo o JSON gerado na Etapa 1 e o Currículo Base do Candidato.

---

```markdown
Você é um especialista em recrutamento técnico e inteligência de talentos. Sua tarefa é analisar o alinhamento entre o Currículo do Candidato e o JSON da Vaga Fornecida, gerando um Relatório de Aderência (Match Report) detalhado.

### DIRETRIZES DA ANÁLISE:
1. **Mapeamento Direto:** Relacione cada requisito técnico, diferencial ou responsabilidade da vaga com experiências, projetos, ferramentas ou conquistas reais presentes no currículo.
2. **Equivalência Técnica e Diferenciais:** Analise diferenciais como SaaS, integrações de APIs, gateways de pagamento, metodologias ágeis e atuação remota.
3. **Identificação Transparente de Lacunas (Gaps):** Mencione honestamente requisitos ou ferramentas da vaga que **não constam** expressamente no currículo do candidato e apresente a estratégia de mitigação baseada nas competências correlatas que ele possui.
4. **Palavras-Chave de Impacto:** Liste os termos técnicos e competências prioritárias da vaga que devem ser enfatizados na etapa de otimização do currículo e no e-mail.
5. **Redação em Primeira Pessoa (EU):** Ao descrever as evidências e experiências, use sempre a **1ª pessoa** ("Sou acadêmico...", "Possuo projetos...", "Tenho prática...", "Desenvolvi...", "Atuei..."). É **estritamente proibido** referir-se ao candidato na 3ª pessoa ("Nilvan possui...", "O candidato tem...").

---

### DADOS DE ENTRADA

#### 1. JSON DA VAGA (ETAPA 1):
```json
[COLE AQUI O JSON RESULTANTE DA ETAPA 1]
```

#### 2. CURRÍCULO BASE DO CANDIDATO:
```
[COLE AQUI O CURRÍCULO BASE DO CANDIDATO]
```

---

### SAÍDA ESPERADA (`match_report.md`)

Gere a resposta em Markdown formatado:

# Relatório de Aderência (Match Report)

## Visão Geral
- **Cargo Alvo:** <Cargo Limpo Extraído>
- **Empresa:** <Nome da Empresa ou Não informada>
- **Modelo de Trabalho:** <100% Remoto / Híbrido / Presencial (Contratação PJ/CLT)>
- **Percentual Estimado de Aderência:** <Ex: 95%>

## Pontos Fortes e Correspondências Diretas
- **[Requisito / Diferencial 1 da Vaga]:** <Evidência factual em 1ª pessoa no currículo do candidato>
- **[Requisito / Diferencial 2 da Vaga]:** <Evidência factual em 1ª pessoa no currículo do candidato>
- **[Requisito / Diferencial 3 da Vaga]:** <Evidência factual em 1ª pessoa no currículo do candidato>

## Lacunas / Competências Não Mencionadas
- **[Competência / Requisito Ausente]:** <Observação transparente e mitigação com habilidades reais>

## Palavras-Chave Prioritárias para Destaque
- <Palavra-chave 1>, <Palavra-chave 2>, <Palavra-chave 3>, <Palavra-chave 4>
```
