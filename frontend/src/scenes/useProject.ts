// The book's project record as server state, for the book header. Spec 003, FR-BOOK-02.
import { useQuery } from '@tanstack/react-query'

import { fetchProject } from './api'

export function useProject() {
  return useQuery({ queryKey: ['scenes', 'project'], queryFn: fetchProject })
}
