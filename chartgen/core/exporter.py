"""Interface every output format implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from chartgen.core.model import Chart


class ChartExporter(ABC):
    """Turns a :class:`Chart` into the bytes of one file."""

    file_name: ClassVar[str]

    @abstractmethod
    def render(self, chart: Chart) -> bytes:
        """Return the file content for ``chart``."""

    def export(self, chart: Chart, directory: Path) -> Path:
        """Write ``chart`` into ``directory`` and return the file's path."""
        path = directory / self.file_name
        path.write_bytes(self.render(chart))
        return path
