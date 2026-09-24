# Verificación formal con Lean 4

**Qué es.** Demostrar, no probar con ejemplos: si el fichero compila, el teorema es cierto para *esos* datos.

**Cómo lo aplicamos aquí.** [`formal/lean/`](../../../formal/lean/README.md) define `Story`, `Event`, `Character` y cuatro invariantes (`temporalOrder`, `agesCoherent`, `noBilocation`, `noAfterExit`) con su teorema de corrección. [`backend/app/formal/lean_export.py`](../../../backend/app/formal/lean_export.py) genera `Story.lean` desde la cronología de la BD (nombres solo en literales escapados) y `lake build` corre como el validador `lean_chronology` en `pre_publish`: un fallo bloquea la versión y vuelve al editor con los eventos implicados. Una copia del proyecto Lean por novela para que dos ejecuciones simultáneas no se pisen.
