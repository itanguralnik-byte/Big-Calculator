# calc_logic.py
import re
from fractions import Fraction
import io
import sys
import math
import ast
import operator

# ============================================================
#                  CONFIGURATION
# ============================================================

# Maximum recursion depth to prevent StackOverflow/Crash on deep nesting
MAX_RECURSION_DEPTH = 50 

# ============================================================
#                  CUSTOM EXCEPTION
# ============================================================

class CalculationError(Exception):
    """Custom exception for errors during calculation."""
    pass

# ============================================================
#                 AST SECURITY LAYER
# ============================================================

# Whitelist allowed operations. 
ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Whitelist allowed functions (Scientific Math)
WHITELISTED_FUNCTIONS = {
    # Basic
    "abs": abs,
    "round": round,
    "sqrt": math.sqrt,
    "cbrt": math.cbrt if hasattr(math, "cbrt") else lambda x: x**(1/3),
    "exp": math.exp,
    "ln": math.log,         # Natural log
    "log": math.log10,      # Base-10 log by default (user expectation)
    "log10": math.log10,
    "log2": math.log2,
    "factorial": math.factorial,
    
    # Trigonometry (Radians)
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    
    # Constants/Misc
    "degrees": math.degrees,
    "radians": math.radians,
}

def _safe_eval_ast(node):
    """
    Recursively evaluates an AST node if and only if it is a number,
    a whitelisted operator, or a whitelisted function call.
    """
    if isinstance(node, (ast.Constant, ast.Num)): # Handle Python 3.8+ and older
        return node.n if isinstance(node, ast.Num) else node.value
        
    elif isinstance(node, ast.BinOp):
        op_func = ALLOWED_OPERATORS.get(type(node.op))
        if op_func:
            left = _safe_eval_ast(node.left)
            right = _safe_eval_ast(node.right)
            # Safety check for massive exponents
            if op_func is operator.pow:
                if abs(right) > 100: 
                    raise CalculationError("Exponent too large")
            return op_func(left, right)
            
    elif isinstance(node, ast.UnaryOp):
        op_func = ALLOWED_OPERATORS.get(type(node.op))
        if op_func:
            return op_func(_safe_eval_ast(node.operand))

    elif isinstance(node, ast.Call):
        # Handle function calls like sin(30) or sqrt(100)
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in WHITELISTED_FUNCTIONS:
                # Recursively evaluate all arguments
                args = [_safe_eval_ast(arg) for arg in node.args]
                try:
                    return WHITELISTED_FUNCTIONS[func_name](*args)
                except ValueError as ve:
                    raise CalculationError(f"Math Domain Error in '{func_name}': {ve}")
                except TypeError as te:
                    raise CalculationError(f"Invalid arguments for '{func_name}': {te}")
            else:
                raise CalculationError(f"Function '{func_name}' is not allowed.")
            
    # If the node is anything else (Attribute, Import, ListComps, etc.), REJECT IT.
    raise CalculationError("Security Violation: Unauthorized syntax detected.")

# ============================================================
#                 PURE HELPER FUNCTIONS
# ============================================================

# Compile regex for efficiency (Added comma for func args)
DISALLOWED_CHARS_REGEX = re.compile(r"[^a-z0-9+\-*/%()[\]{}=;._\s,]") 

