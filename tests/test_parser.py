import pytest

from decaf.lexer import Lexer
from decaf.parser import Parser
from decaf import ast
from decaf.errors import ParseError


#parses helper sources for parser assertions
def parse(source: str) -> ast.Program:
    tokens = Lexer(source).lex()
    return Parser(tokens).parse()


#verifies global let/var parsing and mutability flagging
def test_top_level_var_declarations() -> None:
    program = parse("""
    let x = 1;
    var y = x;
    """)
    assert len(program.declarations) == 2
    first, second = program.declarations
    assert isinstance(first, ast.VarDecl)
    assert first.name == "x"
    assert first.mutable is False
    assert isinstance(second, ast.VarDecl)
    assert second.mutable is True


#ensures functions capture statements and parameters correctly
def test_function_with_statements() -> None:
    program = parse(
        """
        fn add(a, b) {
            let total = a + b;
            print total;
            return total;
        }
        """
    )
    assert len(program.declarations) == 1
    fn_decl = program.declarations[0]
    assert isinstance(fn_decl, ast.FunctionDecl)
    assert fn_decl.name == "add"
    assert [param.name for param in fn_decl.params] == ["a", "b"]
    assert isinstance(fn_decl.body, ast.BlockStmt)
    assert len(fn_decl.body.statements) == 3
    assert isinstance(fn_decl.body.statements[-1], ast.ReturnStmt)


#covers nested control-flow constructs
def test_if_else_and_while_parse() -> None:
    program = parse(
        """
        fn main() {
            var i = 0;
            if (i) {
                print 1;
            } else {
                print 2;
            }
            while (i) {
                i = i - 1;
            }
            return 0;
        }
        """
    )
    fn_decl = program.declarations[0]
    assert isinstance(fn_decl, ast.FunctionDecl)
    body = fn_decl.body
    assert isinstance(body, ast.BlockStmt)
    assert any(isinstance(stmt, ast.IfStmt) for stmt in body.statements)
    assert any(isinstance(stmt, ast.WhileStmt) for stmt in body.statements)


#assignment should reject non-lvalue targets
def test_invalid_assignment_target_raises() -> None:
    with pytest.raises(ParseError):
        parse(
            """
            fn main() {
                (1 + 2) = 3;
            }
            """
        )


#parser forbids stray statements at module scope
def test_top_level_statement_is_error() -> None:
    with pytest.raises(ParseError):
        parse("print 1;")
