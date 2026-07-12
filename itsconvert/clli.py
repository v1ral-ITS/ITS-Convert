"""clli — Cross-Language Library Interface for ITS-Convert.

Provides a clean programmatic API for converting scripts between languages
without going through the command-line interface.

    >>> from itsconvert.clli import convert, inspect, languages
    >>> result = convert('print("Hello")', from_lang="py", to_lang="sh")
    >>> print(result)
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Hello"
"""

from __future__ import annotations

from itsconvert.errors import ParseError, UnsupportedConstructError
from itsconvert.translators import (
    available_emitters,
    available_parsers,
    get_emitter,
    get_parser,
)


__all__ = [
    "convert",
    "inspect",
    "languages",
    "ConvertError",
]


class ConvertError(Exception):
    """Raised when a conversion cannot be completed."""


def convert(source: str, from_lang: str, to_lang: str) -> str:
    """Convert *source* code written in *from_lang* into *to_lang*.

    Parameters
    ----------
    source:
        The source code to convert.
    from_lang:
        Language code of the input (e.g. ``"py"``, ``"sh"``, ``"ps1"``).
        Must be one of the supported parsers returned by :func:`languages`.
    to_lang:
        Language code of the desired output (e.g. ``"go"``, ``"rs"``, ``"js"``).
        Must be one of the supported emitters returned by :func:`languages`.

    Returns
    -------
    str
        The converted source code in *to_lang*.

    Raises
    ------
    ConvertError
        If *from_lang* has no parser, *to_lang* has no emitter, or the source
        cannot be parsed.

    Examples
    --------
    >>> code = convert('x = 1\\nprint(x)\\n', from_lang="py", to_lang="sh")
    >>> "echo" in code
    True
    """
    try:
        parser = get_parser(from_lang)
    except UnsupportedConstructError as exc:
        raise ConvertError(str(exc)) from exc

    try:
        emitter = get_emitter(to_lang)
    except UnsupportedConstructError as exc:
        raise ConvertError(str(exc)) from exc

    try:
        ir = parser.parse(source)
    except ParseError as exc:
        raise ConvertError(f"Failed to parse {from_lang!r} source: {exc}") from exc

    return emitter.emit(ir)


def inspect(source: str, lang: str) -> dict:
    """Parse *source* and return its intermediate representation as a dict.

    Parameters
    ----------
    source:
        The source code to inspect.
    lang:
        Language code of the input (e.g. ``"py"``).

    Returns
    -------
    dict
        The :class:`~itsconvert.ir.ScriptIR` serialised via
        ``model_dump()``, containing ``source_language``, ``nodes``, and
        ``warnings``.

    Raises
    ------
    ConvertError
        If *lang* has no parser or the source cannot be parsed.

    Examples
    --------
    >>> ir = inspect('x = 42\\n', lang="py")
    >>> ir["source_language"]
    'py'
    >>> ir["nodes"][0]["type"]
    'assign'
    """
    try:
        parser = get_parser(lang)
    except UnsupportedConstructError as exc:
        raise ConvertError(str(exc)) from exc

    try:
        ir = parser.parse(source)
    except ParseError as exc:
        raise ConvertError(f"Failed to parse {lang!r} source: {exc}") from exc

    return ir.model_dump()


def languages() -> dict[str, list[str]]:
    """Return the supported parser and emitter language codes.

    Returns
    -------
    dict
        A mapping with two keys:

        * ``"parsers"`` — sorted list of source language codes.
        * ``"emitters"`` — sorted list of target language codes.

    Examples
    --------
    >>> info = languages()
    >>> "py" in info["parsers"]
    True
    >>> "go" in info["emitters"]
    True
    """
    return {
        "parsers": available_parsers(),
        "emitters": available_emitters(),
    }
