// The cover's personalisation: title, "para", dedication and "de". Spec 003, FR-COVER-03;
// plan 003 Q11. The backend has no field for them (spec R2-3), so they live in this browser's
// localStorage under one versioned key and are never sent anywhere.
//
// State lives in the component; the stored copy is read once, when the cover mounts, and
// written in the "Guardar" handler (never in an effect). Every storage access is guarded:
// private modes and blocked site data throw, even on reading `window.localStorage` itself, and
// then the values simply live in memory until the page is left.
import { useState } from 'react'

export const STORAGE_KEY = 'msm.cover.v1'

export interface CoverSettings {
  title: string
  to: string
  dedication: string
  from: string
}

export const EMPTY_SETTINGS: CoverSettings = { title: '', to: '', dedication: '', from: '' }

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

/** Whatever is stored, narrowed field by field: a missing or foreign value reads as empty. */
export function parseSettings(raw: string | null): CoverSettings {
  if (raw === null) {
    return EMPTY_SETTINGS
  }
  let value: unknown
  try {
    value = JSON.parse(raw)
  } catch {
    return EMPTY_SETTINGS
  }
  if (!isRecord(value)) {
    return EMPTY_SETTINGS
  }
  return { title: text(value.title), to: text(value.to), dedication: text(value.dedication), from: text(value.from) }
}

function readStored(): CoverSettings {
  try {
    return parseSettings(window.localStorage.getItem(STORAGE_KEY))
  } catch {
    return EMPTY_SETTINGS
  }
}

/** True when the values reached storage; false when they stay in memory only. */
function writeStored(settings: CoverSettings): boolean {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
    return true
  } catch {
    return false
  }
}

/** Surrounding blanks carry no meaning; the dedication keeps its inner line breaks. */
function normalise(settings: CoverSettings): CoverSettings {
  return {
    title: settings.title.trim(),
    to: settings.to.trim(),
    dedication: settings.dedication.trim(),
    from: settings.from.trim(),
  }
}

export interface CoverSettingsState {
  settings: CoverSettings
  /** Shows the new values and stores them; returns whether they reached storage. */
  save: (next: CoverSettings) => boolean
}

export function useCoverSettings(): CoverSettingsState {
  const [settings, setSettings] = useState(readStored)

  function save(next: CoverSettings): boolean {
    const clean = normalise(next)
    setSettings(clean)
    return writeStored(clean)
  }

  return { settings, save }
}
