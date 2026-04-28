"""Tests de integración para escritura atómica."""

import os

import pytest

from delivery_app.infrastructure.atomic_file_io import atomic_write


class TestAtomicWrite:
    def test_creates_file(self, tmp_path):
        path = tmp_path / "test.json"
        atomic_write(path, '{"key": "value"}')
        assert path.exists()
        assert path.read_text(encoding="utf-8") == '{"key": "value"}'

    def test_overwrites_existing(self, tmp_path):
        path = tmp_path / "test.json"
        atomic_write(path, "old content")
        atomic_write(path, "new content")
        assert path.read_text(encoding="utf-8") == "new content"

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "sub" / "dir" / "test.json"
        atomic_write(path, "content")
        assert path.exists()

    def test_no_temp_file_left_on_success(self, tmp_path):
        path = tmp_path / "test.json"
        atomic_write(path, "content")
        # Only the target file should exist
        files = list(tmp_path.iterdir())
        assert len(files) == 1
        assert files[0].name == "test.json"

    def test_no_corruption_on_write_error(self, tmp_path):
        """Si la escritura falla, el archivo original no se corrompe."""
        path = tmp_path / "test.json"
        atomic_write(path, "original content")

        # Simular fallo: pasar un objeto no-string
        with pytest.raises(TypeError):
            atomic_write(path, 12345)  # type: ignore

        # El archivo original debe estar intacto
        assert path.read_text(encoding="utf-8") == "original content"

    def test_unicode_content(self, tmp_path):
        path = tmp_path / "test.json"
        content = '{"nombre": "Bodega Ñoño", "emoji": "🚚"}'
        atomic_write(path, content)
        assert path.read_text(encoding="utf-8") == content
