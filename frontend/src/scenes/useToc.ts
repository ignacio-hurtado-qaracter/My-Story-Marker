// The table of contents as server state. Spec 002, FR-SCN-01: two requests, whatever the length
// of the novel, and no per-scene fan-out (Decision R2-3).
import { useQuery } from '@tanstack/react-query'

import { fetchChapters, fetchSceneIds } from './api'
import { buildToc, type Toc } from './toc'

async function fetchToc(): Promise<Toc> {
  const [chapters, sceneIds] = await Promise.all([fetchChapters(), fetchSceneIds()])
  return buildToc(chapters, sceneIds)
}

export function useToc() {
  return useQuery({ queryKey: ['scenes', 'toc'], queryFn: fetchToc })
}
