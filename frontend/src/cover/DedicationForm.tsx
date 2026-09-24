// The form that personalises the cover. Spec 003, FR-COVER-03: four labelled fields, "Guardar"
// and "Cancelar", and the note that the values stay in this browser.
//
// Uncontrolled: each field starts from the saved value and the values are read from the form
// on submit, so typing re-renders nothing and "Cancelar" has nothing to undo.
import { useId, type KeyboardEvent, type Ref, type SubmitEvent } from 'react'

import type { CoverSettings } from './useCoverSettings'

export interface DedicationFormProps {
  /** The saved values the fields start from. */
  initial: CoverSettings
  onSave: (next: CoverSettings) => void
  onCancel: () => void
  /** The first field, so the page can move focus into the form when it opens. */
  firstFieldRef?: Ref<HTMLInputElement>
}

function field(data: FormData, name: keyof CoverSettings): string {
  const value = data.get(name)
  return typeof value === 'string' ? value : ''
}

export function DedicationForm({ initial, onSave, onCancel, firstFieldRef }: DedicationFormProps) {
  const id = useId()

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    onSave({
      title: field(data, 'title'),
      to: field(data, 'to'),
      dedication: field(data, 'dedication'),
      from: field(data, 'from'),
    })
  }

  // Escape, in any field, closes the form like "Cancelar".
  function handleKeyDown(event: KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) {
    if (event.key === 'Escape') {
      event.preventDefault()
      onCancel()
    }
  }

  return (
    <form className="cover-form" aria-label="Personalizar portada" onSubmit={handleSubmit}>
      <div className="cover-field">
        <label htmlFor={`${id}-title`}>Título</label>
        <input
          ref={firstFieldRef}
          id={`${id}-title`}
          name="title"
          type="text"
          maxLength={120}
          placeholder="Mi novela"
          defaultValue={initial.title}
          onKeyDown={handleKeyDown}
        />
      </div>
      <div className="cover-field">
        <label htmlFor={`${id}-to`}>Para</label>
        <input id={`${id}-to`} name="to" type="text" maxLength={80} defaultValue={initial.to} onKeyDown={handleKeyDown} />
      </div>
      <div className="cover-field">
        <label htmlFor={`${id}-dedication`}>Dedicatoria</label>
        <textarea
          id={`${id}-dedication`}
          name="dedication"
          rows={4}
          maxLength={600}
          defaultValue={initial.dedication}
          onKeyDown={handleKeyDown}
        />
      </div>
      <div className="cover-field">
        <label htmlFor={`${id}-from`}>De</label>
        <input id={`${id}-from`} name="from" type="text" maxLength={80} defaultValue={initial.from} onKeyDown={handleKeyDown} />
      </div>
      <p className="cover-form-note">Se guarda solo en este navegador.</p>
      <div className="cover-form-actions">
        <button type="submit" className="cover-btn-primary">
          Guardar
        </button>
        <button type="button" className="btn-ghost cover-btn" onClick={onCancel}>
          Cancelar
        </button>
      </div>
    </form>
  )
}
