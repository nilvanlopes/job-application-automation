# Etapa 3: Otimização e Compilação do Currículo em PDF (Resume Adaptation & PDF Render)

Este documento especifica a **Etapa 3** do workflow LLM: adapta estrategicamente o currículo do candidato para a vaga específica, gera o `Curriculo_Otimizado.html` estilizado para A4 e compila o `Curriculo_Nilvan_Lopes_<Cargo_ou_Slug>.pdf` via Microsoft Edge Headless (PowerShell).

---

## 🎯 Instruções de Execução

Forneça o prompt abaixo para a LLM contendo o Currículo Base do Candidato, a Vaga Extraída e o Relatório de Aderência da Etapa 2.

---

```markdown
Você é um consultor especialista em otimização de currículos para sistemas ATS (Applicant Tracking Systems) e seleção técnica executiva.

Sua tarefa é reescrever e otimizar o Currículo Base do Candidato para a Vaga Alvo, utilizando o Relatório de Aderência (Match Report) como guia.

---

### REGRAS CRÍTICAS DE REESCRITA:
1. **VERACIDADE INVIOLÁVEL:** NUNCA adicione empresas onde o candidato não trabalhou, títulos de graduação fictícios, certificados não obtidos ou tecnologias com as quais ele nunca trabalhou.
2. **REDAÇÃO EM PRIMEIRA PESSOA (EU):** Toda a redação do objetivo, resumo profissional, experiências e projetos DEVE ser feita em **1ª pessoa** ("Sou desenvolvedor...", "Possuo projetos...", "Desenvolvi...", "Atuo...", "Integrei..."). É **estritamente proibido** redigir em 3ª pessoa ("Nilvan possui...", "O candidato desenvolveu...").
3. **AJUSTE DE CARGO CABEÇALHO:** Atualize o título profissional localizado logo abaixo do nome do candidato para o **Cargo Limpo Extraído** na Etapa 1.
4. **REESTRUTURAÇÃO DO RESUMO PROFISSIONAL:** Reescreva o resumo profissional em 1ª pessoa destacando imediatamente o alinhamento com a vaga (ex: tempo de atuação, principais linguagens/frameworks solicitados no anúncio, integrações de APIs e áreas de domínio).
5. **REORDENAÇÃO DE COMPETÊNCIAS:** Na seção de Habilidades/Tecnologias, posicione no topo as competências que combinam exatamente com as palavras-chave prioritárias da vaga.
6. **ENFASE EM CONQUISTAS:** Reescreva os bullet points das experiências profissionais em 1ª pessoa para destacar resultados, integrações de serviços, gateways de pagamentos, performance e uso das tecnologias requisitadas no anúncio, preservando os cargos e empresas originais.
7. **NOMENCLATURA DO PDF:** Ao exportar para PDF, utilize o padrão **`Curriculo_Nilvan_Lopes_<Cargo_ou_Slug>.pdf`** (ex: `Curriculo_Nilvan_Lopes_Desenvolvedor_Full_Stack.pdf`).

### REGRAS OBRIGATÓRIAS DE PRESERVAÇÃO DE CONTEÚDO (NÃO VIOLAR):
8. **NUNCA REMOVA SEÇÕES INTEIRAS:** Todas as seções presentes no currículo original DEVEM aparecer no currículo otimizado:
   - **Dados Pessoais:** Nome, localização, telefone, e-mail, LinkedIn e GitHub.
   - **Objetivo:** Adaptado para a vaga em 1ª pessoa.
   - **Resumo Profissional:** Reescrito em 1ª pessoa focado na vaga.
   - **Habilidades Técnicas:** Todas as habilidades do original, reordenadas com prioridade para a vaga.
   - **Experiência Profissional:** TODOS os blocos de empresas e cargos com TODOS os bullet points preservados.
   - **Projetos Pessoais e Portfólio:** Todos os projetos com links e descrições em 1ª pessoa.
   - **Outras Habilidades Técnicas:** Preservar integralmente (Python, Java, Spring, Quarkus, Docker, AWS, UNIX/Linux, Active Directory, ITIL, Google Workspace, Windows Enterprise).
   - **Formação Acadêmica:** Todas as graduações e cursos técnicos.
   - **Certificações e Cursos:** Todos os cursos e certificações com carga horária.
   - **Idiomas:** Todos os idiomas com níveis.
   - **Soft Skills:** Todas as soft skills listadas, pois são vitais para filtros ATS e avaliações de cultura.
9. **PRESERVAR TODOS OS BULLET POINTS DAS EXPERIÊNCIAS:** Cada experiência profissional deve manter a mesma quantidade de bullet points do original. Pode reformular e enriquecer, mas NUNCA omitir itens (como deploy em App Store/Play Store, integração com Asaas/WhatsApp, gerenciamento de estado com React Context, etc.).
10. **REORDENAR SIM, APAGAR NÃO:** É permitido reordenar seções estrategicamente, mas é estritamente proibido deletar qualquer seção ou dado histórico do candidato.

---

### DADOS DE ENTRADA

#### 1. CURRÍCULO BASE DO CANDIDATO:
```
[COLE AQUI O CURRÍCULO BASE DO CANDIDATO — use o conteúdo completo do arquivo curriculo_base.md]
```

#### 2. JSON DA VAGA (ETAPA 1):
```json
[COLE AQUI O JSON DA VAGA]
```

#### 3. RELATÓRIO DE ADERÊNCIA (ETAPA 2):
```markdown
[COLE AQUI O MATCH REPORT DA ETAPA 2]
```

---

### SAÍDA ESPERADA

Gere a versão Markdown (`Curriculo_Otimizado.md`) e a versão HTML com CSS para impressão (`Curriculo_Otimizado.html`).

# ARTEFATO 3A: `Curriculo_Otimizado.md`
```markdown
# [Nome do Candidato]
## [Cargo Limpo Extraído da Vaga]

