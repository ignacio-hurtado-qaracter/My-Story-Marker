// `/scenes/:id`: one scene's record and its prose. Spec 002, FR-SCN route table, FR-SCN-02,
// FR-SCN-03, FR-SCN-06, AC 9.
import { Link, useParams } from 'react-router'

import type { Schemas } from '../shared/api'
import { ErrorPanel, Heading } from '../shared/ui'
import { describeError, isNotFoundError, isSceneId } from './api'
import { Prose } from './Prose'
import { Skeleton } from './Skeleton'
import { neighbours } from './toc'
import { useScene } from './useScene'
import { useToc } from './useToc'

export function ScenePage() {
  const { id = '' } = useParams()
  // FR-SCN-06: a malformed id is not-found without a request. The hooks that fetch live in
  // SceneView, so they are never called for it.
  return isSceneId(id) ? <SceneView id={id} /> : <SceneNotFound />
}

function SceneNotFound() {
  return (
    <section>
      <title>Escena no encontrada · My Story Marker</title>
      <Heading>Escena no encontrada</Heading>
      <p>No existe ninguna escena con ese identificador.</p>
      <Link to="/scenes">Volver al índice</Link>
    </section>
  )
}

function SceneView({ id }: { id: string }) {
  const { scene, draft } = useScene(id)
  const toc = useToc()

  if (scene.isPending) {
    return <Skeleton />
  }
  // A missing scene is not-found whatever its draft request is doing.
  if (scene.error !== null) {
    if (isNotFoundError(scene.error)) {
      return <SceneNotFound />
    }
    return (
      <ErrorPanel
        message={describeError(scene.error)}
        onRetry={() => {
          void scene.refetch()
          void draft.refetch()
        }}
      />
    )
  }
  if (draft.isPending) {
    return <Skeleton />
  }
  if (draft.error !== null) {
    return (
      <ErrorPanel
        message={describeError(draft.error)}
        onRetry={() => {
          void draft.refetch()
        }}
      />
    )
  }

  // Previous/next need the table of contents; while it loads or if it fails, they are omitted.
  const { previous, next } = toc.data === undefined ? {} : neighbours(toc.data, id)
  return (
    <article>
      <title>{`Escena ${id} · My Story Marker`}</title>
      <Heading>Escena {id}</Heading>
      <SceneHeadline scene={scene.data} />
      {draft.data === null ? (
        <p>Esta escena aún no tiene borrador</p>
      ) : (
        <>
          <p className="words">{draft.data.words} palabras</p>
          <Prose markdown={draft.data.body} />
        </>
      )}
      <nav aria-label="Escenas vecinas">
        {previous === undefined ? null : (
          <Link to={`/scenes/${previous}`} rel="prev">
            Anterior: {previous}
          </Link>
        )}
        {next === undefined ? null : (
          <Link to={`/scenes/${next}`} rel="next">
            Siguiente: {next}
          </Link>
        )}
        <Link to="/scenes">Índice</Link>
      </nav>
    </article>
  )
}

function SceneHeadline({ scene }: { scene: Schemas['Scene'] }) {
  return (
    <dl className="scene-headline">
      <dt>Punto de vista</dt>
      <dd>{scene.pov}</dd>
      <dt>Lugar</dt>
      <dd>{scene.location}</dd>
      <dt>Tiempo de la historia</dt>
      <dd>{scene.story_time}</dd>
      <dt>Objetivo</dt>
      <dd>{scene.goal}</dd>
      <dt>Conflicto</dt>
      <dd>{scene.conflict}</dd>
      <dt>Desenlace</dt>
      <dd>{scene.outcome}</dd>
    </dl>
  )
}
