# calc_logic.py
import sys
import math
import statistics
import ast
import unicodedata 
import html
import re
from fractions import Fraction
import sympy
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
    convert_xor,
    split_symbols
)
from sympy import (
    symbols, Symbol, Eq, solve, simplify, expand, factor, 
    diff, integrate, limit, oo, zoo, I, pi, E, Rational,
    Integer, Float, latex, Function
)

# ============================================================
#                 GLOBAL STATE (PERSISTENCE)
# ============================================================

SESSION_VARIABLES = {}

# ============================================================
#               AST-BASED SECURITY ENGINE
# ============================================================

class SecurityError(Exception):
    """Raised when unsafe code patterns are detected."""
    pass

class CalculationError(Exception):
    """Custom exception for general calculator errors."""
    pass

class SafeVisitor(ast.NodeVisitor):
    """
    AST Visitor that ensures only whitelisted operations are present.
    It blocks attributes, imports, lambdas, and dangerous functions.
    """
    
    # Whitelist of allowed AST Node types
    ALLOWED_NODES = {
        ast.Module, ast.Expr, ast.Load, ast.Store,
        ast.Expression,
        # Literals
        ast.Constant, ast.Num, ast.NameConstant,
        # Data Structures (Allowed for stats functions)
        ast.List, ast.Tuple,
        # Operations
        ast.UnaryOp, ast.BinOp, ast.Compare,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod,
        ast.USub, ast.UAdd, ast.BitXor, # Allowed because SymPy treats ^ as power
        ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
        # Variables & Calls
        ast.Name, ast.Call
    }

    # Explicitly forbidden functions (Blacklist)
    # Since we use a sandboxed execution environment (empty __builtins__), 
    # we can allow unknown functions (like 'y(x)') for implicit multiplication,
    # but we strictly block these to prevent introspection or escape attempts.
    FORBIDDEN_FUNCS = {
        'eval', 'exec', 'compile', 'open', 'input', 'print', 'help', 
        'globals', 'locals', 'vars', 'dir', 'exit', 'quit', '__import__',
        'getattr', 'setattr', 'delattr', 'hasattr', 'super', 'type'
    }

    def __init__(self, allowed_functions, allowed_variables):
        self.allowed_functions = allowed_functions
        self.allowed_variables = allowed_variables

    def generic_visit(self, node):
        """Called for every node. If node type isn't allowed, raise error."""
        if type(node) not in self.ALLOWED_NODES:
            raise SecurityError(f"Security Error: Operation '{type(node).__name__}' is not allowed.")
        super().generic_visit(node)

    def visit_Attribute(self, node):
        """Block ALL dot access (e.g. x.__class__)"""
        raise SecurityError("Security Error: Object attribute access (.) is forbidden.")

    def visit_Call(self, node):
        """
        Validate function calls.
        We allow:
        1. Whitelisted math functions (sin, cos)
        2. Unknown functions (y, f) - strictly for symbolic math/implicit mult support.
        
        We REJECT:
        1. Complex calls (x.y()) - handled by visit_Attribute but double checked here.
        2. Dangerous built-ins (eval, open).
        """
        # We only allow direct function calls like sin(x), not math.sin(x)
        if not isinstance(node.func, ast.Name):
            raise SecurityError("Security Error: Complex function calls are forbidden.")
        
        func_name = node.func.id
        
        # 1. Block Internal names
        if func_name.startswith("__"):
             raise SecurityError(f"Security Error: Internal function '{func_name}' forbidden.")

        # 2. Block Dangerous Built-ins (Blacklist)
        if func_name in self.FORBIDDEN_FUNCS:
            raise SecurityError(f"Security Error: Function '{func_name}' is not allowed.")

        # 3. Allow everything else. 
        # Rationale: If user calls 'y(x)', it might be implicit multiplication (y*x)
        # or a symbolic function. The runtime sandbox (empty __builtins__) prevents
        # malicious execution if 'y' is actually a dangerous function we missed.
        
        self.generic_visit(node)

    def visit_Name(self, node):
        """Allow writing to new variables, but restrict reading."""
        if isinstance(node.ctx, ast.Load):
            if node.id.startswith("__"):
                raise SecurityError("Security Error: Internal variables forbidden.")
        self.generic_visit(node)


