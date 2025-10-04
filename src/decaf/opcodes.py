"""Opcode definitions for the Decaf bytecode VM."""
from __future__ import annotations

from enum import IntEnum


#enumerates every instruction emitted by the compiler and executed by the VM
class OpCode(IntEnum):
    PUSH_CONST = 0
    LOAD_LOCAL = 1
    STORE_LOCAL = 2
    LOAD_GLOBAL = 3
    STORE_GLOBAL = 4
    ADD = 5
    SUB = 6
    MUL = 7
    DIV = 8
    JMP = 9
    JMP_IF_FALSE = 10
    CALL = 11
    RET = 12
    PRINT = 13
    POP = 14
    HALT = 15


#notes how each opcode manipulates the operand stack for sanity checks
STACK_EFFECT = {
    OpCode.PUSH_CONST: +1,
    OpCode.LOAD_LOCAL: +1,
    OpCode.STORE_LOCAL: -1,
    OpCode.LOAD_GLOBAL: +1,
    OpCode.STORE_GLOBAL: -1,
    OpCode.ADD: -1,
    OpCode.SUB: -1,
    OpCode.MUL: -1,
    OpCode.DIV: -1,
    OpCode.JMP: 0,
    OpCode.JMP_IF_FALSE: -1,
    OpCode.CALL: lambda argc: -(argc) + 1,
    OpCode.RET: -1,
    OpCode.PRINT: -1,
    OpCode.POP: -1,
    OpCode.HALT: 0,
}
