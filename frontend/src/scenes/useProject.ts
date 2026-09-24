// The book's project record as server state, for the book header. Spec 003, FR-BOOK-02.
import { useQuery } from '@tanstack/react-query'

import { fetchProject } from './api'

export function useProject() {
  return useQuery({
    queryKey: ['scenes', 'project'],
    queryFn: fetchProject,
    // The header is optional (FR-BOOK-02): on any failure it is simply omitted. Retrying would
    // only keep its placeholder on screen - for a 404, forever in effect, since no retry can
    // create a project record.
    retry: false,
  })
}