def validate_safe_code(code_str, allowed_funcs, allowed_vars):
    """
    Parses code into AST and runs the SecurityVisitor.
    """
    # 1. Pre-process for Implicit Multiplication support in AST
    # Python's AST parser doesn't understand '2x' or '(a)(b)'.
    # We normalize these patterns strictly for the validation step to prevent
    # "Call" nodes (e.g. '2(x)') appearing where multiplication is intended.
    # Pattern matches:
    #   - Digit followed by Letter or '('   => 2x, 2(x)
    #   - ')' followed by Letter or '('     => (a)b, (a)(b)
    # Note: We do NOT convert 'y(x)' to 'y*(x)' here because it might be a valid function call.
    # We rely on SymPy's implicit_multiplication_application for that during execution.
    normalized_code = re.sub(r'(\d|\))\s*([a-zA-Z\(])', r'\1*\2', code_str)

    try:
        # 2. Parse into AST
        tree = ast.parse(normalized_code, mode='eval')
    except SyntaxError:
        # If it still fails parsing, it might be valid SymPy but invalid Python.
        # However, for security, we reject anything we can't inspect.
        raise CalculationError("Syntax Error: Input must be valid math expression.")

    # 3. Walk the tree
    visitor = SafeVisitor(allowed_funcs, allowed_vars)
    visitor.visit(tree)


# ============================================================
#                  CONFIGURATION
# ============================================================

TRANSFORMATIONS = (
    standard_transformations + 
    (implicit_multiplication_application, convert_xor, split_symbols)
)

def wrap_stat(func):
    def wrapper(*args):
        try:
            if len(args) == 1 and isinstance(args[0], (list, tuple, set)):
                data = [float(x) for x in args[0]]
            else:
                data = [float(x) for x in args]
            return func(data)
        except Exception as e:
            raise CalculationError(f"Statistics error: {str(e)}")
    return wrapper

SAFE_LOCALS = {
    # Core SymPy Types
    'Integer': Integer, 'Float': Float, 'Symbol': Symbol,
    'Rational': Rational, 'Function': Function,

    # Constants
    'pi': pi, 'e': E, 'E': E, 'i': I, 'oo': oo, 
    
    # Standard Math
    'sqrt': sympy.sqrt, 'cbrt': sympy.cbrt, 'abs': sympy.Abs,
    'exp': sympy.exp, 'ln': sympy.log, 'log': lambda x: sympy.log(x, 10),
    'sin': sympy.sin, 'cos': sympy.cos, 'tan': sympy.tan,
    'asin': sympy.asin, 'acos': sympy.acos, 'atan': sympy.atan,
    'sinh': sympy.sinh, 'cosh': sympy.cosh, 'tanh': sympy.tanh,
    'factorial': sympy.factorial, 'mod': sympy.Mod,
    
    # Calculus & Algebra
    'diff': diff, 'derive': diff, 'integrate': integrate,
    'limit': limit, 'simplify': simplify, 'expand': expand,
    'factor': factor, 'solve': solve,
    
    # Statistics
    'mean': wrap_stat(statistics.mean),
    'median': wrap_stat(statistics.median),
    'stdev': wrap_stat(statistics.stdev),
    'variance': wrap_stat(statistics.variance),
}

SAFE_GLOBALS = {"__builtins__": {}}

# ============================================================
#                 CALCULATOR ENGINE
# ============================================================

