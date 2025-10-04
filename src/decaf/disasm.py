"""Human-readable disassembly for Decaf bytecode."""
from __future__ import annotations

from typing import List

from .chunk import BytecodeFunction, BytecodeProgram
from .opcodes import OpCode


#nice string formatter used by CLI/tests for debugging
def disassemble_program(program: BytecodeProgram) -> str:
    lines: List[str] = []
    for index, function in enumerate(program.functions):
        lines.append(f"== fn {index} {function.name} ==")
        lines.extend(_disassemble_function(function, program))
    return "\n".join(lines)


#handles opcode-specific formatting per function
def _disassemble_function(function: BytecodeFunction, program: BytecodeProgram) -> List[str]:
    chunk = function.chunk
    lines: List[str] = []
    offset = 0
    while offset < len(chunk.code):
        line = chunk.lines[offset]
        opcode = OpCode(chunk.code[offset])
        offset += 1
        if opcode is OpCode.PUSH_CONST:
            const_index, offset = _read_u16(chunk, offset)
            value = chunk.constants[const_index]
            lines.append(f"{offset - 3:04} line {line:>3} {opcode.name:<13} #{const_index} ({value})")
        elif opcode in (OpCode.LOAD_LOCAL, OpCode.STORE_LOCAL, OpCode.LOAD_GLOBAL, OpCode.STORE_GLOBAL):
            index, offset = _read_u16(chunk, offset)
            lines.append(f"{offset - 3:04} line {line:>3} {opcode.name:<13} {index}")
        elif opcode is OpCode.CALL:
            func_index, offset = _read_u16(chunk, offset)
            argc = chunk.code[offset]
            offset += 1
            name = program.functions[func_index].name if 0 <= func_index < len(program.functions) else "<invalid>"
            lines.append(f"{offset - 4:04} line {line:>3} CALL           {func_index} {name} argc={argc}")
        elif opcode in (OpCode.JMP, OpCode.JMP_IF_FALSE):
            target, offset = _read_u16(chunk, offset)
            lines.append(f"{offset - 3:04} line {line:>3} {opcode.name:<13} -> {target:04}")
        else:
            lines.append(f"{offset - 1:04} line {line:>3} {opcode.name}")
    return lines


#helper for reading two-byte operands while walking code
def _read_u16(chunk, offset):
    hi = chunk.code[offset]
    lo = chunk.code[offset + 1]
    value = (hi << 8) | lo
    return value, offset + 2


__all__ = ["disassemble_program"]
