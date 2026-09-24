# Guardrails, motor de políticas y audit log

**Qué es.** Reglas que el sistema impone siempre, independientemente de lo que el modelo quiera, con cada decisión registrada para poder auditarla después.

**Cómo lo aplicamos aquí.** El motor ([`backend/app/policy/engine.py`](../../../backend/app/policy/engine.py)) decide y registra, nunca reescribe: términos prohibidos en tres niveles (global, novela, léxico) con el normalizador compartido ([`normalise.py`](../../../backend/app/policy/normalise.py)) y marcadores de inyección en texto libre. Cada decisión es una fila de `policy_decision` y un score `guardrail:*`. Reescribir es trabajo del pipeline: el acierto vuelve al escritor, acotado. Los hooks de Claude Code escriben también en `policy_decision` y en `.claude/hooks/policy-audit.log`.
