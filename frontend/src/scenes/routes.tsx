// The routes of scenes/, mounted by app/ at `scenes/*`. Spec 002, FR-SCN, FR-SHELL-02; plan P17.
import { Route, Routes } from 'react-router'

import { ScenePage } from './ScenePage'
import { TocPage } from './TocPage'

export function ScenesRoutes() {
  return (
    <Routes>
      <Route index element={<TocPage />} />
      <Route path=":id" element={<ScenePage />} />
    </Routes>
  )
}
