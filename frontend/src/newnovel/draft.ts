// The wizard's form state and its conversion to a brief (spec 020). The form state is UI state,
// not an API shape: the API takes the brief as a plain JSON object (`brief.v1.json`) and answers
// with a `BriefReport`, so the only typed boundary is `toBrief` → `Schemas['GenerateRequest']`.

export const GENRES = [
  ['aventura', 'Aventura'],
  ['fantasía', 'Fantasía'],
  ['comedia', 'Comedia'],
  ['romance', 'Romance'],
  ['misterio', 'Misterio'],
  ['ciencia_ficción', 'Ciencia ficción'],
  ['realista', 'Realista'],
  ['fábula', 'Fábula'],
] as const

export const TONES = [
  ['tierno', 'Tierno'],
  ['divertido', 'Divertido'],
  ['emotivo', 'Emotivo'],
  ['épico', 'Épico'],
  ['nostálgico', 'Nostálgico'],
  ['oscuro', 'Oscuro'],
] as const

export const OCCASIONS = [
  ['cumpleaños', 'Cumpleaños'],
  ['boda', 'Boda'],
  ['aniversario', 'Aniversario'],
  ['jubilación', 'Jubilación'],
  ['nacimiento', 'Nacimiento'],
  ['graduación', 'Graduación'],
  ['otro', 'Otra ocasión'],
] as const

export const GENDERS = [
  ['', 'Sin especificar'],
  ['femenino', 'Femenino'],
  ['masculino', 'Masculino'],
  ['no_binario', 'No binario'],
] as const

export interface PersonRow {
  name: string
  relation: string
  traits: string[]
}

export interface PetRow {
  name: string
  species: string
  description: string
}

export interface PlaceRow {
  name: string
  description: string
}

export interface MemoryRow {
  title: string
  description: string
  date: string
  place: string
  people: string
}

export interface Draft {
  name: string
  age: string
  birthDate: string
  gender: string
  relation: string
  traits: string[]
  hobbies: string[]
  profession: string
  people: PersonRow[]
  pets: PetRow[]
  places: PlaceRow[]
  memories: MemoryRow[]
  genre: string
  tone: string
  chapters: number
  forbidden: string[]
  mandatory: string[]
  freeText: string
  dedication: string
  occasion: string
  buyerName: string
}

export const emptyMemory = (): MemoryRow => ({ title: '', description: '', date: '', place: '', people: '' })

export function emptyDraft(): Draft {
  return {
    name: '',
    age: '',
    birthDate: '',
    gender: '',
    relation: '',
    traits: [],
    hobbies: [],
    profession: '',
    people: [],
    pets: [],
    places: [],
    memories: [emptyMemory()],
    genre: '',
    tone: '',
    chapters: 10,
    forbidden: [],
    mandatory: [],
    freeText: '',
    dedication: '',
    occasion: 'cumpleaños',
    buyerName: '',
  }
}

