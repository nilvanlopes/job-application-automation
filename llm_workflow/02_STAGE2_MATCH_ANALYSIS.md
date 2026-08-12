# Etapa 2: Análise de Aderência e Relatório de Match (Profile Match & Gap Analysis)

Este prompt executa a **Etapa 2** do workflow LLM: cruza os dados extraídos da vaga com o currículo do candidato para gerar um relatório detalhado de correspondência (`match_report.md`).

---

## 🎯 Instruções de Execução

Forneça o prompt abaixo para a LLM, incluindo o JSON gerado na Etapa 1 e o Currículo Base do Candidato.

---

```markdown
Você é um especialista em recrutamento técnico e inteligência de talentos. Sua tarefa é analisar o alinhamento entre o Currículo do Candidato e o JSON da Vaga Fornecida, gerando um Relatório de Aderência (Match Report) detalhado.

### DIRETRIZES DA ANÁLISE:
1. **Mapeamento Direto:** Relacione cada requisito técnico ou comportamental exigido na vaga com experiências, projetos, ferramentas ou conquistas reais presentes no currículo.
2. **Equivalência Técnica:** Se o candidato possui uma tecnologia similar (ex: PostgreSQL vs. MySQL, React vs. Vue), registre como correspondência aproximada.
3. **Identificação de Lacunas (Gaps):** Mencione honestamente requisitos ou ferramentas da vaga que **não constam** no currículo do candidato.
4. **Palavras-Chave de Impacto:** Liste os termos técnicos e competências prioritárias da vaga que devem ser enfatizados na etapa de otimização do currículo e no e-mail.
5. **Redação em Primeira Pessoa (EU):** Ao descrever as evidências e experiências, use sempre a **1ª pessoa** ("Sou acadêmico...", "Possuo projetos...", "Tenho prática..."). É **proibido** referir-se ao candidato na 3ª pessoa ("Nilvan possui...", "O candidato tem...").

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

## 📌 Resumo da Candidatura
- **Cargo Alvo:** <Cargo Limpo Extraído>
- **Empresa:** <Nome da Empresa ou Não informada>
- **Nível de Aderência Estimado:** <Ex: High (85%) / Medium (70%)>

## 🎯 Correspondências Diretas (Pontos Fortes)
| Requisito / Exigência da Vaga | Evidência / Experiência no Currículo | Tipo de Match |
| :--- | :--- | :--- |
| <Requisito 1> | <Experiência real do candidato> | Direto |
| <Requisito 2> | <Conquista / Projeto real> | Equivalente |

## ⚠️ Lacunas e Competências Ausentes (Gaps)
- **<Competência Ausente 1>:** <Observação sobre impacto ou estratégia de mitigação sem falsificar dados>
- **<Competência Ausente 2>:** <Observação>

## 🔑 Palavras-Chave Prioritárias para Destaque
- `<Palavra-chave 1>`
- `<Palavra-chave 2>`
- `<Palavra-chave 3>`
```
