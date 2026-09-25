// `/nueva` (spec 020): a five-step form that builds the brief, validates it live on the review
// step (`POST /interview/validate`) and launches the generation (`POST /novels/generate`). With
// `?novela=<id>` the page shows that generation's progress instead, so a reload keeps it.
import './newnovel.css'

import { useId, useState, type ReactNode, type SubmitEvent } from 'react'
import { useSearchParams } from 'react-router'

import { Heading } from '../shared/ui'
import { InvalidBriefError, useBriefReport, useGenerateNovel } from './api'
import { ChipInput } from './ChipInput'
import {
  GENDERS,
  GENRES,
  OCCASIONS,
  TONES,
  describeReport,
  emptyDraft,
  emptyMemory,
  exampleDraft,
  toBrief,
  type Draft,
  type Issue,
} from './draft'
import { GenerationProgress } from './GenerationProgress'

const STEPS = ['Destinatario', 'Personas y lugares', 'Recuerdos', 'Historia', 'Dedicatoria y revisión'] as const

type Update = <K extends keyof Draft>(key: K, value: Draft[K]) => void

function Field({ label, children, hint }: { label: string; children: (id: string) => ReactNode; hint?: string }) {
  const id = useId()
  return (
    <div className="nn-field">
      <label htmlFor={id}>{label}</label>
      {children(id)}
      {hint === undefined ? null : <p className="nn-hint">{hint}</p>}
    </div>
  )
}

function label(options: readonly (readonly [string, string])[], value: string): string {
  return options.find(([key]) => key === value)?.[1] ?? '—'
}

// ---------- Step 1 ----------