/** A fictional example, a copy of `evals/briefs/ejemplo.json` ("Rellenar con ejemplo"). */
export function exampleDraft(): Draft {
  return {
    name: 'Tomás Arriaga',
    age: '65',
    birthDate: '1961-05-12',
    gender: 'masculino',
    relation: 'padre',
    traits: ['paciente', 'bromista', 'curioso', 'generoso con su tiempo'],
    hobbies: ['la carpintería', 'las rutas en bicicleta', 'los crucigramas del domingo'],
    profession: 'maestro de escuela rural',
    people: [
      { name: 'Lucía', relation: 'esposa', traits: ['risueña', 'valiente', 'gran cocinera'] },
      { name: 'Irene', relation: 'hija', traits: ['organizada', 'cabezota', 'cariñosa'] },
      { name: 'Daniel', relation: 'hijo', traits: ['soñador', 'músico', 'despistado'] },
    ],
    pets: [
      {
        name: 'Canela',
        species: 'perra',
        description:
          'Perra mestiza de color canela, adoptada en 2018, que le acompaña al taller y duerme bajo el banco de carpintero.',
      },
    ],
    places: [
      {
        name: 'Valdelosa',
        description: 'Pueblo de montaña con una escuela de una sola aula donde Tomás dio clase durante treinta años.',
      },
      {
        name: 'el taller del garaje',
        description: 'Un garaje convertido en taller de carpintería, oloroso a serrín y barniz, con una radio antigua.',
      },
    ],
    memories: [
      {
        title: 'El primer día en la escuela de Valdelosa',
        description:
          'Llegó con una maleta de cartón y nueve alumnos le esperaban en la única aula; la estufa no funcionaba y dio la primera clase con abrigo.',
        date: '1992-09-14',
        place: 'Valdelosa',
        people: '',
      },
      {
        title: 'La cuna de madera para Daniel',
        description:
          'Pasó tres meses de noches en el taller construyendo la cuna de su hijo; Lucía le llevaba café y le corregía las medidas.',
        date: '1994-10-20',
        place: 'el taller del garaje',
        people: 'Lucía',
      },
      {
        title: 'La ruta en bici hasta el lago con Irene',
        description:
          'Irene y él pedalearon sesenta kilómetros hasta el lago; se perdieron, compartieron un bocadillo y volvieron de noche cantando.',
        date: '2016-07-03',
        place: '',
        people: 'Irene',
      },
    ],
    genre: 'aventura',
    tone: 'emotivo',
    chapters: 10,
    forbidden: ['Remedios', 'despido', 'hospital'],
    mandatory: ['la última clase antes de jubilarse', 'Canela en el taller'],
    freeText: '',
    dedication:
      'Para papá, que enseñó a leer a medio valle y ahora por fin tiene tiempo para escribir su propia historia. Con todo nuestro cariño, Irene y Daniel.',
    occasion: 'jubilación',
    buyerName: 'Irene',
  }
}

const hasText = (...values: string[]) => values.some((value) => value.trim() !== '')

function optional(value: string): string | undefined {
  const trimmed = value.trim()
  return trimmed === '' ? undefined : trimmed
}

function list(value: string): string[] {
  return value
    .split(',')
    .map((part) => part.trim())
    .filter((part) => part !== '')
}

/** The brief the backend validates. Empty optional fields are left out; empty rows are dropped. */
export function toBrief(draft: Draft): Record<string, unknown> {
  const age = draft.age.trim() === '' ? undefined : Number(draft.age)
  return {
    recipient: {
      name: draft.name.trim(),
      ...(age === undefined || Number.isNaN(age) ? {} : { age }),
      ...(draft.gender === '' ? {} : { gender: draft.gender }),
      ...(draft.birthDate === '' ? {} : { birth_date: draft.birthDate }),
      relation_to_buyer: draft.relation.trim(),
      traits: draft.traits,
      hobbies: draft.hobbies,
      ...(optional(draft.profession) === undefined ? {} : { profession: optional(draft.profession) }),
    },
    occasion: draft.occasion,
    buyer_name: draft.buyerName.trim(),
    dedication: draft.dedication.trim(),
    people: draft.people
      .filter((p) => hasText(p.name, p.relation) || p.traits.length > 0)
      .map((p) => ({ name: p.name.trim(), relation: p.relation.trim(), traits: p.traits })),
    pets: draft.pets
      .filter((p) => hasText(p.name, p.species, p.description))
      .map((p) => ({ name: p.name.trim(), species: p.species.trim(), description: p.description.trim() })),
    places: draft.places
      .filter((p) => hasText(p.name, p.description))
      .map((p) => ({ name: p.name.trim(), description: p.description.trim() })),
    memories: draft.memories
      .filter((m) => hasText(m.title, m.description, m.date, m.place, m.people))
      .map((m) => ({
        title: m.title.trim(),
        description: m.description.trim(),
        date: m.date === '' ? null : m.date,
        place: optional(m.place) ?? null,
        people: list(m.people),
      })),
    ...(draft.genre === '' ? {} : { genre: draft.genre }),
    ...(draft.tone === '' ? {} : { tone: draft.tone }),
    length: { chapters: draft.chapters, words_min: 1000, words_max: 1500 },
    language: 'es',
    forbidden_terms: draft.forbidden,
    mandatory_elements: draft.mandatory,
    free_text: optional(draft.freeText) ?? null,
  }
}

// ---------- The validation report, in Spanish ----------

