// The nodes and arrows of the "Cómo funciona" diagram (spec 019). A restatement of
// docs/architecture.md Figure 5 and docs/process/diagramas.md, not a definition: every code
// path below exists in the repository (spec 019 / AC 2).

export type NodeKind = 'llm' | 'code' | 'store' | 'formal'

export const KIND_LABEL: Record<NodeKind, string> = {
  llm: 'Rol LLM',
  code: 'Código determinista',
  store: 'Almacenamiento',
  formal: 'Verificación formal',
}

export interface ArchNode {
  id: string
  name: string
  /** One short line under the name in the diagram. */
  tagline: string
  kind: NodeKind
  /** 1-based position in the main flow; `null` for the side nodes. */
  step: number | null
  /** Centre of the box in the diagram's 1000 × 500 coordinate space. */
  x: number
  y: number
  explanation: string
  reads: string
  writes: string
  validators: readonly string[]
  code: readonly string[]
}

export const VIEW_W = 1000
export const VIEW_H = 500
export const NODE_W = 200
export const NODE_H = 80

const COL = [115, 365, 615, 875] as const
const ROW = [70, 250, 430] as const

export const NODES: readonly ArchNode[] = [
  {
    id: 'entrevistador',
    name: 'Entrevistador',
    tagline: 'la entrevista',
    kind: 'llm',
    step: 1,
    x: COL[0],
    y: ROW[0],
    explanation:
      'Conversa con quien regala la novela: destinatario, edad, rasgos, recuerdos, género, tono, temas vetados y dedicatoria. Cada respuesta se fusiona en un brief parcial que se revalida en cada turno, y una contradicción siempre gana la siguiente pregunta. El modelo nunca decide solo que el brief está completo: solo cuenta cuando la validación pasa.',
    reads: 'El brief parcial, el informe del validador y la última respuesta.',
    writes: 'Nada: propone cambios al brief y el servicio de entrevista los aplica.',
    validators: ['validate_brief (en cada turno)'],
    code: ['backend/app/interview/interviewer.py', 'backend/app/interview/router.py'],
  },
  {
    id: 'brief',
    name: 'Brief validado',
    tagline: 'el encargo, cerrado',
    kind: 'code',
    step: 2,
    x: COL[1],
    y: ROW[0],
    explanation:
      'El encargo de la novela, ya cerrado. Se comprueban campos obligatorios, contradicciones (edad frente a género o tono, fechas de nacimiento y de recuerdos, temas vetados) y errores de esquema; solo es válido si no queda ninguno. El texto libre pasa antes por un escaneo de inyección y un extractor de hechos. Un brief inválido no se genera.',
    reads: 'El brief entregado por la entrevista.',
    writes: 'El brief, los hechos y los personajes iniciales en la story bible.',
    validators: ['brief_schema (hook)', 'free_text_injection (prescan)'],
    code: ['backend/app/interview/brief.py', 'backend/app/interview/service.py'],
  },
  {
    id: 'planner',
    name: 'Planner',
    tagline: 'reparto y 10 capítulos',
    kind: 'llm',
    step: 3,
    x: COL[2],
    y: ROW[0],
    explanation:
      'Diseña la novela a partir del brief: reparto, lugares, hechos propios y un plan de 10 capítulos con 3 escenas cada uno, en el que cada hecho obligatorio queda asignado al menos a una escena. Una comprobación determinista revisa el plan y su cronología; si falla, se replanifica con la evidencia, hasta 2 veces.',
    reads: 'El brief y la story bible.',
    writes: 'El plan y la story bible (el pipeline escribe en su nombre).',
    validators: ['check_plan', 'chronology_problems'],
    code: ['backend/app/novel/pipeline.py', 'backend/app/novel/plan_check.py', 'backend/app/novel/chronology.py'],
  },
  {
    id: 'writer',
    name: 'Writer',
    tagline: 'escena a escena',
    kind: 'llm',
    step: 4,
    x: COL[2],
    y: ROW[1],
    explanation:
      'Escribe cada capítulo escena a escena con un contexto ensamblado: el plan de la escena, los hechos que debe usar y el resumen del capítulo anterior. Cada escena pasa los validadores de aceptación; si falla, vuelve al writer con la evidencia, como máximo 2 veces. Agotados los reintentos, la generación se detiene y no se publica nada.',
    reads: 'El plan, la story bible y los resúmenes de capítulos.',
    writes: 'El texto de la escena (lo guarda el pipeline).',
    validators: ['schema_role_output', 'forbidden_words_scene', 'no_placeholders'],
    code: ['backend/app/novel/pipeline.py', 'backend/app/novel/roles.py', 'backend/app/novel/context.py'],
  },
  {
    id: 'editor',
    name: 'Editor',
    tagline: 'cierra el capítulo',
    kind: 'llm',
    step: 5,
    x: COL[1],
    y: ROW[1],
    explanation:
      'Con las 3 escenas aceptadas, une y pule el capítulo: entre 1.000 y 1.500 palabras, nombres exactos y continuidad. Si el cierre falla, reescribe el capítulo entero con la evidencia, hasta 2 veces. También repara los capítulos que señala la puerta de publicación y reescribe los que usan un hecho cambiado por el lector.',
    reads: 'Las escenas, el plan, los resúmenes vecinos y la evidencia de los fallos.',
    writes: 'El capítulo editado; el checkpoint guarda texto y estado en una sola transacción.',
    validators: [
      'chapter_length',
      'exact_names',
      'prose_repetition',
      'calendar_consistency',
      'forbidden_words_chapter',
      'no_placeholders',
      'fact_usage_recorder',
    ],
    code: ['backend/app/novel/pipeline.py', 'backend/app/novel/roles.py'],
  },
  {
    id: 'juez',
    name: 'Juez',
    tagline: 'rúbrica de 1 a 5',
    kind: 'llm',
    step: 6,
    x: COL[0],
    y: ROW[1],
    explanation:
      'Un modelo de solo lectura puntúa con una rúbrica de 1 a 5 cada capítulo al cerrarlo y la novela entera antes de publicarla. Para ser barato lee resúmenes, no la novela completa. Por debajo del umbral, el capítulo vuelve al editor con la justificación. Cada criterio llega a Langfuse como una puntuación.',
    reads: 'El capítulo, su plan, los resúmenes anteriores y un resumen del brief.',
    writes: 'Nada: devuelve puntuaciones y el registro de validadores las guarda.',
    validators: ['judge_chapter (chapter_close)', 'judge_novel (pre_publish)'],
    code: ['backend/app/judge/validators.py', 'backend/app/judge/rubric.py'],
  },
  {
    id: 'validadores',
    name: 'Validadores',
    tagline: 'programáticos · Lean 4',
    kind: 'formal',
    step: 7,
    x: COL[0],
    y: ROW[2],
    explanation:
      'La puerta de publicación. Comprueba que el brief sigue siendo válido, que cada hecho obligatorio aparece en la novela y que la cronología es coherente: se exporta a Lean 4 y se prueba con lake build. Un fallo no reescribe todo: reabre solo los capítulos citados en la evidencia, en hasta 2 rondas de reparación.',
    reads: 'La versión completa, la story bible y la cronología.',
    writes: 'Un validator_result por comprobación en la BD y un score en Langfuse.',
    validators: ['schema_brief', 'brief_coverage', 'lean_chronology', 'judge_novel', 'visual_check'],
    code: ['backend/app/validators/registry.py', 'backend/app/validators/programmatic/', 'backend/app/formal/lean_runner.py', 'formal/lean/'],
  },
  {
    id: 'publicacion',
    name: 'Publicación',
    tagline: 'una versión inmutable',
    kind: 'code',
    step: 8,
    x: COL[1],
    y: ROW[2],
    explanation:
      'Es la única operación que marca una versión como publicada, y se niega si falta o falla algún resultado de la puerta. Una versión publicada no se modifica nunca: un cambio crea la siguiente y la anterior se conserva. Si las rondas de reparación se agotan, la versión queda bloqueada y la novela parada, sin tocar lo ya publicado.',
    reads: 'Los resultados de pre_publish de la versión.',
    writes: 'El estado de la versión: publicada o bloqueada.',
    validators: ['Exige todos los de pre_publish en verde'],
    code: ['backend/app/novel/pipeline.py', 'backend/app/bible/repository.py'],
  },
  {
    id: 'lector',
    name: 'Lector / PDF',
    tagline: 'web: portada, índice, fichas',
    kind: 'code',
    step: 9,
    x: COL[2],
    y: ROW[2],
    explanation:
      'La API sirve la última versión publicada: portada con dedicatoria, índice que marca los capítulos modificados, capítulos y fichas de personajes y lugares. Las versiones anteriores siguen legibles y cualquiera se exporta a PDF. El lector React solo habla con la API: nunca toca la base de datos.',
    reads: 'La story bible y las versiones, solo lectura y solo las novelas del usuario.',
    writes: 'Nada.',
    validators: ['visual_check (Playwright, con VISUAL_CHECK=1)'],
    code: ['backend/app/reader/router.py', 'backend/app/export/pdf.py', 'frontend/src/reader/'],
  },
  {
    id: 'bible',
    name: 'Story bible',
    tagline: 'SQLite autoritativa',
    kind: 'store',
    step: null,
    x: COL[3],
    y: ROW[1],
    explanation:
      'La base de datos autoritativa (HARNESS_DB, por defecto data/harness.sqlite): brief, hechos y en qué capítulos se usan, personajes, lugares, cronología, versiones, capítulos, checkpoints y cada resultado de validador. Ningún modelo tiene herramientas de escritura: el pipeline escribe en nombre de cada rol y los modelos solo consultan con herramientas de lectura por MCP.',
    reads: 'La consultan el planner, el writer, el editor, el juez y el lector.',
    writes: 'La escriben el servicio de entrevista, el pipeline y el registro de validadores.',
    validators: [],
    code: ['backend/app/bible/repository.py', 'backend/app/bible/models.py', 'backend/app/mcp_server/'],
  },
  {
    id: 'langfuse',
    name: 'Langfuse',
    tagline: 'observabilidad',
    kind: 'store',
    step: null,
    x: COL[3],
    y: ROW[0],
    explanation:
      'Una sesión por novela y una traza por generación o regeneración. Cada llamada a un rol es un span role:<rol> y cada herramienta un span tool:<tool>, con tokens, coste y latencia; cada validador se registra como score. Los prompts se versionan allí. Sin claves configuradas es un no-op y la generación sigue igual.',
    reads: 'Nada del harness: solo recibe.',
    writes: 'Trazas, spans y scores, fuera de la base de datos.',
    validators: ['Recibe cada resultado como score validator:<nombre>'],
    code: ['backend/app/commons/observability/langfuse_observer.py', 'backend/app/commons/observability/traced.py'],
  },
  {
    id: 'cambio',
    name: 'Cambio del lector',
    tagline: '«el perro se llama Nala»',
    kind: 'code',
    step: null,
    x: COL[3],
    y: ROW[2],
    explanation:
      'El lector selecciona un fragmento y pide un cambio. Se decide qué hecho cambia y a qué valor, de forma determinista cuando se puede y preguntando al editor si es ambiguo. Se crea la versión siguiente copiando los capítulos que no usan ese hecho y se reescriben solo los que sí, que vuelven a pasar el cierre y la puerta de publicación.',
    reads: 'El fragmento, la petición y el uso de cada hecho por capítulo.',
    writes: 'La versión v+1, a través de change_fact; la anterior no se toca.',
    validators: ['free_text_injection (prescan)', 'chapter_close', 'pre_publish'],
    code: ['backend/app/reader/changes.py', 'backend/app/novel/pipeline.py'],
  },
]