def sanitize_input(expr_str):
    """
    Replaces common Unicode math symbols, full-width characters,
    converts to lowercase, and strips any disallowed characters.
    """
    if not isinstance(expr_str, str):
        return expr_str

    expr_str = expr_str.lower()

    replacements = {
        # Math Operators
        "\u2212": "-", "\u22C5": "*", "\u00D7": "*", "\u00F7": "/",
        # Exponents
        "\u005E": "**", "\u00B2": "**2", "\u00B3": "**3", "\u00B9": "**1",
        # Full-width Math
        "\uFF0B": "+", "\uFF0D": "-", "\uFF0A": "*", "\uFF0F": "/",
        "\uFF1D": "=", "\uFF05": "%", "\uFF0E": ".",
        # Full-width Brackets
        "\uFF08": "(", "\uFF09": ")", "\uFF3B": "[", "\uFF3D": "]",
        "\uFF5B": "{", "\uFF5D": "}",
        # Full-width Semicolon
        "\uFF1B": ";",
        # Full-width Numbers (0-9)
        "\uFF10": "0", "\uFF11": "1", "\uFF12": "2", "\uFF13": "3", "\uFF14": "4",
        "\uFF15": "5", "\uFF16": "6", "\uFF17": "7", "\uFF18": "8", "\uFF19": "9",
        # Common Spaces
        "\u3000": " ", "\u00A0": " ",
        # PI Symbol
        "\u03C0": "pi"
    }

    for uni, asc in replacements.items():
        expr_str = expr_str.replace(uni, asc)
    
    expr_str = DISALLOWED_CHARS_REGEX.sub("", expr_str)
    expr_str = expr_str.replace("%", " % ")
    
    return expr_str

def convert_mixed_numbers(expr):
    """Converts mixed number notations (e.g., '1 1/2') to parsable expressions."""
    pattern = r"(\d+)\s+(\d+/\d+)"
    def repl(match):
        return f"({match.group(1)}+({match.group(2)}))"
    return re.sub(pattern, repl, expr)

def split_top_level_equation(expr):
    """Splits an equation at the main '=' sign, ignoring '=' inside brackets."""
    level = 0
    for i, ch in enumerate(expr):
        if ch in "([{": level += 1
        elif ch in ")]}": level -= 1
        elif ch == "=" and level == 0:
            return expr[:i], expr[i + 1 :]
    return None

# ============================================================
#                 CALCULATOR CLASS
# ============================================================

