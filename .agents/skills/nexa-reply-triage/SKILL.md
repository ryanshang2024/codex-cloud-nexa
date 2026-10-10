---
name: nexa-reply-triage
description: Classify replies and create CRM tasks, elevate quotes, warranties and technical commitments to humans.
---

# nexa-reply-triage

Use the NEXA PRD V3.2 and config/hvac-qc-on.json as the source of truth.

## Mandatory rules
- Identify QC vs ON and H01-H10 profile before selecting any tool.
- Cite source URL, observed date and confidence for every nontrivial assertion.
- Keep accounts, contacts, projects and opportunities separate.
- Respect data source terms and privacy; no private-account scraping or anti-bot bypass.
- Do not send messages without human approval and verified contact basis.
- Return structured JSON with unknown values as null; never invent contacts or signals.

## Output
Provide reasoning summary, structured results, excluded leads with exclusion reason, uncertain facts requiring manual review, and next actions.
