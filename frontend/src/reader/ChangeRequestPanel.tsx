// The change-request form (R05, spec 014): the selected fragment, prefilled and editable, and
// what the reader wants changed ("el perro se llama Nala"). It posts the request, polls the job
// and, once the new version is published, switches the reader to its index, where the changed
// chapters carry the "modificado" mark.
import { useId, useState, type SubmitEvent } from 'react'
import { Navigate } from 'react-router'

import { useChangeJob, useRequestChange, type ChangeJob } from './api'
import { readerHref } from './context'

export interface ChangeRequestPanelProps {
  novelId: string
  fragment: string
  onClose: () => void
}

function progress(status: ChangeJob['status'] | undefined): string | null {
  switch (status) {
    case 'queued':
      return 'En cola…'
    case 'resolving':
      return 'Buscando el hecho que quieres cambiar…'
    case 'running':
      return 'Regenerando solo los capítulos que usan ese hecho…'
    default:
      return null
  }
}

function text(data: FormData, name: string): string {
  const value = data.get(name)
  return typeof value === 'string' ? value.trim() : ''
}

export function ChangeRequestPanel({ novelId, fragment, onClose }: ChangeRequestPanelProps) {
  const id = useId()
  const request = useRequestChange(novelId)
  const [jobId, setJobId] = useState<string | null>(null)
  const job = useChangeJob(novelId, jobId)

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const wanted = text(data, 'request')
    if (wanted === '') return
    const selectedText = text(data, 'fragment')
    request.mutate(
      { request: wanted, fragment: selectedText === '' ? null : selectedText },
      {
        onSuccess: (accepted) => {
          setJobId(accepted.job_id)
        },
      },
    )
  }

  const status = job.data?.status
  if (status === 'done' && job.data?.new_version != null) {
    return <Navigate to={readerHref(novelId, job.data.new_version, 'indice')} />
  }
  const busy = request.isPending || (jobId !== null && status !== 'failed')

  return (
    <section className="reader-change card" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`} className="reader-change-title">
        Pedir un cambio
      </h2>
      <form onSubmit={handleSubmit} className="reader-change-form">
        <label htmlFor={`${id}-fragment`}>Fragmento seleccionado</label>
        <textarea id={`${id}-fragment`} name="fragment" rows={3} defaultValue={fragment} maxLength={4000} />
        <label htmlFor={`${id}-request`}>¿Qué quieres cambiar?</label>
        <input
          id={`${id}-request`}
          name="request"
          type="text"
          required
          maxLength={1000}
          placeholder="el perro se llama Nala"
        />
        <div className="reader-change-actions">
          <button type="submit" className="reader-btn-primary" disabled={busy}>
            Enviar
          </button>
          <button type="button" className="btn-ghost" onClick={onClose}>
            Cerrar
          </button>
        </div>
      </form>
      <div role="status" className="reader-change-status">
        {request.isError ? <p>{request.error.message}</p> : null}
        {progress(status) === null ? null : <p>{progress(status)}</p>}
        {status === 'failed' ? <p>{`No se ha podido aplicar el cambio: ${job.data?.detail ?? ''}`}</p> : null}
        {status === 'done' ? <p>El cambio está hecho.</p> : null}
      </div>
    </section>
  )
}
