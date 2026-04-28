"""Componentes reusables de UI."""

from __future__ import annotations

from typing import Any

from prefab_ui.actions import SetState
from prefab_ui.components import Button


def nav_button(label: str, page: str, **kwargs: Any) -> Button:
    """Crea un botón de navegación que cambia de página via SetState."""
    return Button(label, on_click=SetState("page", page), **kwargs)


def back_button() -> Button:
    """Botón estándar para volver al dashboard."""
    return nav_button("← Volver al Dashboard", "dashboard", variant="outline")
