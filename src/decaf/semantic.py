"""Semantic analysis for Decaf ASTs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import ast
from .errors import SemanticError, SourceSpan


#bindings describe symbol metadata surfaced during resolution
@dataclass(slots=True)
class VarBinding:
    name: str
    span: SourceSpan
    mutable: bool


#stores global slot index for bytecode generation
@dataclass(slots=True)
class GlobalBinding(VarBinding):
    index: int


#holds function-local index for reads/writes
@dataclass(slots=True)
class LocalBinding(VarBinding):
    index: int


#represents a function symbol plus derived metadata
@dataclass(slots=True)
class FunctionSymbol:
    name: str
    index: int
    arity: int
    decl: ast.FunctionDecl
    locals: List[LocalBinding] = field(default_factory=list)
    max_locals: int = 0


#associates a global declaration with its binding slot
@dataclass(slots=True)
class GlobalVariable:
    decl: ast.VarDecl
    binding: GlobalBinding


#container describing the entire resolved program state
@dataclass(slots=True)
class ResolvedProgram:
    program: ast.Program
    globals: List[GlobalVariable]
    functions: List[FunctionSymbol]
    var_bindings: Dict[int, VarBinding]
    call_targets: Dict[int, FunctionSymbol]


#individual lexical scopes map names to bindings
@dataclass(slots=True)
class _Scope:
    bindings: Dict[str, VarBinding] = field(default_factory=dict)


#tracks function context while traversing statements
@dataclass(slots=True)
class _FunctionContext:
    function: FunctionSymbol
    next_local_index: int


#performs name resolution, arity checks, and mutability enforcement
class Resolver:
    def __init__(self, program: ast.Program) -> None:
        self._program = program
        self._global_scope = _Scope()
        self._globals: List[GlobalVariable] = []
        self._functions: List[FunctionSymbol] = []
        self._functions_by_name: Dict[str, FunctionSymbol] = {}
        self._var_bindings: Dict[int, VarBinding] = {}
        self._call_targets: Dict[int, FunctionSymbol] = {}
        self._scopes: List[_Scope] = []

    def resolve(self) -> ResolvedProgram:
        self._declare_top_level()
        self._scopes = [self._global_scope]
        for global_var in self._globals:
            self._resolve_expr(global_var.decl.initializer, context=None)
        for function in self._functions:
            self._resolve_function(function)
        return ResolvedProgram(
            program=self._program,
            globals=self._globals,
            functions=self._functions,
            var_bindings=self._var_bindings,
            call_targets=self._call_targets,
        )

    #one pass to register globals/functions before resolution begins
    def _declare_top_level(self) -> None:
        for decl in self._program.declarations:
            if isinstance(decl, ast.VarDecl):
                self._declare_global(decl)
            elif isinstance(decl, ast.FunctionDecl):
                self._declare_function(decl)
            else:
                raise AssertionError(f"unexpected declaration {decl!r}")

    #ensures unique global names and records mutable flag
    def _declare_global(self, decl: ast.VarDecl) -> None:
        if decl.name in self._global_scope.bindings or decl.name in self._functions_by_name:
            raise SemanticError(f"duplicate declaration of '{decl.name}'", decl.name_span)
        index = len(self._globals)
        binding = GlobalBinding(name=decl.name, span=decl.name_span, mutable=decl.mutable, index=index)
        self._global_scope.bindings[decl.name] = binding
        self._globals.append(GlobalVariable(decl=decl, binding=binding))
        self._var_bindings[id(decl)] = binding

    #verifies function names do not collide with globals or other functions
    def _declare_function(self, decl: ast.FunctionDecl) -> None:
        if decl.name in self._functions_by_name or decl.name in self._global_scope.bindings:
            raise SemanticError(f"duplicate declaration of '{decl.name}'", decl.name_span)
        index = len(self._functions)
        symbol = FunctionSymbol(name=decl.name, index=index, arity=len(decl.params), decl=decl)
        self._functions.append(symbol)
        self._functions_by_name[decl.name] = symbol

    #performs resolution of parameters, locals, and statements for a function
    def _resolve_function(self, function: FunctionSymbol) -> None:
        context = _FunctionContext(function=function, next_local_index=len(function.decl.params))
        self._scopes = [self._global_scope]
        self._push_scope()
        for position, param in enumerate(function.decl.params):
            binding = LocalBinding(name=param.name, span=param.name_span, mutable=True, index=position)
            self._declare_local(binding)
            function.locals.append(binding)
        self._resolve_block(function.decl.body, context)
        self._pop_scope()
        function.max_locals = max((binding.index for binding in function.locals), default=-1) + 1
        if not self._guarantees_return(function.decl.body):
            raise SemanticError(f"function '{function.name}' may exit without returning", function.decl.span)

    #enters a new lexical scope for block statements
    def _resolve_block(self, block: ast.BlockStmt, context: _FunctionContext) -> None:
        self._push_scope()
        for stmt in block.statements:
            self._resolve_stmt(stmt, context)
        self._pop_scope()

    #dispatches to the appropriate resolver based on statement type
    def _resolve_stmt(self, stmt: ast.Stmt, context: _FunctionContext) -> None:
        if isinstance(stmt, ast.VarDecl):
            self._resolve_local_var(stmt, context)
        elif isinstance(stmt, ast.BlockStmt):
            self._resolve_block(stmt, context)
        elif isinstance(stmt, ast.ExprStmt):
            self._resolve_expr(stmt.expr, context)
        elif isinstance(stmt, ast.PrintStmt):
            self._resolve_expr(stmt.expr, context)
        elif isinstance(stmt, ast.IfStmt):
            self._resolve_if(stmt, context)
        elif isinstance(stmt, ast.WhileStmt):
            self._resolve_while(stmt, context)
        elif isinstance(stmt, ast.ReturnStmt):
            self._resolve_expr(stmt.value, context)
        else:
            raise AssertionError(f"unexpected statement {stmt!r}")

    #resolves both branches of an if statement
    def _resolve_if(self, stmt: ast.IfStmt, context: _FunctionContext) -> None:
        self._resolve_expr(stmt.condition, context)
        self._resolve_stmt(stmt.then_branch, context)
        if stmt.else_branch is not None:
            self._resolve_stmt(stmt.else_branch, context)

    #validates loop body and condition
    def _resolve_while(self, stmt: ast.WhileStmt, context: _FunctionContext) -> None:
        self._resolve_expr(stmt.condition, context)
        self._resolve_stmt(stmt.body, context)

    #allocates a new local slot and records its binding
    def _resolve_local_var(self, decl: ast.VarDecl, context: _FunctionContext) -> None:
        self._resolve_expr(decl.initializer, context)
        index = context.next_local_index
        context.next_local_index += 1
        binding = LocalBinding(name=decl.name, span=decl.name_span, mutable=decl.mutable, index=index)
        self._declare_local(binding)
        self._var_bindings[id(decl)] = binding
        context.function.locals.append(binding)

    #performs identifier lookup, immutability checks, and call validation
    def _resolve_expr(self, expr: ast.Expr, context: Optional[_FunctionContext]) -> None:
        if isinstance(expr, ast.IntLiteral):
            return
        if isinstance(expr, ast.VarExpr):
            binding = self._lookup(expr.name)
            if binding is None:
                raise SemanticError(f"undeclared variable '{expr.name}'", expr.name_span)
            self._var_bindings[id(expr)] = binding
            return
        if isinstance(expr, ast.AssignExpr):
            binding = self._lookup(expr.name)
            if binding is None:
                raise SemanticError(f"undeclared variable '{expr.name}'", expr.name_span)
            if not binding.mutable:
                raise SemanticError(f"cannot assign to immutable variable '{expr.name}'", expr.name_span)
            self._resolve_expr(expr.value, context)
            self._var_bindings[id(expr)] = binding
            return
        if isinstance(expr, ast.BinaryExpr):
            self._resolve_expr(expr.left, context)
            self._resolve_expr(expr.right, context)
            return
        if isinstance(expr, ast.CallExpr):
            symbol = self._functions_by_name.get(expr.callee)
            if symbol is None:
                raise SemanticError(f"unknown function '{expr.callee}'", expr.callee_span)
            if len(expr.arguments) != symbol.arity:
                raise SemanticError(
                    f"function '{expr.callee}' expects {symbol.arity} argument(s), got {len(expr.arguments)}",
                    expr.callee_span,
                )
            for argument in expr.arguments:
                self._resolve_expr(argument, context)
            self._call_targets[id(expr)] = symbol
            return
        raise AssertionError(f"unexpected expression {expr!r}")

    #manages the scope stack whenever we enter or leave a block
    def _push_scope(self) -> None:
        self._scopes.append(_Scope())

    def _pop_scope(self) -> None:
        self._scopes.pop()

    #adds local bindings to the current scope
    def _declare_local(self, binding: LocalBinding) -> None:
        self._scopes[-1].bindings[binding.name] = binding

    #nested lookup walking from innermost scope outwards
    def _lookup(self, name: str) -> Optional[VarBinding]:
        for scope in reversed(self._scopes):
            binding = scope.bindings.get(name)
            if binding is not None:
                return binding
        return self._global_scope.bindings.get(name)

    #ensures every function concludes with a return statement statically
    def _guarantees_return(self, block: ast.BlockStmt) -> bool:
        if not block.statements:
            return False
        return self._stmt_guarantees_return(block.statements[-1])

    #nested helper for `guarantees_return`
    def _stmt_guarantees_return(self, stmt: ast.Stmt) -> bool:
        if isinstance(stmt, ast.ReturnStmt):
            return True
        if isinstance(stmt, ast.BlockStmt):
            if not stmt.statements:
                return False
            return self._stmt_guarantees_return(stmt.statements[-1])
        if isinstance(stmt, ast.IfStmt):
            if stmt.else_branch is None:
                return False
            return self._stmt_guarantees_return(stmt.then_branch) and self._stmt_guarantees_return(stmt.else_branch)
        return False
