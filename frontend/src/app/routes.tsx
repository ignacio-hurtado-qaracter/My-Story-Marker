// The route table, in declarative mode (plan 002 P2). Spec 002, FR-SHELL-01..03; spec 003,
// FR-IA-01; spec 014: `/` lists the novels, `/novelas/:novelId/...` is the gift-novel reader
// (cover, index, chapter, character and place sheets). The legacy harness pages stay reachable.
// Spec 018: `/login` logs in or registers.
import { Route, Routes } from 'react-router'

import { ArchitectureRoute } from '../architecture'
import { LoginRoute } from '../auth'
import { BibleRoute } from '../bible'
import { CoverRoute } from '../cover'
import { Graph3dRoute } from '../graph3d'
import { ChapterIndexRoute, ChapterRoute, NovelsRoute, ReaderRoute } from '../reader'
import { ChaptersRoutes, ScenesRoutes } from '../scenes'
import { Layout } from './Layout'
import { NotFoundPage } from './NotFoundPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {/* Feature routes, each imported only from its feature's index.ts (FR-SHELL-02, P17). */}
        <Route index element={<NovelsRoute />} />
        <Route path="login" element={<LoginRoute />} />
        <Route path="arquitectura" element={<ArchitectureRoute />} />
        <Route path="novelas/:novelId" element={<ReaderRoute />}>
          <Route index element={<CoverRoute />} />
          <Route path="indice" element={<ChapterIndexRoute />} />
          <Route path="capitulos/:n" element={<ChapterRoute />} />
          <Route path="personajes" element={<BibleRoute />} />
        </Route>
        <Route path="scenes/*" element={<ScenesRoutes />} />
        <Route path="chapters/*" element={<ChaptersRoutes />} />
        <Route path="graph3d" element={<Graph3dRoute />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
