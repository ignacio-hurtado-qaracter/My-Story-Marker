// A list of short values typed one at a time: Enter or comma adds a chip, × removes it.
import { useId, useState, type KeyboardEvent } from 'react'

export interface ChipInputProps {
  label: string
  values: string[]
  onChange: (values: string[]) => void
  placeholder?: string
  hint?: string
}

export function ChipInput({ label, values, onChange, placeholder, hint }: ChipInputProps) {
  const id = useId()
  const [text, setText] = useState('')

  function add() {
    const value = text.trim().replace(/,$/, '').trim()
    if (value !== '' && !values.includes(value)) onChange([...values, value])
    setText('')
  }

  function handleKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault()
      add()
    } else if (event.key === 'Backspace' && text === '' && values.length > 0) {
      onChange(values.slice(0, -1))
    }
  }

  return (
    <div className="nn-field">
      <label htmlFor={id}>{label}</label>
      <div className="nn-chips">
        <ul className="nn-chip-list" aria-label={label}>
          {values.map((value) => (
            <li key={value} className="nn-chip">
              {value}
              <button
                type="button"
                className="nn-chip-remove"
                aria-label={`Quitar ${value}`}
                onClick={() => {
                  onChange(values.filter((v) => v !== value))
                }}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
        <input
          id={id}
          type="text"
          value={text}
          placeholder={placeholder ?? 'Escribe y pulsa Intro'}
          aria-describedby={hint === undefined ? undefined : `${id}-hint`}
          onChange={(event) => {
            setText(event.target.value)
          }}
          onKeyDown={handleKey}
          onBlur={add}
        />
      </div>
      {hint === undefined ? null : (
        <p id={`${id}-hint`} className="nn-hint">
          {hint}
        </p>
      )}
    </div>
  )
}