function RecipientStep({ draft, set }: { draft: Draft; set: Update }) {
  return (
    <>
      <div className="nn-grid">
        <Field label="Nombre *">
          {(id) => (
            <input
              id={id}
              value={draft.name}
              autoComplete="off"
              onChange={(e) => {
                set('name', e.target.value)
              }}
            />
          )}
        </Field>
        <Field label="Edad *">
          {(id) => (
            <input
              id={id}
              type="number"
              min={0}
              max={120}
              inputMode="numeric"
              value={draft.age}
              onChange={(e) => {
                set('age', e.target.value)
              }}
            />
          )}
        </Field>
        <Field label="Fecha de nacimiento (opcional)">
          {(id) => (
            <input
              id={id}
              type="date"
              value={draft.birthDate}
              onChange={(e) => {
                set('birthDate', e.target.value)
              }}
            />
          )}
        </Field>
        <Field label="Género del destinatario">
          {(id) => (
            <select
              id={id}
              value={draft.gender}
              onChange={(e) => {
                set('gender', e.target.value)
              }}
            >
              {GENDERS.map(([value, text]) => (
                <option key={value} value={value}>
                  {text}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Relación contigo">
          {(id) => (
            <input
              id={id}
              value={draft.relation}
              placeholder="padre, amiga, abuela…"
              onChange={(e) => {
                set('relation', e.target.value)
              }}
            />
          )}
        </Field>
        <Field label="Profesión">
          {(id) => (
            <input
              id={id}
              value={draft.profession}
              onChange={(e) => {
                set('profession', e.target.value)
              }}
            />
          )}
        </Field>
      </div>
      <ChipInput
        label="Rasgos de carácter *"
        values={draft.traits}
        onChange={(v) => {
          set('traits', v)
        }}
        placeholder="valiente, bromista…"
        hint="Escribe un rasgo y pulsa Intro o coma."
      />
      <ChipInput
        label="Aficiones"
        values={draft.hobbies}
        onChange={(v) => {
          set('hobbies', v)
        }}
        placeholder="la carpintería, el ajedrez…"
      />
    </>
  )
}

// ---------- Step 2 ----------

function Rows<T>({
  title,
  rows,
  add,
  onChange,
  render,
  addLabel,
  empty,
}: {
  title: string
  rows: T[]
  add: () => T
  onChange: (rows: T[]) => void
  render: (row: T, update: (row: T) => void) => ReactNode
  addLabel: string
  empty: string
}) {
  return (
    <fieldset className="nn-rows">
      <legend>{title}</legend>
      {rows.length === 0 ? <p className="nn-hint">{empty}</p> : null}
      {rows.map((row, index) => (
        <div className="nn-row" key={index}>
          {render(row, (next) => {
            onChange(rows.map((r, i) => (i === index ? next : r)))
          })}
          <button
            type="button"
            className="nn-row-remove"
            aria-label={`Quitar ${title.toLowerCase()} ${String(index + 1)}`}
            onClick={() => {
              onChange(rows.filter((_, i) => i !== index))
            }}
          >
            Quitar
          </button>
        </div>
      ))}
      <button
        type="button"
        className="btn-ghost"
        onClick={() => {
          onChange([...rows, add()])
        }}
      >
        + {addLabel}
      </button>
    </fieldset>
  )
}

function CastStep({ draft, set }: { draft: Draft; set: Update }) {
  return (
    <>
      <Rows
        title="Personas"
        rows={draft.people}
        add={() => ({ name: '', relation: '', traits: [] })}
        onChange={(v) => {
          set('people', v)
        }}
        addLabel="Añadir persona"
        empty="Familia, amigos… quien quieras que aparezca en la historia."
        render={(row, update) => (
          <div className="nn-grid">
            <Field label="Nombre">
              {(id) => (
                <input
                  id={id}
                  value={row.name}
                  onChange={(e) => {
                    update({ ...row, name: e.target.value })
                  }}
                />
              )}
            </Field>
            <Field label="Relación">
              {(id) => (
                <input
                  id={id}
                  value={row.relation}
                  placeholder="hermana, amigo…"
                  onChange={(e) => {
                    update({ ...row, relation: e.target.value })
                  }}
                />
              )}
            </Field>
            <ChipInput
              label="Rasgos"
              values={row.traits}
              onChange={(traits) => {
                update({ ...row, traits })
              }}
            />
          </div>
        )}
      />
      <Rows
        title="Mascotas"
        rows={draft.pets}
        add={() => ({ name: '', species: '', description: '' })}
        onChange={(v) => {
          set('pets', v)
        }}
        addLabel="Añadir mascota"
        empty="Sin mascotas por ahora."
        render={(row, update) => (
          <div className="nn-grid">
            <Field label="Nombre">
              {(id) => (
                <input
                  id={id}
                  value={row.name}
                  onChange={(e) => {
                    update({ ...row, name: e.target.value })
                  }}
                />
              )}
            </Field>
            <Field label="Especie">
              {(id) => (
                <input
                  id={id}
                  value={row.species}
                  placeholder="perro, gata…"
                  onChange={(e) => {
                    update({ ...row, species: e.target.value })
                  }}
                />
              )}
            </Field>
            <Field label="Descripción">
              {(id) => (
                <input
                  id={id}
                  value={row.description}
                  onChange={(e) => {
                    update({ ...row, description: e.target.value })
                  }}
                />
              )}
            </Field>
          </div>
        )}
      />
      <Rows
        title="Lugares"
        rows={draft.places}
        add={() => ({ name: '', description: '' })}
        onChange={(v) => {
          set('places', v)
        }}
        addLabel="Añadir lugar"
        empty="El pueblo, la casa de la playa, el taller…"
        render={(row, update) => (
          <div className="nn-grid">
            <Field label="Nombre">
              {(id) => (
                <input
                  id={id}
                  value={row.name}
                  onChange={(e) => {
                    update({ ...row, name: e.target.value })
                  }}
                />
              )}
            </Field>
            <Field label="Descripción">
              {(id) => (
                <input
                  id={id}
                  value={row.description}
                  onChange={(e) => {
                    update({ ...row, description: e.target.value })
                  }}
                />
              )}
            </Field>
          </div>
        )}
      />
    </>
  )
}

// ---------- Step 3 ----------

function MemoriesStep({ draft, set }: { draft: Draft; set: Update }) {
  return (
    <Rows
      title="Recuerdos"
      rows={draft.memories}
      add={emptyMemory}
      onChange={(v) => {
        set('memories', v)
      }}
      addLabel="Añadir recuerdo"
      empty="Hace falta al menos un recuerdo: es la materia prima de la novela."
      render={(row, update) => (
        <div className="nn-grid">
          <Field label="Título *">
            {(id) => (
              <input
                id={id}
                value={row.title}
                placeholder="El verano en la playa"
                onChange={(e) => {
                  update({ ...row, title: e.target.value })
                }}
              />
            )}
          </Field>
          <Field label="Fecha">
            {(id) => (
              <input
                id={id}
                type="date"
                value={row.date}
                onChange={(e) => {
                  update({ ...row, date: e.target.value })
                }}
              />
            )}
          </Field>
          <Field label="Lugar">
            {(id) => (
              <input
                id={id}
                value={row.place}
                onChange={(e) => {
                  update({ ...row, place: e.target.value })
                }}
              />
            )}
          </Field>
          <Field label="Personas (separadas por comas)">
            {(id) => (
              <input
                id={id}
                value={row.people}
                onChange={(e) => {
                  update({ ...row, people: e.target.value })
                }}
              />
            )}
          </Field>
          <div className="nn-wide">
            <Field label="Qué pasó">
              {(id) => (
                <textarea
                  id={id}
                  rows={3}
                  value={row.description}
                  onChange={(e) => {
                    update({ ...row, description: e.target.value })
                  }}
                />
              )}
            </Field>
          </div>
        </div>
      )}
    />
  )
}

// ---------- Step 4 ----------

function minutes(chapters: number): number {
  return Math.round((chapters * 7) / 5) * 5 || 5
}

function StoryStep({ draft, set }: { draft: Draft; set: Update }) {
  return (
    <>
      <div className="nn-grid">
        <Field label="Género *">
          {(id) => (
            <select
              id={id}
              value={draft.genre}
              onChange={(e) => {
                set('genre', e.target.value)
              }}
            >
              <option value="">Elige un género</option>
              {GENRES.map(([value, text]) => (
                <option key={value} value={value}>
                  {text}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Tono *">
          {(id) => (
            <select
              id={id}
              value={draft.tone}
              onChange={(e) => {
                set('tone', e.target.value)
              }}
            >
              <option value="">Elige un tono</option>
              {TONES.map(([value, text]) => (
                <option key={value} value={value}>
                  {text}
                </option>
              ))}
            </select>
          )}
        </Field>
      </div>
      <Field
        label={`Capítulos: ${String(draft.chapters)}`}
        hint={`Unos ${String(minutes(draft.chapters))} minutos de generación (3 capítulos ≈ 20 min, 10 ≈ 70 min). Cada capítulo tiene entre 1.000 y 1.500 palabras.`}
      >
        {(id) => (
          <input
            id={id}
            type="range"
            min={1}
            max={10}
            step={1}
            value={draft.chapters}
            onChange={(e) => {
              set('chapters', Number(e.target.value))
            }}
          />
        )}
      </Field>
      <ChipInput
        label="Palabras o temas prohibidos"
        values={draft.forbidden}
        onChange={(v) => {
          set('forbidden', v)
        }}
        placeholder="hospital, un nombre…"
        hint="No aparecerán en la novela: se comprueban en cada capítulo."
      />
      <ChipInput
        label="Elementos obligatorios"
        values={draft.mandatory}
        onChange={(v) => {
          set('mandatory', v)
        }}
        placeholder="la última clase, la canción de cuna…"
      />
      <Field
        label="Algo más que quieras contar (opcional)"
        hint="Este texto se trata como datos, no como instrucciones: solo se extraen de él hechos (nombres, fechas, lugares). Pedir aquí que el sistema haga otra cosa no tiene efecto."
      >
        {(id) => (
          <textarea
            id={id}
            rows={4}
            maxLength={4000}
            value={draft.freeText}
            onChange={(e) => {
              set('freeText', e.target.value)
            }}
          />
        )}
      </Field>
    </>
  )
}

// ---------- Step 5 ----------

function IssueList({ issues, goTo }: { issues: Issue[]; goTo: (step: number) => void }) {
  return (
    <ul className="nn-issue-list">
      {issues.map((issue, index) => (
        <li key={`${issue.text}-${String(index)}`} className={`nn-issue nn-issue-${issue.kind}`}>
          <span>{issue.text}</span>
          <button
            type="button"
            className="nn-link"
            onClick={() => {
              goTo(issue.step)
            }}
          >
            Ir al paso {issue.step}
          </button>
        </li>
      ))}
    </ul>
  )
}

function Summary({ draft }: { draft: Draft }) {
  const rows: [string, string][] = [
    ['Para', draft.name === '' ? '—' : `${draft.name}${draft.age === '' ? '' : `, ${draft.age} años`}`],
    ['Rasgos', draft.traits.join(', ') || '—'],
    ['Personas', draft.people.map((p) => p.name).filter(Boolean).join(', ') || '—'],
    ['Mascotas', draft.pets.map((p) => p.name).filter(Boolean).join(', ') || '—'],
    ['Lugares', draft.places.map((p) => p.name).filter(Boolean).join(', ') || '—'],
    ['Recuerdos', String(draft.memories.filter((m) => m.title.trim() !== '').length)],
    ['Género y tono', `${label(GENRES, draft.genre)} · ${label(TONES, draft.tone)}`],
    ['Capítulos', String(draft.chapters)],
    ['Prohibido', draft.forbidden.join(', ') || '—'],
  ]
  return (
    <dl className="nn-summary">
      {rows.map(([term, value]) => (
        <div key={term}>
          <dt>{term}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function ReviewStep({
  draft,
  set,
  issues,
  checking,
  goTo,
}: {
  draft: Draft
  set: Update
  issues: Issue[] | null
  checking: boolean
  goTo: (step: number) => void
}) {
  return (
    <>
      <div className="nn-grid">
        <Field label="Ocasión">
          {(id) => (
            <select
              id={id}
              value={draft.occasion}
              onChange={(e) => {
                set('occasion', e.target.value)
              }}
            >
              {OCCASIONS.map(([value, text]) => (
                <option key={value} value={value}>
                  {text}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Quién la regala">
          {(id) => (
            <input
              id={id}
              value={draft.buyerName}
              onChange={(e) => {
                set('buyerName', e.target.value)
              }}
            />
          )}
        </Field>
      </div>
      <Field label="Dedicatoria *" hint="Aparecerá en la portada, tal cual la escribas.">
        {(id) => (
          <textarea
            id={id}
            rows={3}
            value={draft.dedication}
            onChange={(e) => {
              set('dedication', e.target.value)
            }}
          />
        )}
      </Field>
      <h3 className="nn-subtitle">Resumen</h3>
      <Summary draft={draft} />
      <div className="nn-validation" aria-live="polite">
        {issues === null ? (
          <p className="nn-hint">{checking ? 'Comprobando la ficha…' : ''}</p>
        ) : issues.length === 0 ? (
          <p className="nn-valid">✓ La ficha está completa y es coherente.</p>
        ) : (
          <>
            <p className="nn-invalid" role="alert">
              Antes de generar, revisa {issues.length === 1 ? 'este punto' : `estos ${String(issues.length)} puntos`}:
            </p>
            <IssueList issues={issues} goTo={goTo} />
          </>
        )}
      </div>
    </>
  )
}

// ---------- The page ----------

export function NewNovelPage() {
  const [search, setSearch] = useSearchParams()
  const novelId = search.get('novela')
  const [draft, setDraft] = useState<Draft>(emptyDraft)
  const [step, setStep] = useState(1)
  const generate = useGenerateNovel()
  const brief = toBrief(draft)
  const report = useBriefReport(brief, step === STEPS.length && novelId === null)
  const serverIssues = generate.error instanceof InvalidBriefError ? describeReport(generate.error.report) : null
  const issues = report.data ? describeReport(report.data) : serverIssues
  const valid = report.data?.valid === true && !report.isPlaceholderData

  const set: Update = (key, value) => {
    setDraft((current) => ({ ...current, [key]: value }))
  }

  function goTo(next: number) {
    setStep(Math.min(Math.max(next, 1), STEPS.length))
  }

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    if (step < STEPS.length) {
      goTo(step + 1)
      return
    }
    if (!valid) return
    generate.mutate(
      { brief, chapters: draft.chapters },
      {
        onSuccess: (accepted) => {
          setSearch({ novela: accepted.novel_id })
        },
      },
    )
  }

  if (novelId !== null) {
    return (
      <section className="nn-page">
        <title>Generando tu novela · My Story Marker</title>
        <div className="nn-hero">
          <p className="eyebrow">Nueva novela</p>
          <Heading>Tu novela se está escribiendo</Heading>
        </div>
        <GenerationProgress novelId={novelId} />
      </section>
    )
  }

  const title = STEPS[step - 1] ?? ''
  return (
    <section className="nn-page">
      <title>Nueva novela · My Story Marker</title>
      <div className="nn-hero">
        <p className="eyebrow">Nueva novela</p>
        <Heading>Cuéntanos a quién va dedicada</Heading>
        <p className="nn-lead">
          Rellena la ficha en cinco pasos. Con ella se planifica y escribe una novela única, capítulo a capítulo.
        </p>
        <button
          type="button"
          className="btn-ghost"
          onClick={() => {
            setDraft(exampleDraft())
          }}
        >
          Rellenar con ejemplo
        </button>
      </div>

      <ol className="nn-steps" aria-label="Pasos">
        {STEPS.map((name, index) => (
          <li key={name}>
            <button
              type="button"
              className="nn-step"
              aria-label={`Paso ${String(index + 1)}: ${name}`}
              aria-current={index + 1 === step ? 'step' : undefined}
              onClick={() => {
                goTo(index + 1)
              }}
            >
              <span className="nn-step-number">{index + 1}</span>
              <span className="nn-step-name">{name}</span>
            </button>
          </li>
        ))}
      </ol>

      <form className="card nn-form" onSubmit={handleSubmit} noValidate aria-labelledby="nn-step-title">
        <h2 id="nn-step-title" className="nn-form-title">
          <span className="nn-form-step">
            Paso {step} de {STEPS.length}
          </span>
          {title}
        </h2>
        {step === 1 ? <RecipientStep draft={draft} set={set} /> : null}
        {step === 2 ? <CastStep draft={draft} set={set} /> : null}
        {step === 3 ? <MemoriesStep draft={draft} set={set} /> : null}
        {step === 4 ? <StoryStep draft={draft} set={set} /> : null}
        {step === 5 ? (
          <ReviewStep draft={draft} set={set} issues={issues} checking={report.isFetching} goTo={goTo} />
        ) : null}
        {generate.isError && !(generate.error instanceof InvalidBriefError) ? (
          <p className="nn-invalid" role="alert">
            {generate.error.message}
          </p>
        ) : null}
        <div className="nn-nav">
          {step > 1 ? (
            <button
              type="button"
              className="btn-ghost"
              onClick={() => {
                goTo(step - 1)
              }}
            >
              Anterior
            </button>
          ) : (
            <span />
          )}
          {step < STEPS.length ? (
            <button type="submit" className="nn-btn-primary">
              Siguiente
            </button>
          ) : (
            <button type="submit" className="nn-btn-primary" disabled={!valid || generate.isPending}>
              {generate.isPending ? 'Enviando…' : 'Generar novela'}
            </button>
          )}
        </div>
      </form>
    </section>
  )
}
