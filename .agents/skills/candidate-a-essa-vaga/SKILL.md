---
name: candidate-a-essa-vaga
description: Execute the factual job-application workflow from Codex or ChatGPT using a vacancy and curriculum link, producing the complete PDF and message package plus one reviewable company draft without sending it.
---

# Candidatura pelo app

Use esta skill when the user invokes `$candidate-a-essa-vaga` or asks to process a job vacancy from a mobile app. The workflow is self-contained in the app: do not depend on WSL paths, Docker, local Ollama, Outlook Classic, Edge, or files that exist only on the user's computer.

## Input contract

Require both inputs before generation:

- a vacancy as pasted text, image, or URL;
- a curriculum URL supplied by the user.

Open and read the curriculum URL before writing any candidate fact. If it cannot be accessed or is not a curriculum, stop and request a new URL or an uploaded file. Do not infer facts from a URL, email domain, company name, or job title.

## Execution contract

1. Run one planning pass requesting `gpt-5.6-luna` with maximum reasoning. The planner produces a source-of-truth matrix, a clean stage plan, channel decision, and factual risks.
2. Run the stage roles in order, requesting `gpt-5.6-luna` with medium reasoning: extraction, match analysis, resume, email/WhatsApp, PDF, and final review.
3. If native subagents are available, delegate the roles. Otherwise execute the same roles as isolated sequential passes in the current app conversation. If a requested Luna model is unavailable, use the closest available model and record the requested and actual models in `application_manifest.json`.
4. Gate every stage with the rules in `references/factual-rules.md` and `references/artifact-contract.md`. Repair failed artifacts before continuing.
5. Generate the complete artifact set and attach each artifact to the conversation.
6. For email vacancies, create exactly one draft addressed to the official vacancy recipient, with the HTML body and generated PDF attached. Never invoke send. If the email app or draft action is unavailable, report that the draft was not created and still attach the files.
7. For WhatsApp vacancies, do not create an email draft. Attach the PDF, output the complete message, and create a URL-encoded `wa.me` link. Never send the WhatsApp message.
8. Do not create a replacement draft or rerun generation unless the user explicitly says the result is bad and provides feedback or invokes `corrigir`.

## User commands

- `executar`: run the full workflow once.
- `corrigir`: use the user's feedback to create the next version only when explicitly requested.
- `status`: report source access, channel, generated artifacts, validation, model fallback, and draft state from the current conversation.

Read the relevant supporting references before executing a mode:

- [agent roles](references/agent-roles.md) for planning and delegation;
- [workflow contract](references/workflow-contract.md) for the five stages and channel behavior;
- [factual rules](references/factual-rules.md) for truth, first-person text, and preservation rules;
- [artifact contract](references/artifact-contract.md) for filenames, validation, and manifest fields.

Use `scripts/validate_application.py`, `scripts/count_email_words.py`, and `scripts/build_whatsapp_link.py` when the app runtime supports skill scripts. These scripts validate or format data only; they must not send mail, access credentials, or mutate external services.