/** The wizard step (1–5) where each field is filled in. */
const FIELDS = new Map<string, [label: string, step: number]>([
  ['recipient.name', ['el nombre del destinatario', 1]],
  ['recipient.age', ['la edad', 1]],
  ['recipient.birth_date', ['la fecha de nacimiento', 1]],
  ['recipient.traits', ['al menos un rasgo del destinatario', 1]],
  ['recipient.gender', ['el género del destinatario', 1]],
  ['people', ['las personas', 2]],
  ['pets', ['las mascotas', 2]],
  ['places', ['los lugares', 2]],
  ['memories', ['al menos un recuerdo', 3]],
  ['genre', ['el género literario', 4]],
  ['tone', ['el tono', 4]],
  ['length', ['el número de capítulos', 4]],
  ['forbidden_terms', ['las palabras prohibidas', 4]],
  ['mandatory_elements', ['los elementos obligatorios', 4]],
  ['dedication', ['la dedicatoria', 5]],
  ['occasion', ['la ocasión', 5]],
])

const PARTS = new Map<string, string>([
  ['name', 'nombre'],
  ['title', 'título'],
  ['date', 'fecha'],
  ['age', 'edad'],
  ['genre', 'género'],
  ['tone', 'tono'],
  ['birth_date', 'fecha de nacimiento'],
  ['words_min', 'palabras mínimas'],
  ['words_max', 'palabras máximas'],
])

const ROWS = new Map<string, string>([
  ['memories', 'Recuerdo'],
  ['people', 'Persona'],
  ['pets', 'Mascota'],
  ['places', 'Lugar'],
  ['mandatory_elements', 'Elemento obligatorio'],
])

/** `memories[1].date`, `memories.0.title` or `recipient.age` → a Spanish label and its step. */
export function describePath(path: string): { label: string; step: number } {
  const clean = path.replace(/\[(\d+)\]/g, '.$1')
  const parts = clean.split('.')
  const head = parts[0] ?? ''
  const exact = FIELDS.get(clean)
  const step = (exact ?? FIELDS.get(head))?.[1] ?? (head === 'recipient' ? 1 : 5)
  const row = ROWS.get(head)
  const index = parts[1]
  if (row !== undefined && index !== undefined && /^\d+$/.test(index)) {
    const part = parts[2]
    const leaf = part === undefined ? '' : ` · ${PARTS.get(part) ?? part}`
    return { label: `${row} ${String(Number(index) + 1)}${leaf}`, step }
  }
  if (exact !== undefined) return { label: exact[0], step }
  const leaf = parts.at(-1) ?? clean
  return { label: PARTS.get(leaf) ?? leaf, step }
}

export interface Issue {
  kind: 'missing' | 'contradiction' | 'error'
  text: string
  step: number
}

/** A `BriefReport` as Spanish sentences, each pointing at the step that fixes it. */
export function describeReport(report: { missing?: string[]; contradictions?: string[]; errors?: string[] }): Issue[] {
  const issues: Issue[] = []
  for (const path of report.missing ?? []) {
    const { label, step } = describePath(path)
    issues.push({ kind: 'missing', text: `Falta ${label}.`, step })
  }
  for (const message of report.contradictions ?? []) {
    // "recipient.age=6 vs genre=romance: el romance no es apto para menos de 12 años"
    const cut = message.indexOf(': ')
    const fields = cut < 0 ? '' : message.slice(0, cut)
    const reason = cut < 0 ? message : message.slice(cut + 2)
    const first = fields.split(' vs ')[0]?.split('=')[0] ?? ''
    const involved = fields
      .split(' vs ')
      .map((side) => {
        const [path = '', value] = side.split('=')
        const label = describePath(path).label
        return value === undefined ? label : `${label}: ${value}`
      })
      .join(' · ')
    const sentence = reason.charAt(0).toUpperCase() + reason.slice(1)
    issues.push({
      kind: 'contradiction',
      text: involved === '' ? `${sentence}.` : `${sentence} (${involved}).`,
      step: describePath(first).step,
    })
  }
  for (const message of report.errors ?? []) {
    const cut = message.indexOf(': ')
    const path = cut < 0 ? '' : message.slice(0, cut)
    const { label, step } = describePath(path)
    issues.push({ kind: 'error', text: `Revisa ${label}: el valor no es válido.`, step })
  }
  return issues
}
