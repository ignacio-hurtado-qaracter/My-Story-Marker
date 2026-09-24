// The monograms of the story bible, in main's orange gradient: a round avatar for a character and a
// book-cover tile for a location. Spec 003, FR-BIBLE-02..04. Both are decorative (the name is
// always written next to them), so they are hidden from assistive technology. The gradient stops
// are the dark end of the brand (#E5661F → #AE4E14 → #7C3208): white bold text of at least 20 px
// on them keeps ≥ 3:1 (large text, WCAG 1.4.3).
import './bible.css'

import { initials, locationName } from './names'

export interface AvatarProps {
  name: string
  size?: 'md' | 'lg'
}

export function Avatar({ name, size = 'md' }: AvatarProps) {
  return (
    <span aria-hidden="true" className={`bible-avatar bible-avatar-${size}`}>
      {initials(name)}
    </span>
  )
}

export interface LocationMarkProps {
  id: string
  size?: 'md' | 'lg'
}

export function LocationMark({ id, size = 'md' }: LocationMarkProps) {
  return (
    <span aria-hidden="true" className={`bible-mark bible-mark-${size}`}>
      <span className="bible-mark-letters">{initials(locationName(id))}</span>
    </span>
  )
}
