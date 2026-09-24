// The routes of bible/, mounted by app/ at `characters/*` and `locations/*`. Spec 003, FR-IA-01,
// FR-BIBLE; plan decision Q8.
import { Route, Routes } from 'react-router'

import { CharacterPage } from './CharacterPage'
import { CharactersPage } from './CharactersPage'
import { LocationPage } from './LocationPage'
import { LocationsPage } from './LocationsPage'

export function CharactersRoutes() {
  return (
    <Routes>
      <Route index element={<CharactersPage />} />
      <Route path=":id" element={<CharacterPage />} />
    </Routes>
  )
}

export function LocationsRoutes() {
  return (
    <Routes>
      <Route index element={<LocationsPage />} />
      <Route path=":id" element={<LocationPage />} />
    </Routes>
  )
}
