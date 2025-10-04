"""Command-line entry point for Decaf."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from .compiler import Compiler
from .disasm import disassemble_program
from .lexer import Lexer
from .parser import Parser
from .semantic import Resolver
from .chunk import BytecodeProgram
from .vm import VM


#pipelines lexing->parsing->analysis->codegen for tooling
def compile_text(source: str) -> BytecodeProgram:
    tokens = Lexer(source).lex()
    program = Parser(tokens).parse()
    resolved = Resolver(program).resolve()
    return Compiler(resolved).compile()


#loads a JSON bytecode artifact back into in-memory structures
def load_program(path: Path) -> BytecodeProgram:
    data = json.loads(path.read_text())
    return BytecodeProgram.from_dict(data)


#normalizes JSON output for reproducible storage
def save_program(program: BytecodeProgram, path: Path) -> None:
    data = program.to_dict()
    path.write_text(json.dumps(data, indent=2))


#handles the `decaf compile` subcommand
def cmd_compile(args: argparse.Namespace) -> int:
    source = Path(args.source).read_text()
    program = compile_text(source)
    save_program(program, Path(args.output))
    return 0


#executes either source or precompiled bytecode optionally with trace
def cmd_run(args: argparse.Namespace) -> int:
    if args.bytecode:
        program = load_program(Path(args.bytecode))
    elif args.source:
        source = Path(args.source).read_text()
        program = compile_text(source)
    else:
        raise SystemExit("run requires --bytecode or source path")
    vm = VM(program)
    outputs = vm.run(trace=args.trace)
    if outputs:
        print("\n".join(outputs))
    return 0


#prints a human-readable view of the program structure
def cmd_disasm(args: argparse.Namespace) -> int:
    if args.bytecode:
        program = load_program(Path(args.bytecode))
    elif args.source:
        source = Path(args.source).read_text()
        program = compile_text(source)
    else:
        raise SystemExit("disasm requires --bytecode or source path")
    print(disassemble_program(program))
    return 0


#configures the CLI surface across compile/run/disasm
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="decaf", description="Decaf language tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_compile = subparsers.add_parser("compile", help="compile source to bytecode JSON")
    p_compile.add_argument("source", help="path to source file")
    p_compile.add_argument("-o", "--output", required=True, help="output bytecode file")
    p_compile.set_defaults(func=cmd_compile)

    p_run = subparsers.add_parser("run", help="compile and run source or execute bytecode")
    p_run.add_argument("source", nargs="?", help="path to source file")
    p_run.add_argument("-b", "--bytecode", help="execute existing bytecode JSON")
    p_run.add_argument("--trace", action="store_true", help="print VM trace while executing")
    p_run.set_defaults(func=cmd_run)

    p_dis = subparsers.add_parser("disasm", help="disassemble source or bytecode")
    p_dis.add_argument("source", nargs="?", help="path to source file")
    p_dis.add_argument("-b", "--bytecode", help="disassemble bytecode JSON")
    p_dis.set_defaults(func=cmd_disasm)

    return parser


#entry point used by both console script and module execution
def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
