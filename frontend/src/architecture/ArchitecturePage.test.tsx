// "Cómo funciona" (spec 019): every node is a focusable button, and activating one explains it.
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '../../test/render'
import { ArchitecturePage } from './ArchitecturePage'
import { NODES } from './nodes'

describe('ArchitecturePage (spec 019)', () => {
  // spec 019 / AC 1
  it('renders every node as a labelled button', () => {
    renderWithProviders(<ArchitecturePage />, { route: '/arquitectura' })
    const diagram = screen.getByRole('group', { name: 'Diagrama del harness' })
    const buttons = within(diagram).getAllByRole('button')
    expect(buttons).toHaveLength(NODES.length)
    expect(NODES.length).toBeGreaterThanOrEqual(9)
    for (const button of buttons) {
      expect(button).toHaveAttribute('aria-label')
      expect(button.tabIndex).toBe(0)
    }
  })

  // spec 019 / AC 1
  it('explains the node that is activated, with what it reads, writes, validates and where it lives', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ArchitecturePage />, { route: '/arquitectura' })
    await user.click(screen.getByRole('button', { name: /^Validadores: Verificación formal/ }))
    const panel = screen.getByRole('complementary')
    expect(within(panel).getByRole('heading', { level: 2, name: 'Validadores' })).toBeInTheDocument()
    expect(within(panel).getByText(/Lean 4/)).toBeInTheDocument()
    expect(within(panel).getByText('lean_chronology')).toBeInTheDocument()
    expect(within(panel).getByText('backend/app/formal/lean_runner.py')).toBeInTheDocument()
    expect(within(panel).getByText('Lee')).toBeInTheDocument()
    expect(within(panel).getByText('Escribe')).toBeInTheDocument()

    // Keyboard: tabbing to another node selects it.
    await user.tab()
    expect(screen.getByRole('button', { name: /^Publicación/ })).toHaveAttribute('aria-pressed', 'true')
    expect(within(screen.getByRole('complementary')).getByRole('heading', { level: 2, name: 'Publicación' })).toBeInTheDocument()
  })

  // spec 019 / AC 1: each explanation stays short.
  it('keeps every explanation within 80 words', () => {
    for (const node of NODES) {
      expect(node.explanation.split(/\s+/).length, node.id).toBeLessThanOrEqual(80)
    }
  })
})
