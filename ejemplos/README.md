# Ejemplos

Novelas reales generadas por el sistema de principio a fin, exportadas a PDF desde el
backend. Los destinatarios son ficticios.

| Fichero | Qué es | Qué demuestra |
|---|---|---|
| [`novela-ejemplo.pdf`](./novela-ejemplo.pdf) | `novela-ejemplo-a`, versión 1: novela de **10 capítulos** (1.006–1.170 palabras cada uno, 10.645 en total) con portada y dedicatoria, índice navegable, ficha de personajes y lugares y enlaces internos | El pipeline completo con el brief del README: publicada a la primera en `pre_publish`, sin rondas de reparación, con todos los validadores en verde (`judge_novel` 0,88; `lean_chronology`, `brief_coverage`, `calendar_consistency` ✅). 55 llamadas, **3,10 USD**, ~69 min |
| [`novela-ejemplo-v2-cambio-nala.pdf`](./novela-ejemplo-v2-cambio-nala.pdf) | `novela-ejemplo-a`, versión 2, tras pedir el cambio «la perra se llama Nala» (`pet.canela.name` → `Nala`), con la página **«Novedades»** | El cambio del lector: solo se regeneran los capítulos que usan el hecho (1 y 3–10; el 2 se copia) y la versión 1 se conserva intacta («Canela» 44 veces en v1 y 0 en v2; «Nala» 0 en v1 y 45 en v2). ~27 min, ~0,94 USD |
| [`novela-infantil-3-capitulos.pdf`](./novela-infantil-3-capitulos.pdf) | `novela-infantil`: novela de **3 capítulos** para un destinatario infantil, del brief [`evals/briefs/b2-infantil.json`](../evals/briefs/b2-infantil.json) | Que el sistema funciona con otra longitud y otro público (tono infantil). Publicada v1, 20 llamadas, **0,85 USD**, ~21 min |
| [`brief-ejemplo.json`](./brief-ejemplo.json) | Copia idéntica de [`evals/briefs/ejemplo.json`](../evals/briefs/ejemplo.json) | El brief que produjo `novela-ejemplo.pdf` y su v2 |

Procedencia: `novela-ejemplo-a` se generó con el código del commit `81e1518` (iteración de
tuning 2); el cambio a v2 está en `0e8118c`. Los dos intentos anteriores con el mismo brief
se bloquearon y motivaron las iteraciones de tuning 1 y 2
([registro de iteraciones](../docs/process/iteraciones.md#iteración-de-tuning-2)).

## Cómo se reproduce

Requisitos e instalación en el [README raíz](../README.md#instalación). Desde la raíz:

```bash
cd backend

# 1. generar (si se interrumpe, el mismo comando reanuda desde el último capítulo completado)
uv run python -m app.novel.cli generate --brief ../evals/briefs/ejemplo.json --novel-id novela-ejemplo-a

# 2. estado, validadores y coste
uv run python -m app.novel.cli status --novel-id novela-ejemplo-a

# 3. exportar la versión publicada
uv run python -m app.export.cli pdf --novel-id novela-ejemplo-a --out ../ejemplos/novela-ejemplo.pdf

# 4. pedir un cambio de un hecho: crea la versión 2 y regenera solo sus capítulos
uv run python -m app.novel.cli change-fact --novel-id novela-ejemplo-a --fact pet.canela.name --value Nala
uv run python -m app.export.cli pdf --novel-id novela-ejemplo-a --version 2 --out ../ejemplos/novela-ejemplo-v2-cambio-nala.pdf
```

Sin `--novel-id`, `generate` asigna uno y lo imprime. La novela de 3 capítulos sale de
`--brief ../evals/briefs/b2-infantil.json --novel-id novela-infantil --chapters 3`. La generación es con modelo (Claude Haiku 4.5 vía la CLI
de Claude Code), así que otra ejecución da otro texto y puede no publicarse a la primera:
el intento paralelo `novela-ejemplo-b`, con el mismo código, gastó sus dos rondas de
reparación por un fallo de exportación a Lean que la prosa no puede arreglar
([detalle](../docs/process/iteraciones.md#iteración-de-tuning-2)).
