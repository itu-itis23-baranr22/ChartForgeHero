"""Errors the CLI reports as a clean message instead of a traceback."""


class ChartgenError(Exception):
    """Base class for expected, user-facing failures."""


class AudioLoadError(ChartgenError):
    """The input file is missing, unsupported or unreadable."""


class SeparationError(ChartgenError):
    """Stem separation failed or its dependencies are missing."""


class PackagingError(ChartgenError):
    """The song folder could not be written or failed its audio checks."""


class NoPlayableInstrumentError(ChartgenError):
    """No requested instrument produced a chart, so the song would be unplayable."""


class ChartValidationError(ChartgenError):
    """A generated chart or song folder failed validation."""
