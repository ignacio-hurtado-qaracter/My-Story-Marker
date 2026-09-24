// The routes of scenes/. Spec 002, FR-SCN, FR-SHELL-02, plan 002 P17; spec 003, FR-IA-01,
// plan 003 Q8. app/ mounts `ScenesRoutes` at `scenes/*` and `ChaptersRoutes` at `chapters/*`.
import { Navigate, Route, Routes } from 'react-router'

import { ChapterPage } from './ChapterPage'
import { ScenePage } from './ScenePage'
import { TocPage } from './TocPage'

/** `/scenes`: the chapter index (FR-INDEX); `/scenes/:id`: one scene (spec 002, unchanged). */
export function ScenesRoutes() {
  return (
    <Routes>
      <Route index element={<TocPage />} />
      <Route path=":id" element={<ScenePage />} />
    </Routes>
  )
}

/** `/chapters/:id`: the chapter reader (FR-READ). `/chapters` alone is the index. */
export function ChaptersRoutes() {
  return (
    <Routes>
      <Route index element={<Navigate to="/scenes" replace />} />
      <Route path=":id" element={<ChapterPage />} />
    </Routes>
  )
}