class Calculator:
    def __init__(self, mode="float", show_steps=False, stateless_mode=False):
        self.mode = mode 
        self.show_steps = show_steps
        self.stateless_mode = stateless_mode
        self.log = []
        
        if self.stateless_mode:
            self.variables = {}
        else:
            self.variables = SESSION_VARIABLES

    def _log(self, msg):
        if self.show_steps: self.log.append(msg)

    def _format_result(self, result):
        if result is None: return ""
        
        if isinstance(result, list):
            items = [self._format_result(x).replace("$$", "") for x in result]
            return "$$" + ", ".join(items) + "$$"
            
        if isinstance(result, dict):
            items = []
            for k, v in result.items():
                val_str = self._format_result(v).replace("$$", "")
                items.append(f"{k} = {val_str}")
            return "$$" + ", ".join(items) + "$$"

        try:
            def clean_val(val):
                if hasattr(val, "is_number") and val.is_number and not val.is_imaginary:
                    try:
                        val_rounded = round(float(val), 10)
                        if val_rounded == int(val_rounded): return Integer(int(val_rounded))
                        return Float(val_rounded)
                    except: return val
                return val

            final_val = result
            if self.mode == "fraction":
                if isinstance(result, Float): final_val = clean_val(result)
            else:
                if hasattr(result, "evalf"): final_val = clean_val(result.evalf())

            return f"$${latex(final_val)}$$"
        except Exception:
            return html.escape(str(result))

    def _get_step_wrappers(self):
        def tracked_diff(expr, *args):
            sym = args[0] if args else symbols('x')
            self._log(f"**Differentiating** $${latex(expr)}$$ with respect to $${latex(sym)}$$")
            result = diff(expr, *args)
            self._log(f"&rarr; **Result**: $${latex(result)}$$")
            return result

        def tracked_integrate(expr, *args):
            sym = args[0] if args and not isinstance(args[0], tuple) else symbols('x')
            self._log(f"**Integrating** $${latex(expr)}$$")
            result = integrate(expr, *args)
            self._log(f"&rarr; **Result**: $${latex(result)}$$")
            return result

        return { "diff": tracked_diff, "derive": tracked_diff, "integrate": tracked_integrate }

    def process_input_line(self, line):
        line = line.strip()
        if not line: return None
        if line.startswith("#") or line.startswith("//"): return None
        
        # Pre-Processing
        line = line.replace("%", "/100")
        line = unicodedata.normalize('NFKC', line)

        # 1. Basic String Checks (Defense in Depth)
        if "\\" in line: raise CalculationError("Security Error: Backslashes forbidden.")
        if "__" in line: raise CalculationError("Security Error: Internal variables forbidden.")
        if "lambda" in line or "λ" in line: raise CalculationError("Security Error: Lambda forbidden.")

        # 2. Setup Environment
        local_env = SAFE_LOCALS.copy()
        if self.show_steps: local_env.update(self._get_step_wrappers())
        if not self.stateless_mode: local_env.update(self.variables)
        
        valid_funcs = set(SAFE_LOCALS.keys())
        if self.show_steps: valid_funcs.update(["diff", "derive", "integrate"])
        valid_vars = set(self.variables.keys())

        try:
            # 3. Logic & AST Validation
            
            # Case A: Assignments (a = 5)
            # Only treat as assignment if we are NOT in stateless mode.
            if "=" in line and "==" not in line and "<=" not in line and ">=" not in line and "!=" not in line:
                parts = line.split("=", 1)
                lhs_str = parts[0].strip()
                rhs_str = parts[1].strip()

                if lhs_str.isidentifier() and not self.stateless_mode:
                    # Assignment
                    self._log(f"Assigning variable: {lhs_str}...")
                    validate_safe_code(rhs_str, valid_funcs, valid_vars)
                    
                    rhs_val = parse_expr(rhs_str, local_dict=local_env, global_dict=SAFE_GLOBALS, transformations=TRANSFORMATIONS)
                    
                    self.variables[lhs_str] = rhs_val
                        
                    if self.show_steps:
                        return f"Assigned: {lhs_str} = {self._format_result(rhs_val)}"
                    return None
                
                else:
                    # Equation (2x = 5) OR Stateless Assignment (x = 5 -> solve for x)
                    validate_safe_code(lhs_str, valid_funcs, valid_vars)
                    validate_safe_code(rhs_str, valid_funcs, valid_vars)
                    
                    self._log(f"Solving Equation: $${lhs_str} = {rhs_str}$$")
                    equation_env = local_env if not self.stateless_mode else SAFE_LOCALS.copy()
                    
                    lhs_expr = parse_expr(lhs_str, local_dict=equation_env, global_dict=SAFE_LOCALS, transformations=TRANSFORMATIONS)
                    rhs_expr = parse_expr(rhs_str, local_dict=equation_env, global_dict=SAFE_LOCALS, transformations=TRANSFORMATIONS)
                    
                    free_symbols = lhs_expr.free_symbols.union(rhs_expr.free_symbols)
                    if not free_symbols:
                        return "Result: " + ("True" if lhs_expr == rhs_expr else "False")
                    
                    symbol_to_solve = list(free_symbols)[0]
                    if symbols('x') in free_symbols: symbol_to_solve = symbols('x')
                    
                    solution = solve(Eq(lhs_expr, rhs_expr), symbol_to_solve)
                    return f"Result: {symbol_to_solve} = {self._format_result(solution)}"

            # Case B: Standard Expressions
            else:
                if "==" in line:
                    parts = line.split("==")
                    for p in parts: validate_safe_code(p, valid_funcs, valid_vars)
                else:
                    validate_safe_code(line, valid_funcs, valid_vars)

                expr = parse_expr(line, local_dict=local_env, global_dict=SAFE_GLOBALS, transformations=TRANSFORMATIONS)
                
                if expr == zoo or expr == oo or expr == -oo: raise CalculationError("Division by zero")
                if hasattr(expr, "is_real") and expr.is_real is False:
                     if expr.has(I) or expr.is_imaginary: raise CalculationError("Domain error: result is not real.")

                return f"Result: {self._format_result(expr)}"

        except SecurityError as se:
            raise CalculationError(str(se))
        except SyntaxError:
             raise CalculationError("Syntax Error: Invalid expression.")
        except Exception as e:
            error_message = str(e)
            if "Security" in error_message: raise CalculationError(error_message)
            if "name" in error_message and "is not defined" in error_message:
                raise CalculationError(f"Unknown variable or function: {error_message.split('name')[1]}")
            raise CalculationError(f"Calculation Error: {error_message}")

