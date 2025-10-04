"""Parser that turns Decaf tokens into an AST."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from . import ast
from .errors import ParseError, SourceSpan
from .token import Token, TokenType


#navigates the token stream via recursive descent
@dataclass(slots=True)
class Parser:
    tokens: List[Token]
    _current: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        self._current = 0

    def parse(self) -> ast.Program:
        declarations: List[ast.Declaration] = []
        while not self._is_at_end():
            if self._check(TokenType.FN):
                declarations.append(self._function_decl())
            elif self._check(TokenType.LET) or self._check(TokenType.VAR):
                declarations.append(self._var_decl())
            else:
                token = self._peek()
                raise ParseError("expected function or variable declaration", token.span)
        program_span = self._span_from_nodes(declarations)
        return ast.Program(span=program_span, declarations=declarations)

    # Declarations ---------------------------------------------------------------

    #parses function headers and delegates to block parsing for body
    def _function_decl(self) -> ast.FunctionDecl:
        fn_keyword = self._advance()  # consume 'fn'
        name_token = self._consume(TokenType.IDENTIFIER, "expected function name")
        self._consume(TokenType.LEFT_PAREN, "expected '(' after function name")
        params: List[ast.Param] = []
        if not self._check(TokenType.RIGHT_PAREN):
            while True:
                param_token = self._consume(TokenType.IDENTIFIER, "expected parameter name")
                param = ast.Param(
                    span=param_token.span,
                    name=param_token.lexeme,
                    name_span=param_token.span,
                )
                params.append(param)
                if not self._match(TokenType.COMMA):
                    break
        self._consume(TokenType.RIGHT_PAREN, "expected ')' after parameters")
        body = self._block_stmt()
        span = fn_keyword.span.merge(body.span)
        return ast.FunctionDecl(
            span=span,
            name=name_token.lexeme,
            name_span=name_token.span,
            params=params,
            body=body,
        )

    #handles `let`/`var` definitions both globally and locally
    def _var_decl(self) -> ast.VarDecl:
        mut_keyword = self._advance()  # consumes 'let' or 'var'
        mutable = mut_keyword.type is TokenType.VAR
        name_token = self._consume(TokenType.IDENTIFIER, "expected variable name")
        self._consume(TokenType.EQUAL, "expected '=' after variable name")
        initializer = self._expression()
        semicolon = self._consume(TokenType.SEMICOLON, "expected ';' after variable declaration")
        span = mut_keyword.span.merge(semicolon.span)
        return ast.VarDecl(
            span=span,
            name=name_token.lexeme,
            name_span=name_token.span,
            mutable=mutable,
            initializer=initializer,
        )

    # Statements ----------------------------------------------------------------

    #directs statements based on leading token kind
    def _statement(self) -> ast.Stmt:
        if self._match(TokenType.PRINT):
            return self._print_stmt()
        if self._match(TokenType.IF):
            return self._if_stmt()
        if self._match(TokenType.WHILE):
            return self._while_stmt()
        if self._match(TokenType.RETURN):
            return self._return_stmt()
        if self._match(TokenType.LEFT_BRACE):
            return self._block_from_open_brace(open_brace=self._previous())
        return self._expr_stmt()

    #parses a block that begins with an explicit `{`
    def _block_stmt(self) -> ast.BlockStmt:
        opening = self._consume(TokenType.LEFT_BRACE, "expected '{' to start block")
        return self._block_from_open_brace(opening)

    #allows nested blocks by reusing the token captured earlier
    def _block_from_open_brace(self, open_brace: Token) -> ast.BlockStmt:
        statements: List[ast.Stmt] = []
        while not self._check(TokenType.RIGHT_BRACE) and not self._is_at_end():
            if self._check(TokenType.LET) or self._check(TokenType.VAR):
                statements.append(self._var_decl())
            else:
                statements.append(self._statement())
        close_brace = self._consume(TokenType.RIGHT_BRACE, "expected '}' after block")
        span = open_brace.span.merge(close_brace.span)
        return ast.BlockStmt(span=span, statements=statements)

    #`print` statements expect an expression followed by semicolon
    def _print_stmt(self) -> ast.PrintStmt:
        keyword = self._previous()
        value = self._expression()
        semicolon = self._consume(TokenType.SEMICOLON, "expected ';' after print statement")
        span = keyword.span.merge(semicolon.span)
        return ast.PrintStmt(span=span, expr=value)

    #if/else nests arbitrary statements for branches
    def _if_stmt(self) -> ast.IfStmt:
        keyword = self._previous()
        self._consume(TokenType.LEFT_PAREN, "expected '(' after 'if'")
        condition = self._expression()
        self._consume(TokenType.RIGHT_PAREN, "expected ')' after if condition")
        then_branch = self._statement()
        else_branch = None
        span = keyword.span.merge(then_branch.span)
        if self._match(TokenType.ELSE):
            else_stmt = self._statement()
            else_branch = else_stmt
            span = span.merge(else_stmt.span)
        return ast.IfStmt(span=span, condition=condition, then_branch=then_branch, else_branch=else_branch)

    #while loops reuse expression parsing for the condition
    def _while_stmt(self) -> ast.WhileStmt:
        keyword = self._previous()
        self._consume(TokenType.LEFT_PAREN, "expected '(' after 'while'")
        condition = self._expression()
        self._consume(TokenType.RIGHT_PAREN, "expected ')' after while condition")
        body = self._statement()
        span = keyword.span.merge(body.span)
        return ast.WhileStmt(span=span, condition=condition, body=body)

    #return statements always require a value because the language uses ints
    def _return_stmt(self) -> ast.ReturnStmt:
        keyword = self._previous()
        value = self._expression()
        semicolon = self._consume(TokenType.SEMICOLON, "expected ';' after return value")
        span = keyword.span.merge(semicolon.span)
        return ast.ReturnStmt(span=span, value=value)

    #plain expressions become expression statements
    def _expr_stmt(self) -> ast.ExprStmt:
        expr = self._expression()
        semicolon = self._consume(TokenType.SEMICOLON, "expected ';' after expression")
        span = expr.span.merge(semicolon.span)
        return ast.ExprStmt(span=span, expr=expr)

    # Expressions ---------------------------------------------------------------

    #follows precedence climbing by delegating to `_assignment`
    def _expression(self) -> ast.Expr:
        return self._assignment()

    #assignment is right-associative and validates the left side
    def _assignment(self) -> ast.Expr:
        expr = self._term()
        if self._match(TokenType.EQUAL):
            equals = self._previous()
            value = self._assignment()
            if isinstance(expr, ast.VarExpr):
                span = expr.span.merge(value.span)
                return ast.AssignExpr(span=span, name=expr.name, name_span=expr.name_span, value=value)
            raise ParseError("invalid assignment target", equals.span)
        return expr

    #handles `+` and `-` with left-associativity
    def _term(self) -> ast.Expr:
        expr = self._factor()
        while self._match(TokenType.PLUS, TokenType.MINUS):
            operator = self._previous()
            right = self._factor()
            span = expr.span.merge(right.span)
            expr = ast.BinaryExpr(span=span, left=expr, operator=operator, right=right)
        return expr

    #handles `*` and `/` precedence level
    def _factor(self) -> ast.Expr:
        expr = self._unary()
        while self._match(TokenType.STAR, TokenType.SLASH):
            operator = self._previous()
            right = self._unary()
            span = expr.span.merge(right.span)
            expr = ast.BinaryExpr(span=span, left=expr, operator=operator, right=right)
        return expr

    #unary minus rewrites into `0 - expr` without dedicated node
    def _unary(self) -> ast.Expr:
        if self._match(TokenType.MINUS):
            operator = self._previous()
            right = self._unary()
            span = operator.span.merge(right.span)
            zero = ast.IntLiteral(span=operator.span, value=0)
            return ast.BinaryExpr(span=span, left=zero, operator=operator, right=right)
        return self._call()

    #branches into call parsing when encountering parentheses after an identifier
    def _call(self) -> ast.Expr:
        expr = self._primary()
        while self._check(TokenType.LEFT_PAREN):
            left_paren = self._advance()
            expr = self._finish_call(expr, left_paren)
        return expr

    #ensures only identifiers are callable and parses argument lists
    def _finish_call(self, callee_expr: ast.Expr, left_paren: Token) -> ast.Expr:
        if not isinstance(callee_expr, ast.VarExpr):
            raise ParseError("can only call functions by name", callee_expr.span)
        arguments: List[ast.Expr] = []
        if not self._check(TokenType.RIGHT_PAREN):
            while True:
                arguments.append(self._expression())
                if not self._match(TokenType.COMMA):
                    break
        right_paren = self._consume(TokenType.RIGHT_PAREN, "expected ')' after arguments")
        callee_span = callee_expr.name_span
        span = callee_expr.span.merge(right_paren.span)
        span = span.merge(left_paren.span)
        return ast.CallExpr(span=span, callee=callee_expr.name, callee_span=callee_span, arguments=arguments)

    #primary expressions include literals, identifiers, and parenthesized forms
    def _primary(self) -> ast.Expr:
        if self._match(TokenType.INTEGER):
            token = self._previous()
            assert token.literal is not None
            return ast.IntLiteral(span=token.span, value=token.literal)
        if self._match(TokenType.IDENTIFIER):
            token = self._previous()
            return ast.VarExpr(span=token.span, name=token.lexeme, name_span=token.span)
        if self._match(TokenType.LEFT_PAREN):
            open_paren = self._previous()
            expr = self._expression()
            close_paren = self._consume(TokenType.RIGHT_PAREN, "expected ')' after expression")
            expr.span = open_paren.span.merge(close_paren.span)
            return expr
        token = self._peek()
        raise ParseError("expected expression", token.span)

    # Utilities ----------------------------------------------------------------

    #helper for multi-token lookahead checks
    def _match(self, *types: TokenType) -> bool:
        for token_type in types:
            if self._check(token_type):
                self._advance()
                return True
        return False

    #convenience to assert the upcoming token type
    def _consume(self, token_type: TokenType, message: str) -> Token:
        if self._check(token_type):
            return self._advance()
        token = self._peek()
        raise ParseError(message, token.span)

    #safely checks the current token without consuming it
    def _check(self, token_type: TokenType) -> bool:
        if self._is_at_end():
            return False
        return self._peek().type is token_type

    #moves the cursor forward returning the previous token
    def _advance(self) -> Token:
        if not self._is_at_end():
            self._current += 1
        return self._previous()

    #EOF tokens guard termination
    def _is_at_end(self) -> bool:
        return self._peek().type is TokenType.EOF

    #peeks at the current token without consuming
    def _peek(self) -> Token:
        return self.tokens[self._current]

    #returns the token immediately before `_current`
    def _previous(self) -> Token:
        return self.tokens[self._current - 1]

    #computes a span covering all child nodes for the program root
    def _span_from_nodes(self, nodes: List[ast.Node]) -> SourceSpan:
        if not nodes:
            eof = self.tokens[-1]
            return eof.span
        span = nodes[0].span
        for node in nodes[1:]:
            span = span.merge(node.span)
        return span
