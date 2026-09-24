# L04 — caso real: qué atrapó Lean y qué no

> Registro (spec 004, D10; spec 012, AC 5; iteración de tuning 1, 2026-09-24). Experimento
> con el brief [`b4-temporal`](../../evals/briefs/b4-temporal.json), Haiku 4.5 en todos los
> roles. Script: [`evals/experiments/l04_b4_bypass.py`](../../evals/experiments/l04_b4_bypass.py);
> datos crudos: [`evals/experiments/l04-b4-bypass.json`](../../evals/experiments/l04-b4-bypass.json).

## Por qué hizo falta un experimento

En el pipeline, la cronología del plan pasa por `chronology_problems` **antes** de
escribir (spec 007): si el planner copia una trampa del brief a la cronología, se replanea
y la trampa nunca llega a la prosa. Así ocurrió en el eval `after` de `b4`: el primer plan
situaba a Trueno en la boda de 2008 tras morir en 2005 (`noAfterExit`), el segundo lo
arregló ("homenaje simbólico a Trueno") y la novela siguió. Eso prueba que el chequeo
funciona, pero no permite comparar con los demás validadores sobre el **mismo texto**.

El experimento (solo en `evals/experiments/`, nunca en el pipeline):

1. una llamada al planner, con los mismos arreglos deterministas que `plan_novel`
   (`_repair_plan`, `normalise_events`) y **sin** el prechequeo de cronología ni replan;
2. exporta la cronología y ejecuta `verify_chronology` (Lean 4) y `diagnose`;
3. guarda ese plan y ejecuta el pipeline real con `MAX_REPAIR_ROUNDS = 0` (parcheado en el
   script) para que todos los validadores juzguen el primer borrador: 3 capítulos,
   22 llamadas, 1,29 USD.

## Resultado

**Plan (intento 1).** Lean: `noAfterExit` falla y los otros tres invariantes se
demuestran. `diagnose`: "El evento e3 del capítulo 2 (2008-09-13) hace aparecer a Trueno,
que ya había salido de la historia (death) el 2005-11-03 en e2 (capítulo 2)". El chequeo
programático del plan (`check_plan`) no encontró nada.

**Novela escrita sobre ese plan.** Los capítulos 1, 2 y 3 cuentan a Trueno llevando los
anillos en la boda de 2008 (cap. 2: "Trueno aún vivo entonces… los anillos pendían atados
a su collar"), y el capítulo 2 cuenta también su muerte en 2005.

| Validador | Punto | ¿Vio la contradicción de Trueno? |
|---|---|---|
| `lean_chronology` | `pre_publish` (y ya en el plan) | **Sí**: `noAfterExit`, con evento, fecha y capítulo |
| `judge_novel` | `pre_publish` | **Sí**: `continuidad` 2/5, bloqueante `alta` "Trueno aparece en la boda de 2008 a pesar de haber muerto en 2005", citando el cap. 3 |
| `judge_chapter` | `chapter_close` | **No**: aprobó el cap. 1 (media 5,00), el cap. 2 (3,75, el que cuenta muerte y boda) y el cap. 3 (4,50). En el cap. 2 suspendió dos veces, pero por la **edad** de la carrera (1990 / "catorce años" frente a "con 10 años" del brief) |
| `brief_coverage`, `exact_names`, `chapter_length`, `prose_repetition`, `forbidden_words_*`, `no_placeholders` | varios | No (no miran la cronología) |

## Lectura honesta

- **No es un caso que "solo Lean" viera.** `judge_novel` también lo detectó en
  `pre_publish`, sobre los resúmenes y el final. Lo que ningún otro validador hizo es
  verlo **a nivel de capítulo** (`judge_chapter` aprobó el capítulo que cuenta la muerte y
  la boda) y **antes de escribir**: en el pipeline real el prechequeo del plan lo detiene
  con coste de una llamada al planner (~0,12 USD) en lugar de una novela (~1,3 USD), de
  forma determinista y con el evento exacto, mientras que el juez es estocástico (en el run
  `before` de `ejemplo` suspendió por contradicciones que no pudo citar).
- **Lo que Lean no vio.** La trampa de la edad ("con 10 años" en 1994, nacido en 1980) no
  llega a Lean porque `normalise_events` recalcula las edades declaradas desde la fecha de
  nacimiento: la vio `judge_chapter`. La bilocación del 18-07-2015 la resuelve
  `normalise_events` moviendo el concierto al día siguiente. Julia, que "se mudó a Canadá
  en 2010 y no ha vuelto", aparece en la barbacoa de 2015: el planner no creó un evento
  `departure`, así que Lean no tenía nada que comprobar, y **ningún validador** lo señaló
  (tampoco el juez). Lean solo prueba lo que el planner pone en la cronología.
- **Falso positivo corregido en esta iteración.** En el eval `before`, el prechequeo
  paraba `b4` porque el espejo en Python marcaba como salidos a **todos** los participantes
  de una muerte (Andrés, que entierra a Trueno), mientras Lean solo al primero; y ambos
  ordenaban por `seq` (orden del relato) y no por fecha de la historia. Ahora los dos usan
  el eje de la historia (ver [`formal/lean/README.md`](../../formal/lean/README.md)).

Conclusión para L04: Lean atrapó una incoherencia real que `judge_chapter` y todos los
validadores programáticos dejaron pasar; `judge_novel` coincidió con él en la novela
completa. Su valor diferencial es ser determinista, localizar el evento y actuar antes de
gastar la escritura.