[Cidade, UF] | [Telefone] | [E-mail] | [LinkedIn] | [GitHub]

---

### Objetivo
[Objetivo adaptado para a vaga em 1ª pessoa]

---

### Resumo Profissional
[Resumo profissional em 1ª pessoa altamente focado nas exigências e tecnologias da vaga]

---

### Habilidades Técnicas
- **[Categoria 1]:** [Tecnologias do original reordenadas com as da vaga no topo]
- **[Categoria 2]:** [Bancos de dados e infraestrutura]
- **[Categoria 3]:** [Ferramentas e metodologias]

---

### Experiência Profissional

#### [Empresa 1] | [Cargo]
*[Período] | [Modalidade/Local]*
- [Bullet points em 1ª pessoa preservando 100% dos tópicos do original]

#### [Empresa 2] | [Cargo]
*[Período] | [Local]*
- [Bullet points em 1ª pessoa preservando 100% dos tópicos do original]

---

### Projetos Pessoais e Portfólio
- [Todos os projetos originais mantidos com links]

---

### Outras Habilidades Técnicas
- [Todas as outras habilidades preservadas]

---

### Formação Acadêmica
- [Todas as formações acadêmicas do original]

---

### Certificações e Cursos
- [Todas as certificações do original]

---

### Idiomas
- [Todos os idiomas do original]

---

### Soft Skills
- [Todas as soft skills do original]
```
```

---

## 🖨️ Comando de Compilação do PDF Real (PowerShell / Edge Headless)

Para compilar o arquivo HTML do currículo em um PDF vetorial limpo (sem cabeçalhos/rodapés de navegador):

```powershell
powershell.exe -NoProfile -Command "
$browsers = @(
    'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    'C:\Program Files\Google\Chrome\Application\chrome.exe'
)
$browser = $null
foreach ($b in $browsers) { if (Test-Path $b) { $browser = $b; break } }
if (-not $browser) { $browser = (Get-Command msedge.exe -ErrorAction SilentlyContinue).Source }

$html = 'C:\Users\pyu\OneDrive\Documentos\Obsidian\dev\Curriculo_Otimizado.html'
$pdf = 'C:\Users\pyu\OneDrive\Documentos\Obsidian\dev\Curriculo_Nilvan_Lopes_Desenvolvedor_Full_Stack.pdf'

& $browser --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf-no-header --run-all-compositor-stages-before-draw --print-to-pdf=$pdf $html
Start-Sleep -Seconds 2
if (Test-Path $pdf) { Write-Host 'PDF_SUCCESS' }
"
```
