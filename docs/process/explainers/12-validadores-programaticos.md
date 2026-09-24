# Validadores programáticos

**Qué es.** Comprobaciones deterministas y baratas que no necesitan modelo: si algo se puede contar, se cuenta.

**Cómo lo aplicamos aquí.** [`backend/app/validators/programmatic/`](../../../backend/app/validators/programmatic/__init__.py): `chapter_length` (1.000–1.500), `exact_names` (nombres idénticos a la bible), `brief_coverage` (cada hecho obligatorio aparece en algún capítulo, contra `fact_usage`), `schema_*`, `prose_repetition` (clichés y repeticiones), `lean_chronology`. Todos siguen el protocolo K3 ([`protocol.py`](../../../backend/app/validators/protocol.py)): nombre, punto, `ValidationResult(passed, score, evidence, explanation)`; `run_point` persiste en `validator_result` y puntúa `validator:<nombre>`. Tabla completa en [diagramas](../diagramas.md#validadores-y-punto-de-ejecución).
