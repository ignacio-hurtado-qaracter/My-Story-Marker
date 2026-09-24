// The route table, in declarative mode (plan 002 P2). Spec 002, FR-SHELL-01..03; spec 003,
// FR-IA-01 (revision 2): the cover at `/`, the chapter index and reader, the story-bible sheets.
import { Route, Routes } from 'react-router'

import { CharactersRoutes, LocationsRoutes } from '../bible'
import { CoverRoute } from '../cover'
import { Graph3dRoute } from '../graph3d'
import { ChaptersRoutes, ScenesRoutes } from '../scenes'
import { Layout } from './Layout'
import { NotFoundPage } from './NotFoundPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {/* Feature routes, each imported only from its feature's index.ts (FR-SHELL-02, P17). */}
        <Route index element={<CoverRoute />} />
        <Route path="scenes/*" element={<ScenesRoutes />} />
        <Route path="chapters/*" element={<ChaptersRoutes />} />
        <Route path="characters/*" element={<CharactersRoutes />} />
        <Route path="locations/*" element={<LocationsRoutes />} />
        <Route path="graph3d" element={<Graph3dRoute />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
