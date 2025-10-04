"""Common error and source span utilities."""
from __future__ import annotations

from dataclasses import dataclass


#describes an exact line/column position captured during lexing or parsing
@dataclass(frozen=True, slots=True)
class SourceLocation:
    """A 1-based line/column location inside a source file."""

    line: int
    column: int

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.line}:{self.column}"


#stores the start/end positions for highlighting user diagnostics
@dataclass(frozen=True, slots=True)
class SourceSpan:
    """Represents a half-open source range [start, end)."""

    start: SourceLocation
    end: SourceLocation

    def merge(self, other: "SourceSpan") -> "SourceSpan":
        """Return the minimal span that covers both spans."""

        if (self.start.line, self.start.column) <= (other.start.line, other.start.column):
            start = self.start
        else:
            start = other.start

        if (self.end.line, self.end.column) >= (other.end.line, other.end.column):
            end = self.end
        else:
            end = other.end
        return SourceSpan(start=start, end=end)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.start}-{self.end}"


#normalizes the base exception for all compiler/VM layers
class DecafError(Exception):
    """Base class for Decaf-related errors."""


#lexer raises this when encountering invalid characters or tokens
class LexError(DecafError):
    """Raised when the lexer encounters an invalid character sequence."""

    def __init__(self, message: str, span: SourceSpan) -> None:
        super().__init__(message)
        self.span = span
        self.message = message


#parser uses this to surface syntax errors with spans
class ParseError(DecafError):
    """Raised when the parser encounters an invalid construct."""

    def __init__(self, message: str, span: SourceSpan) -> None:
        super().__init__(message)
        self.span = span
        self.message = message


#semantic checks funnel through this to provide context-rich diagnostics
class SemanticError(DecafError):
    """Raised for semantic analysis failures."""

    def __init__(self, message: str, span: SourceSpan) -> None:
        super().__init__(message)
        self.span = span
        self.message = message
