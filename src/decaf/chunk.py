"""Bytecode chunk helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


#holds raw bytecode, constant pool, and line info for debugging
@dataclass(slots=True)
class Chunk:
    code: List[int] = field(default_factory=list)
    lines: List[int] = field(default_factory=list)
    constants: List[int] = field(default_factory=list)

    def add_constant(self, value: int) -> int:
        self.constants.append(value)
        return len(self.constants) - 1

    def write(self, byte: int, line: int) -> None:
        self.code.append(int(byte))
        self.lines.append(line)

    def write_u16(self, value: int, line: int) -> None:
        self.write((value >> 8) & 0xFF, line)
        self.write(value & 0xFF, line)

    def patch_u16(self, offset: int, value: int) -> None:
        self.code[offset] = (value >> 8) & 0xFF
        self.code[offset + 1] = value & 0xFF

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": [int(b) for b in self.code],
            "lines": list(self.lines),
            "constants": list(self.constants),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Chunk:
        return cls(
            code=[int(x) for x in data["code"]],
            lines=[int(x) for x in data["lines"]],
            constants=[int(x) for x in data["constants"]],
        )


#wraps a chunk with function metadata used at runtime
@dataclass(slots=True)
class BytecodeFunction:
    name: str
    chunk: Chunk
    arity: int
    num_locals: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "chunk": self.chunk.to_dict(),
            "arity": self.arity,
            "num_locals": self.num_locals,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BytecodeFunction:
        return cls(
            name=data["name"],
            chunk=Chunk.from_dict(data["chunk"]),
            arity=int(data["arity"]),
            num_locals=int(data["num_locals"]),
        )


#encapsulates the compiled module with functions, globals, entry point
@dataclass(slots=True)
class BytecodeProgram:
    functions: List[BytecodeFunction]
    globals: List[int]
    entry_index: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "functions": [fn.to_dict() for fn in self.functions],
            "globals": list(self.globals),
            "entry_index": self.entry_index,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BytecodeProgram:
        return cls(
            functions=[BytecodeFunction.from_dict(fn) for fn in data["functions"]],
            globals=[int(x) for x in data["globals"]],
            entry_index=int(data["entry_index"]),
        )
