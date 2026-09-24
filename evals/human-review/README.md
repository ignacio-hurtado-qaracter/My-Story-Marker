# Revisión humana de una novela completa

Segundo validador semántico del examen (§ 5b): una persona lee **una novela completa** y la
puntúa con **la misma rúbrica** que el juez LLM, para comparar el juicio humano con el del
modelo. La comparación es la señal de calibración del juez
([`docs/verification.md`](../../docs/verification.md#llm-as-judge-and-human-review--i),
spec [011](../../specs/011-judge-human-review/011-judge-human-review.md)).

## Ficheros

| Fichero | Qué es |
|---|---|
| [`rubrica.md`](./rubrica.md) | La rúbrica en español: criterios, anclas 1–5, regla de aprobado y defectos bloqueantes. Generada desde `backend/app/judge/rubric.py` (única definición, la misma que lee el juez). |
| [`review-template.yaml`](./review-template.yaml) | Plantilla en blanco para 10 capítulos y la novela. Cópiala antes de rellenarla. |
| [`compare.py`](./compare.py) | Compara la revisión rellenada con los resultados del juez en `HARNESS_DB` y escribe `comparison-<novela>.md`. |

## Protocolo

1. **Elige la novela y la versión** publicadas que vas a revisar (`novel_id`, `version`).
   Ábrela en el lector web o en el PDF exportado.
2. **Copia la plantilla**: `cp review-template.yaml review-<novel_id>.yaml`, y rellena
   `novel_id`, `version`, `reviewer` y `date`. Si la novela no tiene 10 capítulos, borra o
   añade entradas en `chapters`.
3. **No mires las notas del juez** antes de terminar: la comparación solo vale si la revisión
   es independiente.
4. **Lee la novela entera, en orden**. Al acabar cada capítulo, puntúa sus cuatro criterios
   (`continuidad`, `tono`, `calidad_narrativa`, `personalizacion_natural`) de 1 a 5 según las
   anclas de `rubrica.md`, con una justificación de 1 a 3 frases que cite el texto. Anota en
   `blocking_issues` cualquier defecto bloqueante.
5. **Al terminar la novela**, puntúa el bloque `novel` con los mismos criterios más
   `final_satisfactorio`, y lista en `contradicciones` las contradicciones entre capítulos
   ("cap. 3 dice X; cap. 7 dice Y").
6. **Compara** con el juez:

   ```bash
   cd backend
   uv run python ../evals/human-review/compare.py ../evals/human-review/review-<novel_id>.yaml
   # opciones: --db RUTA (por defecto HARNESS_DB), --novel-id, --version, --out-dir
   ```

   Escribe `evals/human-review/comparison-<novel_id>.md` con: el error absoluto medio (MAE)
   por criterio, si el veredicto (regla D11) de humano y juez coincide por capítulo y para la
   novela, y el detalle por capítulo y criterio (diferencia = humano − LLM).
7. **Interpreta**: un MAE por criterio mayor que 1, o veredictos que no coinciden, indican que
   el juez está mal calibrado en ese criterio. Anótalo en el registro de iteraciones
   (`docs/process/`) y ajusta `backend/app/prompts/judge_chapter.md` o la rúbrica (cambiar la
   rúbrica o la regla de aprobado es un cambio de la spec 011).

## Cómo lee el script las notas del juez

El validador `judge_chapter` (en `chapter_close`) y `judge_novel` (en `pre_publish`) guardan
cada criterio como una línea de evidencia `"<criterio>: <n>/5 — <justificación>"` en la tabla
`validator_result`. El script toma el último resultado por capítulo (tras reintentos, el que
cuenta) y el último de la novela.
