# Ejemplos

| Fichero | Qué es |
|---|---|
| `novela-ejemplo.pdf` | Novela completa de 10 capítulos (1.000–1.500 palabras cada uno), exportada a PDF desde el backend, con portada y dedicatoria, índice navegable y ficha de personajes y lugares. Es la evidencia de que el sistema funciona de principio a fin. *Pendiente (bloque B11).* |
| `brief-ejemplo.json` | Copia del brief que la produjo, [`evals/briefs/ejemplo.json`](../evals/briefs/ejemplo.json). Destinatario ficticio. *Pendiente (bloque B11).* |

## Cómo se reproduce

```bash
cd backend
uv run python -m app.novel.cli generate --brief ../evals/briefs/ejemplo.json
```

Después, exportar el PDF de la versión publicada (ver [README raíz](../README.md#leer-la-novela)).
Cuando se añada el PDF, este README anotará el `novel_id`, la versión publicada y el
commit con que se generó.
