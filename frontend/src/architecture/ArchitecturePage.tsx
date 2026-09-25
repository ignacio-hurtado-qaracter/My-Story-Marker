// `/arquitectura`: "Cómo funciona", the harness drawn as a diagram of 12 nodes (spec 019).
// Each node is a button; the selected one (or the hovered one) is explained in the panel.
// Desktop: positioned boxes over an SVG of arrows, both in the same 1000 × 500 space.
// Phone: the boxes stack in flow order and the panel opens right below the selected one.
import './architecture.css'

import type { CSSProperties } from 'react'
import { useState } from 'react'

import { Heading } from '../shared/ui'
import { EDGES, KIND_LABEL, NODE_H, NODE_W, NODES, VIEW_H, VIEW_W } from './nodes'
import type { ArchNode, NodeKind } from './nodes'

const PANEL_ID = 'arch-panel'
const LEGEND: readonly (readonly [NodeKind, string])[] = Object.entries(KIND_LABEL) as [NodeKind, string][]

function pct(value: number, total: number): string {
  return `${String((value / total) * 100)}%`
}

function nodeStyle(node: ArchNode, index: number): CSSProperties {
  return {
    left: pct(node.x - NODE_W / 2, VIEW_W),
    top: pct(node.y - NODE_H / 2, VIEW_H),
    width: pct(NODE_W, VIEW_W),
    height: pct(NODE_H, VIEW_H),
    // Phone layout: nodes at even orders, the panel right after the selected one.
    order: index * 10,
  }
}

function NodePanel({ node, order }: { node: ArchNode; order: number }) {
  return (
    <aside id={PANEL_ID} className="arch-panel card" style={{ order }} aria-live="polite" aria-labelledby="arch-panel-title">
      <p className={`arch-kind arch-kind-${node.kind}`}>{KIND_LABEL[node.kind]}</p>
      <h2 id="arch-panel-title" className="arch-panel-title">
        {node.name}
      </h2>
      <p className="arch-panel-text">{node.explanation}</p>
      <dl className="arch-panel-facts">
        <dt>Lee</dt>
        <dd>{node.reads}</dd>
        <dt>Escribe</dt>
        <dd>{node.writes}</dd>
        <dt>Validadores</dt>
        <dd>
          {node.validators.length === 0 ? (
            'Ninguno: es donde se guardan sus resultados.'
          ) : (
            <ul className="arch-chips">
              {node.validators.map((name) => (
                <li key={name}>
                  <code>{name}</code>
                </li>
              ))}
            </ul>
          )}
        </dd>
        <dt>Código</dt>
        <dd>
          <ul className="arch-paths">
            {node.code.map((path) => (
              <li key={path}>
                <code>{path}</code>
              </li>
            ))}
          </ul>
        </dd>
      </dl>
    </aside>
  )
}

export function ArchitecturePage() {
  const [selectedId, setSelectedId] = useState<string>(NODES[0]?.id ?? '')
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  const shownId = hoveredId ?? selectedId
  const shownIndex = Math.max(
    0,
    NODES.findIndex((node) => node.id === shownId),
  )
  const shown = NODES.find((_node, index) => index === shownIndex)
  const firstSide = NODES.findIndex((node) => node.step === null)

  return (
    <section className="arch-page">
      <title>Cómo funciona · My Story Marker</title>
      <div className="arch-hero">
        <p className="eyebrow">Cómo funciona</p>
        <Heading>De la entrevista al libro</Heading>
        <p className="arch-lead">
          El harness entrevista a quien regala, planifica una novela de 10 capítulos, la escribe escena a escena,
          la valida y prueba su cronología antes de publicarla. Pulsa un paso para ver qué hace.
        </p>
        <ul className="arch-legend" aria-label="Leyenda">
          {LEGEND.map(([kind, label]) => (
            <li key={kind}>
              <span className={`arch-swatch arch-node-${kind}`} aria-hidden="true" />
              {label}
            </li>
          ))}
        </ul>
      </div>

      <div className="arch-layout">
        <div className="arch-canvas" role="group" aria-label="Diagrama del harness" onMouseLeave={() => { setHoveredId(null) }}>
          <svg className="arch-edges" viewBox={`0 0 ${String(VIEW_W)} ${String(VIEW_H)}`} aria-hidden="true" focusable="false">
            <defs>
              <marker id="arch-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" className="arch-arrowhead" />
              </marker>
            </defs>
            {EDGES.map((edge) => (
              <g key={edge.id}>
                <path
                  d={edge.d}
                  className={['arch-edge', edge.flow ? 'arch-edge-flow' : '', edge.dashed === true ? 'arch-edge-dashed' : '']
                    .filter(Boolean)
                    .join(' ')}
                  markerEnd="url(#arch-arrow)"
                  markerStart={edge.both === true ? 'url(#arch-arrow)' : undefined}
                />
                {edge.label === undefined ? null : (
                  <text x={edge.label.x} y={edge.label.y} className="arch-edge-label" textAnchor="middle">
                    {edge.label.text}
                  </text>
                )}
              </g>
            ))}
          </svg>
          {NODES.map((node, index) => {
            const isShown = node.id === shownId
            return (
              <button
                key={node.id}
                type="button"
                className={`arch-node arch-node-${node.kind}${node.step === null ? ' arch-node-side' : ''}${isShown ? ' is-active' : ''}`}
                style={nodeStyle(node, index)}
                aria-label={`${node.name}: ${KIND_LABEL[node.kind]}${node.step === null ? '' : `, paso ${String(node.step)}`}`}
                aria-pressed={node.id === selectedId}
                aria-controls={PANEL_ID}
                data-last={node.step === 9 ? 'true' : undefined}
                onClick={() => {
                  setSelectedId(node.id)
                  setHoveredId(null)
                }}
                onFocus={() => {
                  setSelectedId(node.id)
                }}
                onMouseEnter={() => {
                  setHoveredId(node.id)
                }}
              >
                {node.step === null ? null : (
                  <span className="arch-step" aria-hidden="true">
                    {node.step}
                  </span>
                )}
                <span className="arch-node-text">
                  <span className="arch-node-name">{node.name}</span>
                  <span className="arch-node-tagline">{node.tagline}</span>
                </span>
              </button>
            )
          })}
          <p className="arch-side-label" style={{ order: firstSide * 10 - 5 }}>
            Alrededor del flujo
          </p>
        </div>
        {shown === undefined ? null : <NodePanel node={shown} order={shownIndex * 10 + 5} />}
      </div>
    </section>
  )
}
