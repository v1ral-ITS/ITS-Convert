class ItsConvertError(Exception):
    """Base project exception."""


class UnsupportedConstructError(ItsConvertError):
    """Raised when a source construct is outside v1 scope."""


class ParseError(ItsConvertError):
    """Raised when the source cannot be parsed."""


class PackagingError(ItsConvertError):
    """Raised when packaging fails."""
