"""Base classes for Intent models."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..state import ConnectionState


class Hashable:
    """Mixin providing equality and hashing based on snowflake ID."""

    __slots__ = ()

    id: str

    def __eq__(self, other: Any) -> bool:
        """Check equality based on ID."""
        return isinstance(other, self.__class__) and self.id == other.id

    def __hash__(self) -> int:
        """Hash based on ID."""
        return hash(self.id)


class StatefulModel(Hashable):
    """Base model with state reference."""

    __slots__ = ("_state",)

    def __init__(self, *, state: ConnectionState) -> None:
        self._state = state
