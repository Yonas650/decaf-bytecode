from pathlib import Path

from decaf.compiler import Compiler
from decaf.disasm import disassemble_program
from decaf.lexer import Lexer
from decaf.parser import Parser
from decaf.semantic import Resolver
from decaf.vm import VM, VMRuntimeError
from decaf.chunk import BytecodeProgram


#compiles helper programs so VM tests stay focused on runtime
def compile_source(source: str) -> BytecodeProgram:
    tokens = Lexer(source).lex()
    program = Parser(tokens).parse()
    resolved = Resolver(program).resolve()
    return Compiler(resolved).compile()


#basic arithmetic program should print the right result
def test_vm_runs_arithmetic_program(tmp_path: Path) -> None:
    program = compile_source(
        """
        fn main() {
            print 2 + 3 * 4;
            return 0;
        }
        """
    )
    vm = VM(program)
    outputs = vm.run()
    assert outputs == ["14"]


#global mutation and loop execution should succeed
def test_vm_handles_globals_and_functions() -> None:
    program = compile_source(
        """
        var g = 10;
        fn main() {
            var i = 0;
            while (i - 3) {
                g = g + i;
                i = i + 1;
            }
            print g;
            return g;
        }
        """
    )
    vm = VM(program)
    outputs = vm.run()
    assert outputs == ["13"]


#division by zero must raise a VMRuntimeError
def test_vm_division_by_zero_raises() -> None:
    program = compile_source(
        """
        fn main() {
            var a = 1;
            print a / (a - 1);
            return 0;
        }
        """
    )
    vm = VM(program)
    try:
        vm.run()
        raised = False
    except VMRuntimeError:
        raised = True
    assert raised


#json serialization should preserve bytecode contents
def test_program_serialization_roundtrip(tmp_path: Path) -> None:
    program = compile_source(
        """
        fn main() {
            print 1;
            return 0;
        }
        """
    )
    data = program.to_dict()
    restored = BytecodeProgram.from_dict(data)
    assert disassemble_program(program) == disassemble_program(restored)
