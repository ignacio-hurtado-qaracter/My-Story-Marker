# My-Story-Marker

Un *harness* de agentes que escribe novelas de ciencia ficción completas, fragmento a
fragmento, sin perder la coherencia entre la primera página y la última.

## El problema que resuelve

Si le pides a un modelo de lenguaje que escriba una novela de un tirón, a las pocas
páginas ya se ha olvidado de qué prometió la trama, qué sabe cada personaje y a qué ritmo
iba la historia. El texto suena bien párrafo a párrafo y no se sostiene como libro.

Este proyecto no intenta que un solo modelo lo recuerde todo. En su lugar, reparte el
trabajo entre tres agentes con roles cerrados y un bucle de control que decide qué ve cada
uno en cada momento. Es la misma idea que un equipo editorial: alguien planifica, alguien
escribe y alguien revisa antes de que nada entre en el manuscrito.

## Cómo funciona

```
config.json ─► Spirit Creator ─► Spirit (plan de la novela)
                                    │
              ┌─────────────────────┴──────────────────────┐
              │  Ventana de contexto del Writer            │
              │  · plan del capítulo actual y personajes   │
              │  · últimos N párrafos, literales           │
              │  · resúmenes de capítulos anteriores       │
              │  · beats pendientes                        │
              └─────────────────────┬──────────────────────┘
                                    ▼
                                 Writer ──► fragmento ──► Reviewer
                                    ▲                        │
                                    └── rechazo + motivos ◄──┤
                                                             ▼ aprobado
                                                       manuscrito
```

**Spirit Creator** planifica antes de escribir una sola frase: inventa título y premisa,
divide la novela en capítulos y cada capítulo en *beats* (los hechos que deben ocurrir), y
define el reparto con su arco. Ese documento, el **Spirit**, es la autoridad sobre lo que
la novela tiene que ser.

**Writer** escribe un fragmento de pocos párrafos a partir de una ventana de contexto
curada: nunca ve el libro entero, solo el plan del capítulo actual, los últimos párrafos
aprobados, un resumen de lo lejano y los beats que quedan por delante.

**Reviewer** decide si el fragmento entra o no. Comprueba cuatro cosas —hilo principal,
capítulo actual, personajes y ritmo— y si rechaza, devuelve motivos concretos que el Writer
recibe en el siguiente intento.

El bucle repite esto hasta cerrar cada capítulo. Si un fragmento falla demasiadas veces, se
asume que el problema es el plan y no la prosa: se descarta el capítulo, el Spirit Creator lo
replanifica y se vuelve a empezar. Si eso también se agota, la ejecución se detiene con error
en lugar de entregar un libro incoherente.

La especificación completa está en [Specs/Spec1.md](Specs/Spec1.md).

## Qué produce

Cada ejecución crea una carpeta en `books/` con el nombre de la novela:

```
books/<titulo-slug>/
  novel.md            ← la novela terminada (el entregable)
  spirit.md           ← plan: premisa, hilo principal, capítulos y beats
  characters.md       ← personajes con su estado a lo largo del libro
  manuscript/         ← un fichero por capítulo con los fragmentos aprobados
  summaries/          ← resúmenes de cada capítulo cerrado
  metrics.jsonl       ← cada veredicto del Reviewer, aprobado o no
  run.json            ← contadores, posición actual y configuración usada
  rejected/           ← fragmentos rechazados con sus motivos (opcional)
```

Todo menos `novel.md` es estado de trabajo, guardado para poder auditar o retomar una
ejecución. En `books/` hay ya varias novelas generadas que sirven de ejemplo.

## Cómo se ejecuta

El harness corre sobre [Claude Code](https://claude.com/claude-code). No hay código de
orquestación: los agentes están definidos como ficheros Markdown en
[.claude/agents/](.claude/agents/) y la sesión principal sigue el bucle de la especificación.

1. Abre el repositorio en Claude Code.
2. Ajusta [Specs/config.json](Specs/config.json): número de capítulos, párrafos por
   capítulo, idioma, tema opcional. Solo `chapters.count` es obligatorio.
3. Pide una novela: *«Escribe una novela siguiendo Specs/Spec1.md»*.

El resultado aparece en `books/<titulo>/novel.md` cuando cierra el último capítulo.

## Estructura del repositorio

| Ruta | Contenido |
|------|-----------|
| `Specs/` | Especificación, configuración de entrada y diagrama del harness |
| `.claude/agents/` | Definición de los tres agentes (system prompt, herramientas) |
| `books/` | Novelas generadas, una carpeta por ejecución |
| `web/` | Sitio estático para crear configuraciones, explorar la biblioteca de novelas y ver la arquitectura. Ver [web/README.md](web/README.md) |

## Observabilidad

Las sesiones se trazan a [Langfuse](https://langfuse.com) mediante el plugin
`langfuse-observability` de Claude Code: cada ejecución queda registrada con sus llamadas al
modelo, subagentes, herramientas, tokens y coste, lo que permite analizar dónde se gasta el
tiempo y por qué el Reviewer rechaza. Es opcional; el harness funciona igual sin él.
