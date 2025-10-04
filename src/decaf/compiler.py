"""Lower the resolved AST into bytecode chunks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from . import ast
from .chunk import BytecodeFunction, BytecodeProgram, Chunk
from .opcodes import OpCode
from .semantic import GlobalBinding, LocalBinding, Resolver, ResolvedProgram, VarBinding


#unused placeholder kept for clarity when extending contexts later on
@dataclass(slots=True)
class _CompilationContext:
    function: Optional[BytecodeFunction]
    chunk: Chunk


#walks the resolved AST and emits bytecode instructions
class Compiler:
    def __init__(self, resolved: ResolvedProgram) -> None:
        self.resolved = resolved
        self.functions: List[Optional[BytecodeFunction]] = [None] * len(resolved.functions)
        self._current_chunk: Chunk | None = None
        self._current_function_symbol = None
        self._line_cache: Dict[int, int] = {}

    @classmethod
    def from_program(cls, program: ast.Program) -> BytecodeProgram:
        resolved = Resolver(program).resolve()
        return cls(resolved).compile()

    def compile(self) -> BytecodeProgram:
        for symbol in self.resolved.functions:
            compiled = self._compile_function(symbol)
            self.functions[symbol.index] = compiled
        entry_fn = self._compile_entry_function()
        functions: List[BytecodeFunction] = [fn for fn in self.functions if fn is not None]
        entry_index = len(functions)
        functions.append(entry_fn)
        globals_init = [0 for _ in self.resolved.globals]
        return BytecodeProgram(functions=functions, globals=globals_init, entry_index=entry_index)

    # Function compilation -----------------------------------------------------

    #compiles user-defined function bodies into independent chunks
    def _compile_function(self, symbol) -> BytecodeFunction:
        chunk = Chunk()
        prev_chunk = self._current_chunk
        prev_symbol = self._current_function_symbol
        self._current_chunk = chunk
        self._current_function_symbol = symbol
        self._compile_block(symbol.decl.body)
        self._current_chunk = prev_chunk
        self._current_function_symbol = prev_symbol
        return BytecodeFunction(
            name=symbol.name,
            chunk=chunk,
            arity=symbol.arity,
            num_locals=symbol.max_locals,
        )

    #entry chunk initializes globals then calls `main`
    def _compile_entry_function(self) -> BytecodeFunction:
        chunk = Chunk()
        prev_chunk = self._current_chunk
        self._current_chunk = chunk
        for global_var in self.resolved.globals:
            self._compile_expr(global_var.decl.initializer)
            self._emit_store_global(global_var.binding.index, global_var.decl.span.start.line)
        main_symbol = next((fn for fn in self.resolved.functions if fn.name == "main"), None)
        if main_symbol is None:
            raise RuntimeError("entry point 'main' is missing")
        line = main_symbol.decl.span.start.line
        self._emit_call(main_symbol.index, len(main_symbol.decl.params), line)
        self._emit(OpCode.POP, line)
        self._emit(OpCode.HALT, line)
        self._current_chunk = prev_chunk
        return BytecodeFunction(name="<entry>", chunk=chunk, arity=0, num_locals=0)

    # Statement compilation ----------------------------------------------------

    #walks statements in order to generate correct control flow
    def _compile_block(self, block: ast.BlockStmt) -> None:
        for stmt in block.statements:
            self._compile_stmt(stmt)

    def _compile_stmt(self, stmt: ast.Stmt) -> None:
        if isinstance(stmt, ast.VarDecl):
            self._compile_var_decl(stmt)
        elif isinstance(stmt, ast.BlockStmt):
            self._compile_block(stmt)
        elif isinstance(stmt, ast.ExprStmt):
            self._compile_expr(stmt.expr)
            self._emit(OpCode.POP, stmt.span.start.line)
        elif isinstance(stmt, ast.PrintStmt):
            self._compile_expr(stmt.expr)
            self._emit(OpCode.PRINT, stmt.span.start.line)
        elif isinstance(stmt, ast.IfStmt):
            self._compile_if(stmt)
        elif isinstance(stmt, ast.WhileStmt):
            self._compile_while(stmt)
        elif isinstance(stmt, ast.ReturnStmt):
            self._compile_expr(stmt.value)
            self._emit(OpCode.RET, stmt.span.start.line)
        else:
            raise AssertionError(f"unknown statement {stmt!r}")

    #global/local declarations share initializer logic, differ on storage op
    def _compile_var_decl(self, decl: ast.VarDecl) -> None:
        binding = self._binding_for_node(decl)
        self._compile_expr(decl.initializer)
        line = decl.span.start.line
        if isinstance(binding, LocalBinding):
            self._emit_store_local(binding.index, line)
        elif isinstance(binding, GlobalBinding):
            self._emit_store_global(binding.index, line)
        else:
            raise AssertionError("unexpected binding type")

    #generates branch targets for both `if` and optional `else`
    def _compile_if(self, stmt: ast.IfStmt) -> None:
        line = stmt.span.start.line
        self._compile_expr(stmt.condition)
        jump_else = self._emit_jump(OpCode.JMP_IF_FALSE, line)
        self._compile_stmt(stmt.then_branch)
        jump_end = None
        if stmt.else_branch is not None:
            jump_end = self._emit_jump(OpCode.JMP, line)
        self._patch_jump(jump_else)
        if stmt.else_branch is not None:
            self._compile_stmt(stmt.else_branch)
            if jump_end is not None:
                self._patch_jump(jump_end)
        else:
            if jump_end is not None:
                self._patch_jump(jump_end)

    #implements loop start/end patching for `while`
    def _compile_while(self, stmt: ast.WhileStmt) -> None:
        line = stmt.span.start.line
        loop_start = self._current_offset
        self._compile_expr(stmt.condition)
        exit_jump = self._emit_jump(OpCode.JMP_IF_FALSE, line)
        self._compile_stmt(stmt.body)
        self._emit_loop(loop_start, line)
        self._patch_jump(exit_jump)

    # Expression compilation ---------------------------------------------------

    #expression compilation is recursive and stack-based
    def _compile_expr(self, expr: ast.Expr) -> None:
        if isinstance(expr, ast.IntLiteral):
            index = self._current_chunk.add_constant(expr.value)
            self._emit(OpCode.PUSH_CONST, expr.span.start.line)
            self._emit_u16(index, expr.span.start.line)
        elif isinstance(expr, ast.VarExpr):
            binding = self._binding_for_node(expr)
            line = expr.span.start.line
            if isinstance(binding, LocalBinding):
                self._emit_load_local(binding.index, line)
            elif isinstance(binding, GlobalBinding):
                self._emit_load_global(binding.index, line)
            else:
                raise AssertionError("unexpected binding type")
        elif isinstance(expr, ast.AssignExpr):
            binding = self._binding_for_node(expr)
            line = expr.span.start.line
            self._compile_expr(expr.value)
            if isinstance(binding, LocalBinding):
                self._emit_store_local(binding.index, line)
                self._emit_load_local(binding.index, line)
            elif isinstance(binding, GlobalBinding):
                self._emit_store_global(binding.index, line)
                self._emit_load_global(binding.index, line)
            else:
                raise AssertionError("unexpected binding type")
        elif isinstance(expr, ast.BinaryExpr):
            self._compile_expr(expr.left)
            self._compile_expr(expr.right)
            line = expr.span.start.line
            op_map = {
                "+": OpCode.ADD,
                "-": OpCode.SUB,
                "*": OpCode.MUL,
                "/": OpCode.DIV,
            }
            opcode = op_map.get(expr.operator.lexeme)
            if opcode is None:
                raise AssertionError(f"unsupported binary operator {expr.operator.lexeme}")
            self._emit(opcode, line)
        elif isinstance(expr, ast.CallExpr):
            symbol = self.resolved.call_targets[id(expr)]
            for argument in expr.arguments:
                self._compile_expr(argument)
            line = expr.span.start.line
            self._emit_call(symbol.index, len(expr.arguments), line)
        else:
            raise AssertionError(f"unknown expression {expr!r}")

    # Bytecode helpers ---------------------------------------------------------

    @property
    def _current_offset(self) -> int:
        assert self._current_chunk is not None
        return len(self._current_chunk.code)

    #convenience wrappers for writing opcodes and operands
    def _emit(self, opcode: OpCode, line: int) -> None:
        assert self._current_chunk is not None
        self._current_chunk.write(opcode, line)

    def _emit_u16(self, value: int, line: int) -> None:
        assert self._current_chunk is not None
        self._current_chunk.write_u16(value, line)

    def _emit_load_local(self, index: int, line: int) -> None:
        self._emit(OpCode.LOAD_LOCAL, line)
        self._emit_u16(index, line)

    def _emit_store_local(self, index: int, line: int) -> None:
        self._emit(OpCode.STORE_LOCAL, line)
        self._emit_u16(index, line)

    def _emit_load_global(self, index: int, line: int) -> None:
        self._emit(OpCode.LOAD_GLOBAL, line)
        self._emit_u16(index, line)

    def _emit_store_global(self, index: int, line: int) -> None:
        self._emit(OpCode.STORE_GLOBAL, line)
        self._emit_u16(index, line)

    def _emit_call(self, func_index: int, argc: int, line: int) -> None:
        self._emit(OpCode.CALL, line)
        self._emit_u16(func_index, line)
        assert self._current_chunk is not None
        self._current_chunk.write(argc, line)

    #emits placeholder operands so later we can patch jump targets
    def _emit_jump(self, opcode: OpCode, line: int) -> int:
        self._emit(opcode, line)
        offset = self._current_offset
        assert self._current_chunk is not None
        self._current_chunk.write(0, line)
        self._current_chunk.write(0, line)
        return offset

    def _patch_jump(self, offset: int) -> None:
        assert self._current_chunk is not None
        jump_target = len(self._current_chunk.code)
        self._current_chunk.patch_u16(offset, jump_target)

    def _emit_loop(self, loop_start: int, line: int) -> None:
        self._emit(OpCode.JMP, line)
        self._emit_u16(loop_start, line)

    #consults resolver metadata to pick global vs. local opcodes
    def _binding_for_node(self, node: ast.Node) -> VarBinding:
        binding = self.resolved.var_bindings.get(id(node))
        if binding is None:
            raise RuntimeError(f"no binding recorded for node {node}")
        return binding


__all__ = ["Compiler"]