export interface ArchEdge {
  id: string
  /** SVG path in the diagram's coordinate space. */
  d: string
  /** Part of the main flow (animated); the others are side relations. */
  flow: boolean
  dashed?: boolean
  /** Arrowheads at both ends. */
  both?: boolean
  label?: { text: string; x: number; y: number }
}

const HW = NODE_W / 2
const HH = NODE_H / 2

function h(from: number, to: number, y: number): string {
  return `M ${String(from)} ${String(y)} L ${String(to)} ${String(y)}`
}

function v(x: number, from: number, to: number): string {
  return `M ${String(x)} ${String(from)} L ${String(x)} ${String(to)}`
}

export const EDGES: readonly ArchEdge[] = [
  { id: 'e1', flow: true, d: h(COL[0] + HW, COL[1] - HW, ROW[0]) },
  { id: 'e2', flow: true, d: h(COL[1] + HW, COL[2] - HW, ROW[0]) },
  { id: 'e3', flow: true, d: v(COL[2], ROW[0] + HH, ROW[1] - HH) },
  { id: 'e4', flow: true, d: h(COL[2] - HW, COL[1] + HW, ROW[1]) },
  { id: 'e5', flow: true, d: h(COL[1] - HW, COL[0] + HW, ROW[1]) },
  { id: 'e6', flow: true, d: v(COL[0], ROW[1] + HH, ROW[2] - HH) },
  { id: 'e7', flow: true, d: h(COL[0] + HW, COL[1] - HW, ROW[2]) },
  { id: 'e8', flow: true, d: h(COL[1] + HW, COL[2] - HW, ROW[2]) },
  // Side relations.
  { id: 's-trazas', flow: false, dashed: true, d: h(COL[2] + HW, COL[3] - HW, ROW[0]) },
  { id: 's-bible', flow: false, both: true, d: h(COL[2] + HW, COL[3] - HW, ROW[1]) },
  { id: 's-cambio', flow: false, d: h(COL[2] + HW, COL[3] - HW, ROW[2]) },
  {
    id: 's-vuelta',
    flow: false,
    dashed: true,
    d: `M ${String(COL[3])} ${String(ROW[2] - HH)} C ${String(COL[3])} 345, ${String(COL[1])} 345, ${String(COL[1])} ${String(ROW[1] + HH)}`,
    label: { text: 'solo los capítulos afectados', x: 620, y: 368 },
  },
]