# ============================================================
#               MAIN PUBLIC INTERFACE
# ============================================================

def run_calculator(mode, expression_lines, show_steps=False, stateless_mode=False):
    calc = Calculator(mode, show_steps, stateless_mode)
    full_output = []
    
    if show_steps and expression_lines:
        full_output.append("<h4>Calculation Steps:</h4>")

    for i, line in enumerate(expression_lines):
        line = line.strip()
        if not line: continue
            
        try:
            result = calc.process_input_line(line)
            
            if calc.log:
                steps_html = "<ul class='steps-list'>" + "".join([f"<li>{step}</li>" for step in calc.log]) + "</ul>"
                full_output.append(steps_html)
                calc.log = [] 

            if result:
                full_output.append(result)
                
        except CalculationError as e:
            safe_error = html.escape(str(e))
            full_output.append(f"<span style='color:red'>{safe_error}</span>")

    vars_out = {}
    if not stateless_mode:
        for name, val in SESSION_VARIABLES.items():
            try:
                display_str = latex(val)
                if len(display_str) > 100: display_str = display_str[:97] + "..."
                vars_out[name] = { "display": f"$${display_str}$$", "raw": str(val) }
            except:
                vars_out[name] = {"display": "Error", "raw": ""}

    return "\n".join(full_output), vars_out

def delete_variable(var_name):
    if var_name in SESSION_VARIABLES:
        del SESSION_VARIABLES[var_name]
        return True
    return False