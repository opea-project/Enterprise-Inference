"""Safe arithmetic evaluation shared by the domain MCP servers.

The ``calculate`` tool exposed by each domain server accepts an expression string
supplied by the model. Evaluating that string with ``eval()`` would allow arbitrary
code execution, so expressions are parsed into an AST and only plain numeric
arithmetic nodes are interpreted.
"""

import ast
import operator
from typing import Callable, Dict, Type, Union

ALLOWED_CHARACTERS = "0123456789+-*/(). "

_BINARY_OPERATORS: Dict[Type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def _evaluate_node(node: ast.AST) -> float:
    """Recursively evaluate an arithmetic-only AST node."""
    if isinstance(node, ast.Expression):
        return _evaluate_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _evaluate_node(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        return _BINARY_OPERATORS[type(node.op)](_evaluate_node(node.left), _evaluate_node(node.right))
    raise ValueError("Unsupported expression")


def calculate_expression(expression: str, ndigits: int) -> str:
    """Evaluate a numeric expression and return the result rounded to ``ndigits``.

    Args:
        expression: Expression built from numbers, ``+ - * /``, parentheses and spaces.
        ndigits: Number of decimal places to round the result to.

    Returns:
        The rounded result as a string.

    Raises:
        ValueError: If the expression contains disallowed characters or constructs.
        ZeroDivisionError: If the expression divides by zero.
    """
    if not all(char in ALLOWED_CHARACTERS for char in expression):
        raise ValueError("Invalid characters in expression")
    try:
        # Leading/trailing whitespace is stripped so that ast.parse does not report it
        # as an indentation error.
        parsed: Union[ast.Expression, ast.AST] = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise ValueError("Invalid expression") from exc
    return str(round(_evaluate_node(parsed), ndigits))
