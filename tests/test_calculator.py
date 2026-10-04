"""计算引擎单元测试（纯业务，不需要数据库与 Web 框架）。

运行方式::

    python -m unittest discover -s tests -v
"""

import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.calculator import calculate_expression  # noqa: E402
from src.calculator.exceptions import (  # noqa: E402
    DivisionByZeroError,
    EmptyExpressionError,
    ExpressionTooLongError,
    InvalidCharacterError,
    InvalidExpressionError,
    MathDomainError,
    NumericOverflowError,
)


class BasicCalculationTests(unittest.TestCase):
    """四则运算。"""

    def assertResult(self, expression, expected):  # noqa: N802 - 保持 unittest 风格
        self.assertEqual(calculate_expression(expression).display, expected, msg=expression)

    def test_addition(self):
        self.assertResult("12+8", "20")

    def test_subtraction(self):
        self.assertResult("8-3*2", "2")

    def test_multiplication(self):
        self.assertResult("5*8", "40")

    def test_division(self):
        self.assertResult("10/2+7", "12")

    def test_full_width_and_unicode_symbols(self):
        """前端展示用的 × ÷ −（全角/Unicode）也能被后端正确解析。"""
        self.assertResult("12×8", "96")
        self.assertResult("12÷4", "3")
        self.assertResult("12−8", "4")

    def test_decimal_precision(self):
        """0.1 + 0.2 必须得到 0.3，而不是二进制浮点的 0.30000000000000004。"""
        self.assertResult("0.1+0.2", "0.3")

    def test_repeating_decimal_is_rounded_to_15_digits(self):
        self.assertResult("1/3", "0.333333333333333")

    def test_scientific_notation_input(self):
        self.assertResult("1e-3*2", "0.002")


class CompoundExpressionTests(unittest.TestCase):
    """复合表达式：优先级、括号、一元正负号、幂运算。"""

    def assertResult(self, expression, expected):  # noqa: N802
        self.assertEqual(calculate_expression(expression).display, expected, msg=expression)

    def test_operator_precedence(self):
        self.assertResult("1+2*3", "7")

    def test_parentheses_override_precedence(self):
        self.assertResult("(1+2)*3", "9")

    def test_nested_parentheses(self):
        self.assertResult("((1+2)*(3+4))-5", "16")

    def test_unary_minus(self):
        self.assertResult("-5+8", "3")

    def test_unary_minus_after_operator(self):
        self.assertResult("3*-2", "-6")

    def test_double_unary_sign(self):
        self.assertResult("--5", "5")

    def test_power_is_right_associative(self):
        self.assertResult("2^3^2", "512")

    def test_unary_minus_has_lower_priority_than_power(self):
        self.assertResult("-2^2", "-4")

    def test_power_with_negative_exponent(self):
        self.assertResult("2^-3", "0.125")

    def test_modulo(self):
        self.assertResult("10%3", "1")


class FunctionTests(unittest.TestCase):
    """函数、常量与阶乘。"""

    def assertResult(self, expression, expected):  # noqa: N802
        self.assertEqual(calculate_expression(expression).display, expected, msg=expression)

    def test_square_root(self):
        self.assertResult("sqrt(9)+1", "4")

    def test_log_with_base(self):
        self.assertResult("log(2,8)", "3")

    def test_constant_pi(self):
        self.assertResult("2*pi", "6.28318530717959")

    def test_constant_pi_symbol(self):
        self.assertResult("2*π", "6.28318530717959")

    def test_factorial_postfix(self):
        self.assertResult("5!", "120")

    def test_factorial_of_parenthesized_expression(self):
        self.assertResult("(2+3)!", "120")

    def test_absolute_value(self):
        self.assertResult("abs(-3)", "3")

    def test_round_with_digits(self):
        self.assertResult("round(3.14159,2)", "3.14")

    def test_unknown_function_is_rejected(self):
        with self.assertRaises(InvalidExpressionError):
            calculate_expression("evil(1)")


class ErrorHandlingTests(unittest.TestCase):
    """异常处理：除零、定义域、语法错误、长度限制。"""

    def test_division_by_zero(self):
        with self.assertRaises(DivisionByZeroError):
            calculate_expression("1/0")

    def test_modulo_by_zero(self):
        with self.assertRaises(DivisionByZeroError):
            calculate_expression("5%0")

    def test_zero_to_negative_power(self):
        with self.assertRaises(DivisionByZeroError):
            calculate_expression("0^-1")

    def test_sqrt_of_negative(self):
        with self.assertRaises(MathDomainError):
            calculate_expression("sqrt(-1)")

    def test_log_of_zero(self):
        with self.assertRaises(MathDomainError):
            calculate_expression("ln(0)")

    def test_negative_base_fractional_power(self):
        with self.assertRaises(MathDomainError):
            calculate_expression("(-8)^(1/3)")

    def test_factorial_of_negative(self):
        with self.assertRaises(MathDomainError):
            calculate_expression("(-3)!")

    def test_factorial_of_fraction(self):
        with self.assertRaises(MathDomainError):
            calculate_expression("2.5!")

    def test_empty_expression(self):
        with self.assertRaises(EmptyExpressionError):
            calculate_expression("   ")

    def test_expression_too_long(self):
        with self.assertRaises(ExpressionTooLongError):
            calculate_expression("1+" * 200 + "1")

    def test_illegal_character(self):
        with self.assertRaises(InvalidCharacterError):
            calculate_expression("1+2;a")

    def test_missing_operand(self):
        with self.assertRaises(InvalidExpressionError):
            calculate_expression("1+")

    def test_unbalanced_parentheses(self):
        with self.assertRaises(InvalidExpressionError):
            calculate_expression("(1+2")

    def test_extra_right_parenthesis(self):
        with self.assertRaises(InvalidExpressionError):
            calculate_expression("1+2)")

    def test_unknown_identifier(self):
        with self.assertRaises(InvalidExpressionError):
            calculate_expression("abc")

    def test_adjacent_operands_without_operator(self):
        with self.assertRaises(InvalidExpressionError):
            calculate_expression("1 2")

    def test_power_exponent_too_large(self):
        with self.assertRaises(NumericOverflowError):
            calculate_expression("2^99999")

    def test_result_magnitude_guard(self):
        with self.assertRaises(NumericOverflowError):
            calculate_expression("9^9000")

    def test_illegal_character_reports_position(self):
        with self.assertRaises(InvalidCharacterError) as context:
            calculate_expression("1+2$")
        self.assertEqual(context.exception.error_code, "INVALID_CHARACTER")
        self.assertEqual(context.exception.position, 3)
        self.assertIn("第 4 个字符", context.exception.message)


class SecurityTests(unittest.TestCase):
    """安全相关：禁止任何形式的代码执行。"""

    def test_python_code_is_not_executed(self):
        for payload in ("__import__('os')", "1+1; print(1)", "eval('1+1')", "1 or 1", "lambda: 1"):
            with self.subTest(payload=payload):
                with self.assertRaises(Exception):
                    calculate_expression(payload)

    def test_no_eval_in_source_code(self):
        """静态检查：核心计算模块中不得出现 eval / exec。"""
        package = PROJECT_ROOT / "src" / "calculator"
        for path in package.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("eval(", source, msg=f"{path.name} 中不允许使用 eval")
            self.assertNotIn("exec(", source, msg=f"{path.name} 中不允许使用 exec")


if __name__ == "__main__":
    unittest.main(verbosity=2)
