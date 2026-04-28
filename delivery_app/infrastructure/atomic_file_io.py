"""Escritura atómica de archivos.

Escribe en un archivo temporal y luego renombra (os.replace),
que es atómico en la mayoría de sistemas de archivos (NTFS, ext4).
Esto previene corrupción si el proceso se interrumpe a medio escribir.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Escribe contenido en un archivo de forma atómica.

    Estrategia: escribe en un archivo temporal en el mismo directorio
    y luego lo renombra al destino. os.replace() es atómico en NTFS
    y ext4, lo que garantiza que el archivo destino nunca quede
    parcialmente escrito.

    Args:
        path: Ruta destino del archivo.
        content: Contenido a escribir.
        encoding: Codificación del archivo.

    Raises:
        OSError: Si falla la escritura o el rename.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Crear temp file en el mismo directorio para que os.replace funcione
    # (mismo filesystem = rename atómico garantizado)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(path))
    except BaseException:
        # Limpiar el temporal si algo falla
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
