"""Stack-based virtual machine for Decaf bytecode."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .chunk import BytecodeFunction, BytecodeProgram
from .opcodes import OpCode


#captures a single activation record during execution
@dataclass(slots=True)
class CallFrame:
    function: BytecodeFunction
    ip: int
    stack_base: int


#vm-specific runtime exceptions so callers can react cleanly
class VMRuntimeError(RuntimeError):
    pass


#interprets bytecode programs emitted by the compiler
class VM:
    def __init__(self, program: BytecodeProgram) -> None:
        self.program = program
        self.stack: List[int] = []
        self.frames: List[CallFrame] = []
        self.globals: List[int] = list(program.globals)
        self.output: List[str] = []

    #runs the entry chunk until HALT while optionally tracing state
    def run(self, trace: bool = False) -> List[str]:
        self._call_function(self.program.entry_index, 0)
        while self.frames:
            frame = self.frames[-1]
            chunk = frame.function.chunk
            if frame.ip >= len(chunk.code):
                raise VMRuntimeError("instruction pointer out of bounds")
            opcode = OpCode(chunk.code[frame.ip])
            frame.ip += 1
            if trace:
                self._trace(frame, opcode)
            if opcode is OpCode.PUSH_CONST:
                const_index = self._read_u16(frame)
                value = chunk.constants[const_index]
                self.stack.append(value)
            elif opcode is OpCode.LOAD_LOCAL:
                index = self._read_u16(frame)
                self.stack.append(self._load_local(frame, index))
            elif opcode is OpCode.STORE_LOCAL:
                index = self._read_u16(frame)
                self._store_local(frame, index)
            elif opcode is OpCode.LOAD_GLOBAL:
                index = self._read_u16(frame)
                self.stack.append(self.globals[index])
            elif opcode is OpCode.STORE_GLOBAL:
                index = self._read_u16(frame)
                self._store_global(index)
            elif opcode is OpCode.ADD:
                self._binary(lambda a, b: a + b)
            elif opcode is OpCode.SUB:
                self._binary(lambda a, b: a - b)
            elif opcode is OpCode.MUL:
                self._binary(lambda a, b: a * b)
            elif opcode is OpCode.DIV:
                self._binary(self._safe_div)
            elif opcode is OpCode.JMP:
                target = self._read_u16(frame)
                frame.ip = target
            elif opcode is OpCode.JMP_IF_FALSE:
                target = self._read_u16(frame)
                value = self.stack.pop()
                if value == 0:
                    frame.ip = target
            elif opcode is OpCode.CALL:
                func_index = self._read_u16(frame)
                argc = self._read_byte(frame)
                self._call_function(func_index, argc)
            elif opcode is OpCode.RET:
                self._return()
            elif opcode is OpCode.PRINT:
                value = self.stack.pop()
                self.output.append(str(value))
            elif opcode is OpCode.POP:
                self.stack.pop()
            elif opcode is OpCode.HALT:
                if trace:
                    self._log("halt")
                self.frames.clear()
                break
            else:
                raise VMRuntimeError(f"unknown opcode {opcode}")
        return self.output

    # Helpers -----------------------------------------------------------------

    #prints a concise view of the current instruction and stack tail
    def _trace(self, frame: CallFrame, opcode: OpCode) -> None:
        ip = frame.ip - 1
        tail = self.stack[-5:]
        prefix = "..." if len(self.stack) > 5 else ""
        stack_preview = prefix + ",".join(str(v) for v in tail) if tail else "<empty>"
        self._log(f"ip={ip} fn={frame.function.name} op={opcode.name} stack=[{stack_preview}]")

    def _log(self, message: str) -> None:
        print(f"[trace] {message}")

    #utility readers abstract operand decoding
    def _read_u16(self, frame: CallFrame) -> int:
        chunk = frame.function.chunk
        hi = chunk.code[frame.ip]
        lo = chunk.code[frame.ip + 1]
        frame.ip += 2
        return (hi << 8) | lo

    def _read_byte(self, frame: CallFrame) -> int:
        chunk = frame.function.chunk
        value = chunk.code[frame.ip]
        frame.ip += 1
        return value

    #performs generic binary arithmetic by popping two operands
    def _binary(self, op) -> None:
        b = self.stack.pop()
        a = self.stack.pop()
        self.stack.append(op(a, b))

    #implements integer division with explicit zero guard
    def _safe_div(self, a: int, b: int) -> int:
        if b == 0:
            raise VMRuntimeError("division by zero")
        return a // b

    #pushes a new frame and allocates local slots for calls
    def _call_function(self, func_index: int, argc: int) -> None:
        if func_index < 0 or func_index >= len(self.program.functions):
            raise VMRuntimeError(f"call target {func_index} out of range")
        function = self.program.functions[func_index]
        if argc != function.arity:
            raise VMRuntimeError(f"function '{function.name}' arity mismatch: expected {function.arity}, got {argc}")
        stack_base = len(self.stack) - argc
        if stack_base < 0:
            raise VMRuntimeError("call stack underflow")
        needed = stack_base + function.num_locals
        while len(self.stack) < needed:
            self.stack.append(0)
        frame = CallFrame(function=function, ip=0, stack_base=stack_base)
        self.frames.append(frame)

    #unwinds the current frame and hands back the top value
    def _return(self) -> None:
        if not self.frames:
            raise VMRuntimeError("return with empty call stack")
        frame = self.frames.pop()
        value = self.stack.pop()
        del self.stack[frame.stack_base:]
        self.stack.append(value)
        if not self.frames:
            self.stack.clear()

    #native helpers enforce bounds on local/global access
    def _store_local(self, frame: CallFrame, index: int) -> None:
        value = self.stack.pop()
        slot = frame.stack_base + index
        if slot >= len(self.stack):
            raise VMRuntimeError("local store out of range")
        self.stack[slot] = value

    def _load_local(self, frame: CallFrame, index: int) -> int:
        slot = frame.stack_base + index
        if slot >= len(self.stack):
            raise VMRuntimeError("local load out of range")
        return self.stack[slot]

    def _store_global(self, index: int) -> None:
        value = self.stack.pop()
        if index >= len(self.globals):
            raise VMRuntimeError("global store out of range")
        self.globals[index] = value


__all__ = ["VM", "VMRuntimeError"]
