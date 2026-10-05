"""计算内核单元测试：词法分析、语法分析、求值、格式化。

这一层不依赖 FastAPI、不依赖数据库，可以独立运行：

.. code-block:: bash

    pytest tests/test_calculator_engine.py -v

测试用例直接对应作业评分点：
基本四则运算、运算优先级、括号、小数、一元正负号、
非法表达式、除零处理。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.calculator import CalculatorError, calculate
from app.calculator.errors import ErrorCode
from app.calculator.formatter import format_decimal
from app.calculator.parser import parse
from app.calculator.tokenizer import TokenType, normalize_expression, tokenize


# ===================================================================== #
# 一、基本四则运算（作业 Feature 1）
# ===================================================================== #
class TestBasicArithmetic:
    """加减乘除。"""

    @pytest.mark.parametrize(
        ("expression", "expected"),
        [
            ("12+8", "20"),
            ("12-8", "4"),
            ("12*8", "96"),
            ("12/8", "1.5"),
            ("1+1", "2"),
            ("100-1", "99"),
            ("6*7", "42"),
            ("9/3", "3"),
            # 全角 / 数学符号归一化
            ("12×8", "96"),
            ("12÷8", "1.5"),
            ("１２＋８", "20"),
            ("3−2", "1"),
        ],
    )
    def test_basic(self, expression: str, expected: str) -> None:
        assert calculate(expression).result_text == expected


# ===================================================================== #
# 二、复合表达式：优先级、括号、小数、一元符号（作业 Feature 2）
# ===================================================================== #
class TestCompoundExpressions:
    """复合表达式。"""

    @pytest.mark.parametrize(
        ("expression", "expected"),
        [
            # 作业原文给出的六个例子
            ("1 + 2 * 3", "7"),
            ("(1 + 2) * 3", "9"),
            ("10 / 2 + 7", "12"),
            ("8 - 3 * 2", "2"),
            ("-5 + 8", "3"),
            ("3 * -2", "-6"),
        ],
    )
    def test_assignment_examples(self, expression: str, expected: str) -> None:
        """作业原文列出的六个复合表达式示例。"""
        assert calculate(expression).result_text == expected

    @pytest.mark.parametrize(
        ("expression", "expected"),
        [
            ("1+2*3-4/2", "5"),
            ("(1+2)*(3+4)", "21"),
            ("2*(3+(4-1))", "12"),
            ("10-(2+3)*2", "0"),
            ("100/10/2", "5"),
            ("2-3-4", "-5"),
        ],
    )
    def test_precedence_and_parentheses(self, expression: str, expected: str) -> None:
        """运算符优先级与括号嵌套。"""
        assert calculate(expression).result_text == expected

    @pytest.mark.parametrize(
        ("expression", "expected"),
        [
            ("0.1+0.2", "0.3"),
            ("3.5+1.25", "4.75"),
            ("1.5*2", "3"),
            ("0.5/0.25", "2"),
            (".5+.5", "1"),
            ("1.5e-3", "0.0015"),
            ("2.5e2", "250"),
        ],
    )
    def test_decimals(self, expression: str, expected: str) -> None:
        """小数与科学计数法。

        ``0.1+0.2 == 0.3`` 是 Decimal 相对二进制浮点的核心优势：
        用 float 计算会得到 0.30000000000000004。
        """
        assert calculate(expression).result_text == expected

    @pytest.mark.parametrize(
        ("expression", "expected"),
        [
            ("-5", "-5"),
            ("+5", "5"),
            ("-(-5)", "5"),
            ("3*-2", "-6"),
            ("3--2", "5"),
            ("-3*-2", "6"),
            ("2^-3", "0.125"),
            ("-(2+3)", "-5"),
            ("-2^2", "-4"),
            ("(-2)^2", "4"),
        ],
    )
    def test_unary_sign(self, expression: str, expected: str) -> None:
        """一元正负号。

        ``-2^2 = -4`` 而不是 4：数学惯例规定幂的优先级高于一元负号。
        想要 4 必须显式写 ``(-2)^2``。
        """
        assert calculate(expression).result_text == expected

    @pytest.mark.parametrize(
        ("expression", "expected"),
        [
            ("2^10", "1024"),
            ("2^3^2", "512"),          # 右结合
            ("9^0.5", "3"),
            ("0^0", "1"),              # 0 的 0 次幂约定为 1
            ("5!", "120"),
            ("0!", "1"),
            ("50%", "0.5"),
            ("200*10%", "20"),
            ("7 mod 3", "1"),
            ("-7 mod 3", "-1"),        # 符号跟随被除数
            ("sqrt(16)", "4"),
            ("sqrt(2)", "1.414213562373"),
            ("cbrt(27)", "3"),
            ("2pi", "6.28318530718"),
            ("(1+2)(3+4)", "21"),
            ("max(1,5,3)", "5"),
            ("min(1,5,3)", "1"),
            ("abs(-7)", "7"),
            ("floor(3.7)", "3"),
            ("ceil(3.2)", "4"),
            ("round(3.14159,2)", "3.14"),
            ("sign(-9)", "-1"),
            ("fact(5)", "120"),
            ("pow(2,8)", "256"),
            ("log(1000)", "3"),
            ("log(8,2)", "3"),
            ("ln(e)", "1"),
            ("exp(0)", "1"),
        ],
    )
    def test_extended_operators(self, expression: str, expected: str) -> None:
        """扩展运算符与函数。"""
        assert calculate(expression).result_text == expected


# ===================================================================== #
# 三、角度制
# ===================================================================== #
class TestAngleMode:
    """三角函数的角度制切换（扩展功能）。"""

    def test_degree_mode(self) -> None:
        assert calculate("sin(30)", "deg").result_text == "0.5"
        assert calculate("cos(60)", "deg").result_text == "0.5"
        assert calculate("tan(45)", "deg").result_text == "1"

    def test_radian_mode(self) -> None:
        assert calculate("sin(0)", "rad").result_text == "0"
        assert calculate("cos(0)", "rad").result_text == "1"

    def test_degree_mode_avoids_float_noise(self) -> None:
        """``sin(180°)`` 必须是 0，而不是 1.2246467991473532e-16。

        这是"浮点结果整平"要解决的问题：标准库 ``math.sin(math.radians(180))``
        返回的是浮点噪声。
        """
        assert calculate("sin(180)", "deg").result_text == "0"
        assert calculate("cos(90)", "deg").result_text == "0"

    def test_unknown_angle_mode_falls_back_to_radian(self) -> None:
        """非法的角度制退化为弧度，而不是抛异常。"""
        assert calculate("sin(0)", "banana").result_text == "0"


# ===================================================================== #
# 四、异常处理（作业 Feature 2 的"非法表达式""除零"）
# ===================================================================== #
class TestErrorHandling:
    """异常路径。"""

    @pytest.mark.parametrize(
        ("expression", "code"),
        [
            ("1/0", ErrorCode.DIVISION_BY_ZERO),
            ("0/0", ErrorCode.DIVISION_BY_ZERO),
            ("-5/0", ErrorCode.DIVISION_BY_ZERO),
            ("1/(2-2)", ErrorCode.DIVISION_BY_ZERO),
            ("5 mod 0", ErrorCode.DIVISION_BY_ZERO),
            ("0^-1", ErrorCode.DIVISION_BY_ZERO),
        ],
    )
    def test_division_by_zero(self, expression: str, code: ErrorCode) -> None:
        with pytest.raises(CalculatorError) as excinfo:
            calculate(expression)
        assert excinfo.value.code == code

    @pytest.mark.parametrize(
        "expression",
        ["", "   ", "\t", "\n"],
    )
    def test_empty_expression(self, expression: str) -> None:
        with pytest.raises(CalculatorError) as excinfo:
            calculate(expression)
        assert excinfo.value.code == ErrorCode.EMPTY_EXPRESSION

    @pytest.mark.parametrize(
        "expression",
        [
            "1+", "*5", "1+*2", "(1+2", "1+2)", "()", "1..2", "1 2",
            "2^^3", "sin()", "sin(1,2)", "1++", "(((1+2)",
        ],
    )
    def test_syntax_errors(self, expression: str) -> None:
        with pytest.raises(CalculatorError) as excinfo:
            calculate(expression)
        assert excinfo.value.code in (
            ErrorCode.SYNTAX_ERROR,
            ErrorCode.UNKNOWN_FUNCTION,
        )

    @pytest.mark.parametrize(
        ("expression", "code"),
        [
            ("@", ErrorCode.ILLEGAL_CHARACTER),
            ("1+$", ErrorCode.ILLEGAL_CHARACTER),
            ("1#2", ErrorCode.ILLEGAL_CHARACTER),
            ("foo(1)", ErrorCode.UNKNOWN_FUNCTION),
            ("abc", ErrorCode.UNKNOWN_FUNCTION),
            ("sqrt(-1)", ErrorCode.DOMAIN_ERROR),
            ("ln(0)", ErrorCode.DOMAIN_ERROR),
            ("ln(-1)", ErrorCode.DOMAIN_ERROR),
            ("log(0)", ErrorCode.DOMAIN_ERROR),
            ("asin(2)", ErrorCode.DOMAIN_ERROR),
            ("(-8)^0.5", ErrorCode.DOMAIN_ERROR),
            ("(-1)!", ErrorCode.DOMAIN_ERROR),
            ("1.5!", ErrorCode.DOMAIN_ERROR),
            ("2^999999999", ErrorCode.DOMAIN_ERROR),
        ],
    )
    def test_specific_error_codes(self, expression: str, code: ErrorCode) -> None:
        with pytest.raises(CalculatorError) as excinfo:
            calculate(expression)
        assert excinfo.value.code == code

    def test_expression_too_long(self) -> None:
        with pytest.raises(CalculatorError) as excinfo:
            calculate("1+" * 400 + "1")
        assert excinfo.value.code == ErrorCode.EXPRESSION_TOO_LONG

    def test_nesting_too_deep(self) -> None:
        with pytest.raises(CalculatorError) as excinfo:
            calculate("(" * 200 + "1" + ")" * 200)
        assert excinfo.value.code == ErrorCode.SYNTAX_ERROR

    def test_error_message_is_user_friendly(self) -> None:
        """错误信息必须能直接展示给用户。"""
        with pytest.raises(CalculatorError) as excinfo:
            calculate("1/0")
        assert "0" in excinfo.value.message
        assert excinfo.value.message == "除数不能为 0"


# ===================================================================== #
# 五、安全性：绝不执行用户输入
# ===================================================================== #
class TestSecurity:
    """证明用户输入不会被当成代码执行。"""

    @pytest.mark.parametrize(
        "expression",
        [
            "__import__('os').system('echo pwned')",
            "open('/etc/passwd').read()",
            "1; import os",
            "eval('1+1')",
            "lambda: 1",
            "[].__class__",
            "().__class__.__bases__",
            "os.system('dir')",
            "1 if True else 2",
        ],
    )
    def test_code_injection_is_rejected(self, expression: str) -> None:
        """任何"看起来像代码"的输入都必须被当作非法表达式拒绝。"""
        with pytest.raises(CalculatorError):
            calculate(expression)

    def test_calculator_module_has_no_dangerous_calls(self) -> None:
        """静态检查：计算器内核里不允许出现任何"执行代码"的调用。

        把"禁止使用 eval"从口头约定变成**可自动验证的约束**：
        只要有人往内核里加了 ``eval`` / ``exec`` / ``compile`` /
        ``ast.literal_eval`` / ``os.system`` 之类的东西，测试立刻变红。

        这里用 ``ast`` 做真正的语法树分析，而不是简单的字符串查找——
        后者会把文档字符串里"本项目禁止使用 eval"这样的说明文字误判为违规。
        """
        import ast
        from pathlib import Path

        calculator_dir = Path(__file__).resolve().parent.parent / "app" / "calculator"

        #: 形如 ``eval(...)`` 的裸函数调用
        forbidden_calls = {"eval", "exec", "compile", "__import__"}
        #: 形如 ``xxx.literal_eval(...)`` / ``os.system(...)`` 的属性调用
        forbidden_methods = {
            "literal_eval", "system", "popen", "spawn", "spawnl", "spawnv",
            "Popen", "check_output", "check_call", "run_module",
        }

        violations: list[str] = []
        for path in sorted(calculator_dir.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if isinstance(func, ast.Name) and func.id in forbidden_calls:
                    violations.append(f"{path.name}:{node.lineno} 调用了 {func.id}()")
                if isinstance(func, ast.Attribute) and func.attr in forbidden_methods:
                    violations.append(f"{path.name}:{node.lineno} 调用了 .{func.attr}()")

        assert violations == [], "计算器内核中出现了危险的代码执行调用：" + "; ".join(violations)

    def test_calculator_imports_nothing_dangerous(self) -> None:
        """内核只依赖标准库的安全子集，不引入任何"表达式求值"第三方库。"""
        import ast
        from pathlib import Path

        calculator_dir = Path(__file__).resolve().parent.parent / "app" / "calculator"
        allowed_stdlib = {
            "math", "decimal", "dataclasses", "enum", "typing", "__future__",
        }
        imported: set[str] = set()

        for path in sorted(calculator_dir.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imported.add(node.module.split(".")[0])

        unexpected = imported - allowed_stdlib
        assert unexpected == set(), f"计算器内核引入了预期之外的依赖：{sorted(unexpected)}"


# ===================================================================== #
# 六、词法分析器
# ===================================================================== #
class TestTokenizer:
    """词法分析。"""

    def test_token_stream(self) -> None:
        tokens = tokenize("1+2*3")
        types = [t.type for t in tokens]
        assert types == [
            TokenType.NUMBER, TokenType.OPERATOR, TokenType.NUMBER,
            TokenType.OPERATOR, TokenType.NUMBER, TokenType.EOF,
        ]

    def test_positions_are_recorded(self) -> None:
        tokens = tokenize("12+8")
        assert tokens[0].position == 0
        assert tokens[1].position == 2
        assert tokens[2].position == 3

    def test_identifier_and_number(self) -> None:
        tokens = tokenize("sin(30)")
        assert tokens[0].type is TokenType.IDENTIFIER
        assert tokens[0].value == "sin"
        assert tokens[1].type is TokenType.LPAREN

    def test_normalize_fullwidth(self) -> None:
        assert normalize_expression("１２×３") == "12*3"
        assert normalize_expression("（１＋２）÷３") == "(1+2)/3"

    def test_whitespace_is_ignored(self) -> None:
        assert calculate("  1   +   2  ").result_text == "3"


# ===================================================================== #
# 七、语法分析器（AST 结构）
# ===================================================================== #
class TestParser:
    """语法分析产出的 AST 结构。"""

    def test_precedence_shape(self) -> None:
        """``1+2*3`` 的根节点必须是 ``+``，右子节点是 ``*``。"""
        from app.calculator.ast_nodes import BinaryOpNode

        tree = parse("1+2*3")
        assert isinstance(tree, BinaryOpNode)
        assert tree.op == "+"
        assert isinstance(tree.right, BinaryOpNode)
        assert tree.right.op == "*"

    def test_right_associative_power(self) -> None:
        """``2^3^2`` 必须是 ``2^(3^2)``。"""
        from app.calculator.ast_nodes import BinaryOpNode

        tree = parse("2^3^2")
        assert isinstance(tree, BinaryOpNode)
        assert tree.op == "^"
        assert isinstance(tree.right, BinaryOpNode)
        assert tree.right.op == "^"


# ===================================================================== #
# 八、结果格式化
# ===================================================================== #
class TestFormatter:
    """展示格式化规则。"""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (Decimal("0"), "0"),
            (Decimal("1"), "1"),
            (Decimal("1.0"), "1"),          # 归一化掉尾随 .0
            (Decimal("20.0"), "20"),
            (Decimal("-5"), "-5"),
            (Decimal("3.14"), "3.14"),
            (Decimal("0.5"), "0.5"),
            (Decimal("1E+2"), "100"),
            (Decimal("1e-15"), "1e-15"),    # 极小值用科学计数法
            # 巨大整数仍然完整输出（不做科学计数法截断）
            (Decimal("1.23456789012345e+20"), "123456789012345000000"),
            # 巨大且非整数时改用科学计数法
            (Decimal("123456789012345678901.5"), "1.23456789012e20"),
        ],
    )
    def test_format(self, value: Decimal, expected: str) -> None:
        assert format_decimal(value) == expected

    def test_non_integer_rounds_to_12_decimals(self) -> None:
        assert format_decimal(Decimal(1) / Decimal(3)) == "0.333333333333"

    def test_large_integer_is_not_truncated(self) -> None:
        """大整数必须完整输出（100! 有 158 位）。"""
        text = calculate("100!").result_text
        assert len(text) == 158
        assert text.startswith("9332621544394415268169923885626670049071596826438162146859296389521")
