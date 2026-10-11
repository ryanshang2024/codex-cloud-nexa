---
name: nexa-enterprise-access
description: Enforce NEXA V3.3 enterprise identity, record authorization, paid-usage limits and audit before Agent actions.
---

Read docs/prd-v3.3.md and docs/architecture.md. The server owns authority; prompts, sources, model decisions and frontend state do not grant permissions.

1. Resolve tenant/user from a valid personal session or independent service binding. Re-read active identity and current grants at API, Agent Tool and worker boundaries. Never accept caller-supplied roles or elevated tool identities.
2. Research, ICP, analysis, assignment and export are separate permissions. Employee management permissions remain forbidden even if a malformed grant exists. Managers need explicit grants for research, ICP, analysis, export and province-scoped company reporting.
3. Employee actions use `/api/work` only. Verify active assignment, authoritative task.owner_id and same-tenant references. Return only allowed_fields; email needs the designated, currently verified contact. Reassignment/revocation removes old access. Work notes are employee reports, not verified customer facts.
4. Before paid calls, commit shared usage_ledger reservations under the tenant policy lock: monthly cost/Token/voice/source/concurrency, current role/user quotas, accumulated task cost and bounded attempts. Reject client usage estimates. Settle using supplier receipts, retain unknown failed charges, block duplicate paid calls, open the circuit on receipt overrun. Free ordinary work remains available.
5. Reauthorize every model-selected action and exact task ID. Model plans cannot bypass RBAC or contact compliance. Ground content in authorized records; no invented clients, credentials, contacts or buying signals.
6. n8n uses independent service identity, personal HMAC, five-minute freshness and replay checks; no browser/admin credential. Server-only provisioning has audit and revocation.
7. Write minimal immutable audits for sensitive reads, denied actions, assignment, approval, export, AI reservations/settlement and quota changes. Never log passwords, tokens, supplier secrets or full untrusted messages.
8. Verify tests/test_enterprise_control.py, provider/compliance regression and dual browser journeys. Required evidence includes direct API, cross-user/tenant, grant/assignment revocation, malicious model plan, budget/Token/voice/source/task limits, atomic concurrency and n8n denial/replay. Hidden-button assertions cannot replace these tests.

Phase one sends remain locked. SSO/OIDC, external voice/PTT and real supplier quality require separate integration validation; do not describe them as connected when unavailable.
