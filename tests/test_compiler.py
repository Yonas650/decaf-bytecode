from decaf.lexer import Lexer
from decaf.parser import Parser
from decaf.semantic import Resolver
from decaf.compiler import Compiler
from decaf.opcodes import OpCode


#helper compiles source to bytecode for regression checks
def compile_source(source: str):
    tokens = Lexer(source).lex()
    program = Parser(tokens).parse()
    resolved = Resolver(program).resolve()
    return Compiler(resolved).compile()


#ensures arithmetic and print compile with expected bytecode
def test_compile_print_and_return() -> None:
    program = compile_source(
        """
        fn main() {
            print 2 + 3 * 4;
            return 0;
        }
        """
    )
    main_fn = next(fn for fn in program.functions if fn.name == "main")
    chunk = main_fn.chunk
    assert chunk.constants == [2, 3, 4, 0]
    assert chunk.code == [
        OpCode.PUSH_CONST,
        0,
        0,
        OpCode.PUSH_CONST,
        0,
        1,
        OpCode.PUSH_CONST,
        0,
        2,
        OpCode.MUL,
        OpCode.ADD,
        OpCode.PRINT,
        OpCode.PUSH_CONST,
        0,
        3,
        OpCode.RET,
    ]


#global initializers plus entry call flow should be encoded
def test_compile_global_initializer_and_call() -> None:
    program = compile_source(
        """
        let g = 10;
        fn main() {
            return g;
        }
        """
    )
    entry_fn = program.functions[program.entry_index]
    entry_code = entry_fn.chunk.code
    #entry should load constant 10, store global 0, call main, pop result, halt
    assert entry_fn.chunk.constants == [10]
    assert entry_code[:6] == [
        OpCode.PUSH_CONST,
        0,
        0,
        OpCode.STORE_GLOBAL,
        0,
        0,
    ]
    assert entry_code[-2:] == [OpCode.POP, OpCode.HALT]
    main_fn = next(fn for fn in program.functions if fn.name == "main")
    main_code = main_fn.chunk.code
    assert main_code == [
        OpCode.LOAD_GLOBAL,
        0,
        0,
        OpCode.RET,
    ]


#control flow constructs should emit jump opcodes
def test_compile_if_else_and_while_generates_jumps() -> None:
    program = compile_source(
        """
        fn main() {
            var i = 0;
            while (i) {
                if (i) {
                    print i;
                } else {
                    print 0;
                }
                i = i - 1;
            }
            return 0;
        }
        """
    )
    main_fn = next(fn for fn in program.functions if fn.name == "main")
    code = main_fn.chunk.code
    #ensure we have at least one conditional and loop jump
    assert OpCode.JMP_IF_FALSE in code
    assert OpCode.JMP in code
