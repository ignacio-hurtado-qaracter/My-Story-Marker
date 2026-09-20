El objetivo es optimizar el correctness y rendimiento de la interacción entre orquestrador y writer.

maneras de medirlo desde las trazas:
- Contexto adecuado que llega al agente y de manera estructurada (y determinista?): prompt del orquestrador¿?, main thread, current chapter, budget (paragraphs approved in this chapter, chapter target_paragraphs, beats not yet done), characters, últimos N párrafos, resumen de los últimos M capítulos, contexto futuro, rejection reasons (if any). Además, todo lo que concierna del config al writer: min-max paragraphs por fragmento, tono y estilo, language
- Sin errores de llamadas a herramientas del writer
- Tiempo de razonamiento? tokens gastados?
- Debería de ser una sola llamada del subagente writer, o debe hacer más de una? es decir, habría que restringir a solo hacer una llamada?

# Writer task: chapter {chapter_id}, fragment {fragment_index}, attempt {attempt}

## Spirit view
### Main thread
{introduction / development / resolution of the novel, verbatim from spirit.md}
### Current chapter: {id} — {title}
{introduction / development / resolution of this chapter, verbatim}
### Characters
{characters.md content, verbatim}

## Recent
{last N paragraphs of manuscript/, verbatim, N = config.context.recent_paragraphs}
{or exactly the line: (empty — this is the first fragment of the novel)}

## Distant
{summaries/chapter-NN.md of the last M closed chapters, oldest first}
{or exactly the line: (empty — no closed chapters yet)}

## Future
{ordered beats not yet done, starting with the current one, each as "- {id} (current|pending): {description}"}

## Budget
- paragraphs approved in this chapter: {n}
- chapter target_paragraphs: {t}
- beats not yet done: {k}

## Constraints
- language: {config.language}
- tone_and_style: {spirit.tone_and_style, or "(none)"}
- fragment length: {min}–{max} paragraphs

## Rejection reasons            ← only on a retry
- {reason 1}