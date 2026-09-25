// The progress of one generation (spec 020): phase, chapters written, cost so far, the last
// validator failures; a link to the novel once published, an explanation when it stops.
import { Link } from 'react-router'

import { readerHref } from '../reader'
import { downloadFile } from '../shared/api'
import { ErrorPanel } from '../shared/ui'
import { useGeneration, type GenerationStatus } from './api'

const money = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })

function phaseText(state: GenerationStatus): string {
  const next = Math.min(state.chapters_done + 1, state.chapters_total)
  switch (state.status) {
    case 'queued':
      return 'En cola: guardando la ficha de la novela…'
    case 'published':
      return '¡Tu novela está lista!'
    case 'blocked':
      return 'La novela se ha escrito, pero no ha superado la revisión final.'
    case 'stopped_error':
      return 'La generación se ha detenido.'
    case 'running':
      break
  }
  switch (state.phase) {
    case 'ingesting':
      return 'Guardando la ficha de la novela…'
    case 'planning':
      return 'Planificando los capítulos y la cronología…'
    case 'writing':
      return `Escribiendo el capítulo ${String(next)} de ${String(state.chapters_total)}…`
    case 'pre_publish':
      return 'Revisión final: cronología en Lean, juez y comprobaciones de publicación…'
    case 'repairing':
      return 'Reescribiendo los capítulos que la revisión final ha señalado…'
    default:
      return 'Generando…'
  }
}

function explanation(state: GenerationStatus): string {
  if (state.status === 'blocked') {
    return 'Los validadores han encontrado problemas que no se han podido reparar en las rondas permitidas. Puedes leer lo escrito y revisar los avisos de abajo.'
  }
  return 'Algo ha impedido terminar la novela. Si ya había capítulos escritos, se conservan; al relanzar la misma ficha desde la línea de comandos se reanuda en el primer capítulo pendiente.'
}

function formatTime(iso: string | null | undefined): string {
  if (iso == null) return '—'
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })
}

export function GenerationProgress({ novelId }: { novelId: string }) {
  const generation = useGeneration(novelId)
  if (generation.isPending) return <p className="nn-state">Consultando el estado de la novela…</p>
  if (generation.isError) {
    return <ErrorPanel message={generation.error.message} onRetry={() => void generation.refetch()} />
  }
  const state = generation.data
  const total = Math.max(state.chapters_total, 1)
  const finished = state.status !== 'queued' && state.status !== 'running'
  const version = state.version ?? null
  const issues = state.issues ?? []

  return (
    <section className="card nn-progress" aria-labelledby="nn-progress-title" aria-live="polite">
      <p className="eyebrow">Generación en curso</p>
      <h2 id="nn-progress-title" className="nn-progress-title">
        {phaseText(state)}
      </h2>
      <div className="nn-progress-bar">
        <label htmlFor="nn-progress-chapters">
          Capítulos escritos: {state.chapters_done} de {state.chapters_total}
        </label>
        <progress id="nn-progress-chapters" max={total} value={state.chapters_done} />
      </div>
      <dl className="nn-progress-facts">
        <div>
          <dt>Coste hasta ahora</dt>
          <dd>{money.format(state.cost_usd)}</dd>
        </div>
        <div>
          <dt>Llamadas al modelo</dt>
          <dd>{state.calls}</dd>
        </div>
        <div>
          <dt>Inicio</dt>
          <dd>{formatTime(state.started_at)}</dd>
        </div>
        <div>
          <dt>Última actualización</dt>
          <dd>{formatTime(state.updated_at)}</dd>
        </div>
      </dl>
      {finished ? null : (
        <p className="nn-hint">
          Esta página se actualiza sola cada 5 segundos. Puedes cerrarla: la novela seguirá escribiéndose y aparecerá
          en tu biblioteca.
        </p>
      )}

      {state.status === 'published' && version !== null ? (
        <div className="nn-actions">
          <Link className="nn-btn-primary" to={readerHref(novelId, version)}>
            Leer la novela
          </Link>
          <button
            type="button"
            className="btn-ghost"
            onClick={() => {
              downloadFile(
                `/api/novels/${encodeURIComponent(novelId)}/versions/${String(version)}/pdf`,
                `${novelId}-v${String(version)}.pdf`,
              ).catch(() => undefined)
            }}
          >
            Descargar PDF
          </button>
        </div>
      ) : null}

      {state.status === 'blocked' || state.status === 'stopped_error' ? (
        <div className="nn-stopped" role="status">
          <p>{explanation(state)}</p>
          {state.detail === '' ? null : <p className="nn-detail">{state.detail}</p>}
          {version !== null && state.chapters_done > 0 ? (
            <Link className="btn-ghost" to={readerHref(novelId, version, 'indice')}>
              Ver la novela parcial
            </Link>
          ) : null}
        </div>
      ) : null}

      {issues.length > 0 ? (
        <details className="nn-issues" open={finished}>
          <summary>Últimos avisos de los validadores ({issues.length})</summary>
          <ul>
            {issues.map((issue, index) => (
              <li key={`${issue.name}-${String(index)}`}>
                <strong>{issue.name}</strong>
                {issue.chapter == null ? '' : ` · capítulo ${String(issue.chapter)}`}
                {issue.explanation === '' ? null : <span>: {issue.explanation}</span>}
              </li>
            ))}
          </ul>
          {finished ? null : (
            <p className="nn-hint">Es normal ver avisos mientras se escribe: cada uno provoca una reescritura acotada.</p>
          )}
        </details>
      ) : null}
    </section>
  )
}
