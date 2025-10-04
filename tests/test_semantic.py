import pytest

from decaf.lexer import Lexer
from decaf.parser import Parser
from decaf import ast
from decaf.semantic import Resolver, SemanticError, GlobalBinding, LocalBinding


#utility to run the full pipeline up to semantic resolution
def resolve_source(source: str):
    tokens = Lexer(source).lex()
    program = Parser(tokens).parse()
    result = Resolver(program).resolve()
    return program, result


#confirms binding metadata for globals and locals
def test_resolver_assigns_globals_and_locals() -> None:
    program, resolved = resolve_source(
        """
        let g = 1;
        fn main() {
            var x = g;
            x = x + 1;
            return 0;
        }
        """
    )
    assert len(resolved.globals) == 1
    g_binding = resolved.globals[0].binding
    assert isinstance(g_binding, GlobalBinding)
    assert g_binding.index == 0

    main_decl = program.declarations[1]
    body = main_decl.body
    assert body is not None
    var_decl = body.statements[0]
    assert isinstance(var_decl, ast.VarDecl)
    init_expr = var_decl.initializer
    binding = resolved.var_bindings[id(init_expr)]
    assert isinstance(binding, GlobalBinding)

    assign_stmt = body.statements[1]
    assert isinstance(assign_stmt, ast.ExprStmt)
    assign_expr = assign_stmt.expr
    assert isinstance(assign_expr, ast.AssignExpr)
    binding = resolved.var_bindings[id(assign_expr)]
    assert isinstance(binding, LocalBinding)
    assert binding.index == 0

    function_symbol = resolved.functions[0]
    assert function_symbol.max_locals == 1


#immutable `let` variables should reject writes
def test_assignment_to_immutable_is_error() -> None:
    with pytest.raises(SemanticError):
        resolve_source(
            """
            fn main() {
                let x = 0;
                x = 1;
                return 0;
            }
            """
        )


#use-before-declare must trigger a semantic error
def test_undeclared_variable_is_error() -> None:
    with pytest.raises(SemanticError):
        resolve_source(
            """
            fn main() {
                print y;
                return 0;
            }
            """
        )


#arity mismatches should surface clear diagnostics
def test_wrong_arity_call_is_error() -> None:
    with pytest.raises(SemanticError):
        resolve_source(
            """
            fn main() {
                return add(1);
            }
            fn add(a, b) {
                return a + b;
            }
            """
        )


#functions must statically guarantee a return
def test_functions_must_return() -> None:
    with pytest.raises(SemanticError):
        resolve_source(
            """
            fn main() {
                print 1;
            }
            """
        )


#verifies the simple return-path analysis handles else branches
def test_if_else_return_paths_are_checked() -> None:
    program, resolved = resolve_source(
        """
        fn main() {
            if (1) {
                return 1;
            } else {
                return 0;
            }
        }
        """
    )
    assert resolved.functions[0].name == "main"
