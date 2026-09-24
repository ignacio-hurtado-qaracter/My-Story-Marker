# Model checking con TLA+/TLC

**Qué es.** Describir el flujo como máquina de estados y dejar que TLC recorra **todas** las ejecuciones posibles (fallos y crashes incluidos) buscando una que viole un invariante.

**Cómo lo aplicamos aquí.** [`formal/tla/GiftNovelHarness.tla`](../../../formal/tla/README.md): plan, escenas, editor, cierre, checkpoint, pre-publicación con una ronda de reparación, publicación, `Crash`/`Resume` y un `ChangeFact`. Invariantes `NoUnvalidatedPublish`, `ResumeNoDupNoLoss`, `PreviousVersionKept`, `RetriesBounded`; vivacidad `Termination`. N = 5, 2 reintentos: ~696k estados distintos en ~1 min. Sus cuatro contraejemplos cambiaron el esquema y el pipeline ([iteraciones](../iteraciones.md#contraejemplos-de-tlc-ce1ce4)).