class Calculator:
    """
    Encapsulates all logic and state for a single calculation run.
    """
    def __init__(self, mode, show_steps):
        # Configuration
        self.return_fraction = (mode == "fraction")
        self.show_steps = show_steps
        
        # State
        self.variables = {}     
        self.step_log = []      
        self.step_count = 0     

    def _log_step(self, message):
        """Internal helper to add a message to the step log if enabled."""
        if self.show_steps:
            self.step_log.append(message)

    def _normalize_unary_minus(self, expr: str) -> str:
        """Normalizes unary minus occurrences for the parser."""
        if not isinstance(expr, str): return expr
        expr = re.sub(r"\s+", "", expr)
        expr = re.sub(r"^\-", "0-", expr)
        expr = re.sub(r"([\(\[\{])\-", r"\g<1>0-", expr)
        return expr

    def _calculate_standard_expression(self, expr):
        """
        Evaluates a simple numeric expression string using SAFER AST parsing.
        """
        expr = expr.replace(" ", "")

        if re.search(r"[^a-z0-9+\-*/.%()eE,]", expr):
            expr = self._normalize_unary_minus(expr)
            if re.search(r"[^a-z0-9+\-*/.%()eE,]", expr):
                 self._log_step(f"  [Error] Calculation REJECTED (invalid chars): '{expr}'")
                 raise CalculationError(f"Invalid characters in numeric expression '{expr}'")

        try:
            tree = ast.parse(expr, mode='eval')
            value = _safe_eval_ast(tree.body)

            if self.return_fraction:
                try:
                    return Fraction(value).limit_denominator()
                except (ValueError, OverflowError):
                    return value
            return value

        except ZeroDivisionError:
            self._log_step("  [Error] Calculation FAILED: Division by zero")
            raise CalculationError("Cannot divide by zero")
        except SyntaxError as e:
            msg = str(e).lower()
            if "unexpected eof" in msg or "unmatched" in msg or "expected" in msg:
                self._log_step("  [Error] Calculation FAILED: Mismatched bracket")
                raise CalculationError("Mismatched or missing brackets")
            else:
                self._log_step(f"  [Error] Calculation FAILED: Syntax error {e}")
                raise CalculationError("Invalid syntax in expression")
        except CalculationError as e:
            raise e
        except Exception as e:
            self._log_step(f"  [Error] Calculation FAILED: {e}")
            raise CalculationError(f"An unexpected error occurred during calculation: {e}")

    def _convert_percentages_in_expr(self, expr):
        """Converts 'X% of Y' or 'X% Y' to '((X/100)*Y)' form."""
        pattern = r"((?<![\d.])-?\d+(?:\.\d+)?)\s*%\s*(?:of\s*)?(-?\d+(?:\.\d+)?)"
        
        def repl(match):
            return f"((({match.group(1)})/100)*({match.group(2)}))"

        new_expr = re.sub(pattern, repl, expr, count=1)
        
        if new_expr != expr:
            if self.step_count >= 0:
                self.step_count += 1
                self._log_step(f"Step {self.step_count}: Converted percentage: {new_expr}")
            return new_expr, True
        return new_expr, False

    def _find_and_solve_innermost(self, expr, open_c, close_c, name, depth):
        """Finds and solves the first innermost bracket pair."""
        
        open_re = re.escape(open_c)
        close_re = re.escape(close_c)
        pattern = rf"{open_re}([^{open_re}{close_re}]+?){close_re}"
        
        m = re.search(pattern, expr)
        if not m:
            return expr, False

        inner, full = m.group(1), m.group(0)
        start_idx, end_idx = m.span()

        # --- IMPORTANT FIX: Check if this is a function call (e.g. sin(...)) ---
        is_func_call = False
        if start_idx > 0:
            preceding_char = expr[start_idx - 1]
            if re.match(r"[a-z0-9_]", preceding_char):
                is_func_call = True

        # Save and restore step count mode
        current_step_mode = self.step_count
        
        # Recursively solve the inner part
        solved = self._solve_expression(
            inner, 
            print_steps=False, 
            _is_recursive_call=True, 
            depth=depth + 1
        )
        
        self.step_count = current_step_mode
        
        if str(solved) != inner and self.step_count >= 0:
            self.step_count += 1
            self._log_step(f"Step {self.step_count}: Solved {name}: {inner} -> {solved}")

        solved_str = str(solved)
        
        need_paren = False
        if is_func_call:
            need_paren = True # Always keep parens for functions like sin(0)
        elif solved_str.startswith("-"):
            need_paren = True
        elif end_idx < len(expr) and expr[end_idx:end_idx+2] == "**":
            need_paren = True
        else:
            try:
                float(solved_str) 
            except ValueError:
                need_paren = True 

        replacement = f"({solved_str})" if need_paren else solved_str
        new_expr = expr[:start_idx] + replacement + expr[end_idx:]
        did_change = (new_expr != expr)
            
        return new_expr, did_change

    def _parse_linear(self, expr):
        """Parses a linear expression string (e.g., '2x - 5 + x')."""
        expr = self._normalize_unary_minus(expr.replace(" ", ""))
        expr = re.sub(r"(?<![\d.])x", "1x", expr)
        expr = expr.replace("-", "+-")

        parts = expr.split("+")
        a, b = Fraction(0), Fraction(0)

        for p in parts:
            if p == "": continue
            if "x" in p:
                coef = p.replace("x", "")
                if coef == "" or coef == "+": coef = "1"
                elif coef == "-": coef = "-1"
                a += Fraction(coef)
            else:
                evaluated_constant = self._calculate_standard_expression(p)
                b += evaluated_constant
                
        return a, b

    def _solve_equation(self, left, right):
        """Solves a linear equation 'ax + b = cx + d'."""
        self._log_step(f"Equation to solve: {left} = {right}")
        
        a1, b1 = self._parse_linear(left)
        a2, b2 = self._parse_linear(right)

        A = a1 - a2
        B = b2 - b1

        if A == 0:
            return "all real numbers satisfy the equation" if B == 0 else "no solution"

        x = (B / A).limit_denominator()
        
        if not self.return_fraction:
            x = float(x)

        return f"x = {x}"

    def _substitute_variables(self, expr):
        """Applies all stored variable substitutions to an expression."""
        if not self.variables:
            return expr

        original_expr = expr
        substituted_expr = expr

        sorted_assignments = sorted(
            self.variables.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )

        for var_name, var_value in sorted_assignments:
            val_str = str(var_value)
            val_str_paren = f"({val_str})"
            var_name_re = re.escape(var_name)
            word_chars = r"a-z0-9_"

            coef_regex = rf"\b(?P<coef>(\d+(\.\d*)?|\.\d+)){var_name_re}\b"
            substituted_expr = re.sub(
                coef_regex, rf"\g<coef>*({val_str})", substituted_expr
            )
            pre_regex = rf"(?P<pre>[{word_chars}\)\]\}}]}}])(\s*)\b{var_name_re}\b"
            substituted_expr = re.sub(
                pre_regex, rf"\g<pre>*{val_str_paren}", substituted_expr
            )
            post_regex = rf"\b{var_name_re}\b(\s*)(?P<post>[{word_chars}\(\[\{{{{])"
            substituted_expr = re.sub(
                post_regex, rf"{val_str_paren}*\g<post>", substituted_expr
            )
            standalone_regex = rf"\b{var_name_re}\b"
            substituted_expr = re.sub(
                standalone_regex, val_str_paren, substituted_expr
            )
        
        if substituted_expr != original_expr:
            self._log_step(f"Substituted '{var_name}': {substituted_expr}")
        
        return substituted_expr

    def _substitute_constants(self, expr):
        """Substitutes constants like pi with their numeric value."""
        return re.sub(r"\bpi\b", str(math.pi), expr)

    def _solve_expression(self, expr_str, print_steps=True, _is_recursive_call=False, depth=0):
        """
        Main function to solve a mathematical expression or equation.
        """
        if depth > MAX_RECURSION_DEPTH:
            raise CalculationError("Expression too complex: maximum recursion depth exceeded.")

        expr_str = sanitize_input(expr_str)
        expr = convert_mixed_numbers(expr_str).replace(" ", "")
        expr = self._normalize_unary_minus(expr)

        if not _is_recursive_call:
            expr = self._substitute_constants(expr)
            expr = self._substitute_variables(expr)
            expr = self._normalize_unary_minus(expr) 

        if not print_steps:
            self.step_count = -1
        elif print_steps and all(ch not in expr for ch in "()[]{}") and not re.search(r"%\s*(?:of\b\s*)?", expr):
            self.step_count = -1
        elif not _is_recursive_call:
            self.step_count = 0

        eq = split_top_level_equation(expr)
        if eq is not None:
            L, R = eq
            LS = self._solve_expression(L, print_steps=False, _is_recursive_call=True, depth=depth + 1)
            RS = self._solve_expression(R, print_steps=False, _is_recursive_call=True, depth=depth + 1)
            return self._solve_equation(str(LS), str(RS))

        precedence = [
            ("(", ")", "parentheses"),
            ("[", "]", "brackets"),
            ("{", "}", "braces"),
        ]

        changed = True
        while changed:
            changed = False
            for o, c, n in precedence:
                expr, updated = self._find_and_solve_innermost(expr, o, c, n, depth)
                if updated:
                    changed = True
                    break
            if not changed:
                expr, updated_percentage = self._convert_percentages_in_expr(expr)
                if updated_percentage:
                    changed = True

        if "x" in expr and "sin" not in expr and "cos" not in expr:
            try:
                a, b = self._parse_linear(expr)
                
                if not self.return_fraction:
                    a, b = float(a), float(b)

                ax = f"{a}x" if a != 0 else ""
                if a == 1: ax = "x"
                elif a == -1: ax = "-x"
                
                bs = ""
                if b > 0: bs = f"+{b}"
                elif b < 0: bs = f"{b}"
                
                if ax and bs: return f"{ax}{bs}"
                elif ax: return ax
                elif b != 0: return str(b)
                else: return "0"
            except:
                pass

        return self._calculate_standard_expression(expr)

    def process_input_line(self, raw_line):
        """
        Processes a single, full line of input.
        """
        if not raw_line.strip():
            return ""

        output_log = []

        raw_line = sanitize_input(raw_line)
        parts = [p.strip() for p in raw_line.split(";") if p.strip()]
        expression_to_solve = ""
        is_equation_for_x = False

        for i, part in enumerate(parts):
            match = re.match(r"^\s*([a-z_][a-z0-9_]*)\s*=(.*)", part)
            if match:
                var_name = match.group(1)
                value_expr_str = match.group(2).strip()
                
                if not value_expr_str:
                     raise CalculationError(f"No value provided for assignment of '{var_name}'")

                solved_value = self._solve_expression(
                    value_expr_str, 
                    print_steps=False, 
                    _is_recursive_call=False,
                    depth=0
                )
                
                if isinstance(solved_value, str) and "x" in solved_value and var_name == "x":
                    expression_to_solve = part
                    is_equation_for_x = True
                    break
                elif isinstance(solved_value, str) and "x" in solved_value:
                    raise CalculationError(
                        f"Invalid assignment for '{var_name}'. "
                        f"Result '{solved_value}' still contains 'x'."
                    )
                else:
                    self.variables[var_name] = solved_value
                    output_log.append(f"Assigned: {var_name} = {solved_value}")
            else:
                expression_to_solve = part.rstrip("?")
                if i == len(parts) - 1 or "=" in part:
                    break
                else:
                    expression_to_solve = ""

        if not is_equation_for_x and not expression_to_solve and parts:
            if self.variables:
                output_log.append("Assignments active:")
                for var, val in self.variables.items():
                    output_log.append(f"  {var} = {val}")
            else:
                raise CalculationError(f"Could not parse expression: '{raw_line}'")
        
        elif not parts:
            return ""
        else:
            result = self._solve_expression(
                expression_to_solve, 
                print_steps=self.show_steps,
                depth=0
            )
            
            if self.show_steps and self.step_log:
                output_log.extend(self.step_log)
                output_log.append("") 
            
            output_log.append(f"Result: {result}")

        return "\n".join(output_log)

