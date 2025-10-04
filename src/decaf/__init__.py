"""Decaf: a tiny bytecode-compiled language."""

#makes package exports explicit for downstream imports
from . import ast, compiler, disasm, lexer, parser, semantic, token, vm

__all__ = [
    "ast",
    "compiler",
    "disasm",
    "lexer",
    "parser",
    "semantic",
    "token",
    "vm",
]
