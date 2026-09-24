"""A fake three-chapter novel with two versions, to build and check the reader without the
pipeline (spec 014). Fictional people only.

    cd backend
    uv run python -m app.reader.dev_seed            # into HARNESS_DB
    uv run python -m app.reader.dev_seed --db PATH  # into another file

Version 1 names the dog Toby; version 2 is the change "el perro se llama Nala", which
regenerated chapters 1 and 3 (the ones using the pet fact) and copied chapter 2. Both are
published, so the reader's version selector has something to show. Running it twice is
harmless: an existing novel with the same id is left as it is.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Final

from app.bible import BibleRepository

NOVEL_ID: Final[str] = "demo-faro"

_CHAPTERS: Final[list[tuple[str, str]]] = [
    (
        "La llegada al faro",
        (
            "Lucía llegó al faro de Cabo Luz una tarde de viento, con la maleta llena de "
            "libros y {pet} trotando a su lado. El mar golpeaba las rocas con la paciencia de "
            "siempre y las gaviotas dibujaban círculos sobre la torre blanca.\n\n"
            "Nadie la esperaba, pero la puerta estaba abierta. Dentro olía a sal, a madera "
            "vieja y a café recién hecho. {pet} olfateó cada rincón antes de tumbarse junto a "
            "la estufa, como si aquella casa hubiera sido suya desde siempre.\n\n"
            "Aquella noche Lucía subió la escalera de caracol contando los peldaños. Eran "
            "ciento doce. Desde arriba, las luces del pueblo parecían un collar olvidado en "
            "la orilla, y pensó que quizá, por primera vez en mucho tiempo, había llegado a "
            "tiempo a algún sitio."
        ),
    ),
    (
        "El cuaderno azul",
        (
            "Por la mañana encontró el cuaderno azul en un cajón de la cocina. Tenía las "
            "tapas gastadas y una letra inclinada que llenaba cada página de fechas, mareas y "
            "nombres de barcos que ya no existían.\n\n"
            "Lucía leyó durante horas. El antiguo farero había anotado cada tormenta y cada "
            "visita, y entre las cifras aparecían frases sueltas: «hoy el mar está de buen "
            "humor», «ha vuelto la niña del faro de enfrente». Nadie en el pueblo recordaba a "
            "ninguna niña.\n\n"
            "Cuando cerró el cuaderno, el sol ya se ponía sobre Cabo Luz. Decidió que "
            "averiguaría a quién pertenecían aquellas palabras, aunque tuviera que preguntar "
            "puerta por puerta."
        ),
    ),
    (
        "La luz de enfrente",
        (
            "La última noche del verano, {pet} empezó a ladrar hacia el mar. Lucía subió "
            "corriendo a la linterna y la vio: una luz pequeña, al otro lado de la bahía, que "
            "se encendía y se apagaba con un ritmo que no era el de ningún faro.\n\n"
            "Tres destellos largos, uno corto. Lo mismo que el cuaderno azul repetía en su "
            "última página. Lucía encendió la lámpara de mano y respondió, torpe al "
            "principio, segura después.\n\n"
            "La luz de enfrente se quedó fija un instante, como quien sonríe. {pet} dejó de "
            "ladrar y apoyó la cabeza en su rodilla. Abajo, el mar seguía golpeando las "
            "rocas, y Lucía supo que aquel faro ya no era un lugar de paso, sino su casa."
        ),
    ),
]

DEDICATION: Final[str] = (
    "Para Lucía, que siempre encuentra el camino de vuelta.\n\n"
    "Con todo el cariño de quien te espera en la orilla."
)


def seed(repo: BibleRepository, novel_id: str = NOVEL_ID) -> bool:
    """Create the demo novel; False when it already exists."""
    if any(n.id == novel_id for n in repo.list_novels()):
        return False
    repo.create_novel(
        novel_id=novel_id,
        title="La luz de Cabo Luz",
        dedication=DEDICATION,
        recipient_name="Lucía",
    )
    recipient = repo.add_fact(
        novel_id, key="recipient.name", value="Lucía", kind="recipient",
        source="interview", mandatory=True,
    )
    pet = repo.add_fact(
        novel_id, key="pet.toby.name", value="Toby", kind="pet", source="interview",
        mandatory=True,
    )
    place = repo.add_fact(
        novel_id, key="place.cabo-luz", value="Cabo Luz", kind="place", source="interview"
    )
    repo.add_character(
        novel_id, name="Lucía", role="protagonista", birth_date="1990-05-14",
        description="Bibliotecaria curiosa que hereda un faro.", fact_id=recipient.id,
    )
    repo.add_character(
        novel_id, name="Nala", role="mascota",
        description="Perra de aguas, fiel y ladradora (Toby en la versión 1).", fact_id=pet.id,
    )
    repo.add_character(
        novel_id, name="El antiguo farero", role="secundario",
        description="Solo aparece en su cuaderno azul.",
    )
    repo.add_place(
        novel_id, name="Cabo Luz", description="Faro blanco sobre las rocas.", fact_id=place.id
    )
    repo.add_place(novel_id, name="El pueblo", description="Casas bajas junto a la orilla.")

    v1 = repo.create_version(novel_id, note="Primera edición")
    for n, (title, text) in enumerate(_CHAPTERS, start=1):
        repo.save_chapter_and_checkpoint(
            novel_id, v1.version, n, title=title, text=text.format(pet="Toby")
        )
        repo.record_fact_usage(recipient.id, chapter=n, scene=1, version=v1.version)
        repo.record_fact_usage(place.id, chapter=n, scene=1, version=v1.version)
        if "{pet}" in text:
            repo.record_fact_usage(pet.id, chapter=n, scene=1, version=v1.version)
    repo.set_version_status(novel_id, v1.version, "published")

    # Version 2: the reader's change "el perro se llama Nala" (what change_fact produces).
    uses_pet = {n for n, (_, text) in enumerate(_CHAPTERS, start=1) if "{pet}" in text}
    repo.update_fact_value(pet.id, "Nala")
    v2 = repo.create_version_from(
        novel_id, v1.version, copy_chapters_except=uses_pet,
        note="Cambio pedido por el lector: el perro se llama Nala",
    )
    for n in sorted(uses_pet):
        title, text = _CHAPTERS[n - 1]
        repo.save_chapter_and_checkpoint(
            novel_id, v2.version, n, title=title, text=text.format(pet="Nala")
        )
    for n in range(1, len(_CHAPTERS) + 1):
        repo.record_fact_usage(recipient.id, chapter=n, scene=1, version=v2.version)
        repo.record_fact_usage(place.id, chapter=n, scene=1, version=v2.version)
        if n in uses_pet:
            repo.record_fact_usage(pet.id, chapter=n, scene=1, version=v2.version)
    repo.set_version_status(novel_id, v2.version, "published")
    repo.update_novel(novel_id, status="published")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.reader.dev_seed")
    parser.add_argument("--db", type=Path, default=None, help="default: HARNESS_DB")
    parser.add_argument("--novel-id", default=NOVEL_ID)
    args = parser.parse_args(argv)
    with BibleRepository.open(args.db) as repo:
        created = seed(repo, args.novel_id)
    sys.stdout.write(f"{'created' if created else 'already present'}: {args.novel_id}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
