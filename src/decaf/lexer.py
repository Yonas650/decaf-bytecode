"""Lexical analysis for the Decaf language."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .errors import LexError, SourceLocation, SourceSpan
from .token import KEYWORDS, Token, TokenType


#transforms raw characters into a stream of tokens consumed by the parser
@dataclass(slots=True)
class Lexer:
    source: str
    _length: int = field(init=False)
    _index: int = field(init=False, default=0)
    _line: int = field(init=False, default=1)
    _column: int = field(init=False, default=1)

    def __post_init__(self) -> None:
        self._length = len(self.source)
        self._index = 0
        self._line = 1
        self._column = 1

    def lex(self) -> List[Token]:
        tokens: List[Token] = []
        while not self._is_at_end():
            self._skip_whitespace()
            if self._is_at_end():
                break

            start_loc = self._current_location()
            char = self._advance()

            if char.isalpha() or char == "_":
                token = self._identifier(start_loc, char)
                tokens.append(token)
                continue

            if char.isdigit():
                token = self._number(start_loc, char)
                tokens.append(token)
                continue

            match char:
                case "(":
                    tokens.append(self._simple_token(TokenType.LEFT_PAREN, start_loc))
                case ")":
                    tokens.append(self._simple_token(TokenType.RIGHT_PAREN, start_loc))
                case "{":
                    tokens.append(self._simple_token(TokenType.LEFT_BRACE, start_loc))
                case "}":
                    tokens.append(self._simple_token(TokenType.RIGHT_BRACE, start_loc))
                case ",":
                    tokens.append(self._simple_token(TokenType.COMMA, start_loc))
                case ";":
                    tokens.append(self._simple_token(TokenType.SEMICOLON, start_loc))
                case "+":
                    tokens.append(self._simple_token(TokenType.PLUS, start_loc))
                case "-":
                    tokens.append(self._simple_token(TokenType.MINUS, start_loc))
                case "*":
                    tokens.append(self._simple_token(TokenType.STAR, start_loc))
                case "/":
                    if self._match("/"):
                        self._line_comment()
                    else:
                        tokens.append(self._simple_token(TokenType.SLASH, start_loc))
                case "=":
                    tokens.append(self._simple_token(TokenType.EQUAL, start_loc))
                case _:
                    span = SourceSpan(start=start_loc, end=self._current_location())
                    raise LexError(f"unexpected character {char!r}", span)

        eof_loc = self._current_location()
        tokens.append(
            Token(
                type=TokenType.EOF,
                lexeme="",
                span=SourceSpan(start=eof_loc, end=eof_loc),
            )
        )
        return tokens

    # Internal helpers -------------------------------------------------

    def _is_at_end(self) -> bool:
        return self._index >= self._length

    def _current_location(self) -> SourceLocation:
        return SourceLocation(line=self._line, column=self._column)

    def _advance(self) -> str:
        char = self.source[self._index]
        self._index += 1
        if char == "\n":
            self._line += 1
            self._column = 1
        else:
            self._column += 1
        return char

    def _peek(self) -> str:
        if self._is_at_end():
            return "\0"
        return self.source[self._index]

    def _match(self, expected: str) -> bool:
        if self._is_at_end():
            return False
        if self.source[self._index] != expected:
            return False
        self._advance()
        return True

    def _skip_whitespace(self) -> None:
        while not self._is_at_end():
            char = self._peek()
            if char in " \r\t":
                self._advance()
            elif char == "\n":
                self._advance()
            else:
                break

    def _simple_token(self, token_type: TokenType, start: SourceLocation) -> Token:
        end = self._current_location()
        lexeme = self.source[self._index - 1 : self._index]
        return Token(token_type, lexeme, SourceSpan(start=start, end=end))

    def _identifier(self, start: SourceLocation, first_char: str) -> Token:
        start_index = self._index - 1
        while True:
            char = self._peek()
            if char.isalnum() or char == "_":
                self._advance()
            else:
                break
        lexeme = self.source[start_index:self._index]
        token_type = KEYWORDS.get(lexeme, TokenType.IDENTIFIER)
        end = self._current_location()
        return Token(token_type, lexeme, SourceSpan(start=start, end=end))

    def _number(self, start: SourceLocation, first_char: str) -> Token:
        start_index = self._index - 1
        while self._peek().isdigit():
            self._advance()
        lexeme = self.source[start_index:self._index]
        value = int(lexeme)
        end = self._current_location()
        return Token(TokenType.INTEGER, lexeme, SourceSpan(start=start, end=end), literal=value)

    def _line_comment(self) -> None:
        while not self._is_at_end() and self._peek() != "\n":
            self._advance()
