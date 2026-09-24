// One scene's record and draft as server state. Spec 002, FR-SCN-02. The caller has already
// checked the id against the scene-id pattern (FR-SCN-06).
import { useQuery } from '@tanstack/react-query'

import { fetchDraft, fetchScene } from './api'

export function useScene(id: string) {
  const scene = useQuery({ queryKey: ['scenes', 'record', id], queryFn: () => fetchScene(id) })
  // Requested in parallel with the record; a 404 resolves to null (the empty state).
  const draft = useQuery({ queryKey: ['scenes', 'draft', id], queryFn: () => fetchDraft(id) })
  return { scene, draft }
}
