"""Abstract syntax tree definitions for Decaf."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .errors import SourceSpan
from .token import Token


#notes that every AST node tracks a span for diagnostics
@dataclass(slots=True)
class Node:
    span: SourceSpan


# Declarations -----------------------------------------------------------------


#represents the root of the parsed file containing declarations
@dataclass(slots=True)
class Program(Node):
    declarations: List["Declaration"] = field(default_factory=list)


#captures `let`/`var` declarations with mutability and initializer
@dataclass(slots=True)
class VarDecl(Node):
    name: str
    name_span: SourceSpan
    mutable: bool
    initializer: "Expr"


#function parameters are treated like local declarations with spans
@dataclass(slots=True)
class Param(Node):
    name: str
    name_span: SourceSpan


#holds the parsed function signature and body
@dataclass(slots=True)
class FunctionDecl(Node):
    name: str
    name_span: SourceSpan
    params: List[Param] = field(default_factory=list)
    body: "BlockStmt" | None = None


Declaration = VarDecl | FunctionDecl


# Statements -------------------------------------------------------------------


#common base for all statements allowing polymorphic handling
@dataclass(slots=True)
class Stmt(Node):
    pass


#container for zero or more statements with its own scope
@dataclass(slots=True)
class BlockStmt(Stmt):
    statements: List[Stmt] = field(default_factory=list)


#expression statements preserve results solely for side effects
@dataclass(slots=True)
class ExprStmt(Stmt):
    expr: "Expr"


#represents `print` commands in the language
@dataclass(slots=True)
class PrintStmt(Stmt):
    expr: "Expr"


#classic `if` syntax with optional `else` branch
@dataclass(slots=True)
class IfStmt(Stmt):
    condition: "Expr"
    then_branch: Stmt
    else_branch: Stmt | None


#`while` loops hold the condition and body statement
@dataclass(slots=True)
class WhileStmt(Stmt):
    condition: "Expr"
    body: Stmt


#defines explicit returns required in every function
@dataclass(slots=True)
class ReturnStmt(Stmt):
    value: "Expr"


# Expressions ------------------------------------------------------------------


#expressions share the base `Node` to carry spans
@dataclass(slots=True)
class Expr(Node):
    pass


#integer literals store their numeric value directly
@dataclass(slots=True)
class IntLiteral(Expr):
    value: int


#variable references keep both name and span for error reporting
@dataclass(slots=True)
class VarExpr(Expr):
    name: str
    name_span: SourceSpan


#assignment expressions reuse the name span for mutability diagnostics
@dataclass(slots=True)
class AssignExpr(Expr):
    name: str
    name_span: SourceSpan
    value: Expr


#binary operations store operator token to reuse for bytecode mapping
@dataclass(slots=True)
class BinaryExpr(Expr):
    left: Expr
    operator: Token
    right: Expr


#function calls store the callee identifier and positional arguments
@dataclass(slots=True)
class CallExpr(Expr):
    callee: str
    callee_span: SourceSpan
    arguments: List[Expr] = field(default_factory=list)
