// The route table, in declarative mode (plan P2). Spec 002, FR-SHELL-01..03.
import { Navigate, Route, Routes } from 'react-router'

import { ScenesRoutes } from '../scenes'
import { Layout } from './Layout'
import { NotFoundPage } from './NotFoundPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/scenes" replace />} />
        {/* Feature routes, each imported only from its feature's index.ts (FR-SHELL-02, P17). */}
        <Route path="scenes/*" element={<ScenesRoutes />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