# ============================================================
#               MAIN PUBLIC INTERFACE
# ============================================================

def run_calculator(mode, expression_lines, show_steps=False):
    """
    Public-facing function to run the calculator.
    """
    
    full_output_log = []
    
    calc = Calculator(mode, show_steps)
    
    valid_lines_count = 0
    for line in expression_lines:
        if not line.strip(): continue
        
        calc.step_log = []
        
        if valid_lines_count > 0:
            full_output_log.append("\n" + ("-" * 10) + "\n") 

        try:
            line_result_str = calc.process_input_line(line)
            
            if line_result_str:
                full_output_log.append(line_result_str)
                valid_lines_count += 1

        except CalculationError as e:
            full_output_log.append(f"Error: {e}")
        except Exception as e:
            full_output_log.append(f"System Error: {e}")
            
    return "\n".join(full_output_log)


if __name__ == "__main__":
    print("Clean Calculator CLI")
    print("Type 'quit' to exit.")

    current_mode = "float" 
    mode_input = input("\nMode (f/fraction) [default: float]: ").strip().lower()
    if mode_input in ["fraction", "f"]:
        current_mode = "fraction"
    
    calc = Calculator(current_mode, show_steps=False)

    while True:
        try:
            raw = input(f"[{current_mode}] Expr: ")
            
            if raw.lower() in ("quit", "exit"): break
            if not raw.strip(): continue

            output_string = calc.process_input_line(raw)
            
            print(output_string)
            
        except Exception as e:
            print(f"Error: {e}")