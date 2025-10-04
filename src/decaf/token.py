"""Token definitions for the Decaf language."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Final, Optional

from .errors import SourceSpan


#enumerates every lexical category produced by the lexer
class TokenType(Enum):
    # Single-character tokens
    LEFT_PAREN = auto()
    RIGHT_PAREN = auto()
    LEFT_BRACE = auto()
    RIGHT_BRACE = auto()
    COMMA = auto()
    SEMICOLON = auto()

    # One or two character tokens
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    EQUAL = auto()

    # Literals and identifiers
    IDENTIFIER = auto()
    INTEGER = auto()

    # Keywords
    LET = auto()
    VAR = auto()
    FN = auto()
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    RETURN = auto()
    PRINT = auto()

    EOF = auto()


#normalized keyword lookup so the lexer can emit keyword tokens quickly
KEYWORDS: Final[dict[str, TokenType]] = {
    "let": TokenType.LET,
    "var": TokenType.VAR,
    "fn": TokenType.FN,
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "while": TokenType.WHILE,
    "return": TokenType.RETURN,
    "print": TokenType.PRINT,
}


#encapsulates the lexeme string, token kind, literal value, and span
@dataclass(slots=True)
class Token:
    type: TokenType
    lexeme: str
    span: SourceSpan
    literal: Optional[int] = None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Token({self.type}, {self.lexeme!r}, {self.span})"
