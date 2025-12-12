import sys
import math
import statistics
import re
import unicodedata 
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
#                  CONFIGURATION & SECURITY
# ============================================================

TRANSFORMATIONS = (
    standard_transformations + 
    (implicit_multiplication_application, convert_xor, split_symbols)
)

class CalculationError(Exception):
    """Custom exception for calculator errors to satisfy unit tests."""
    pass

# Helper for statistics functions to handle both lists and varargs
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

# Whitelist of allowed functions and constants
SAFE_LOCALS = {
    # Core SymPy Types
    'Integer': Integer,
    'Float': Float,
    'Symbol': Symbol,
    'Rational': Rational,
    'Function': Function,

    # Constants
    'pi': pi,
    'e': E,
    'E': E,
    'i': I,
    'oo': oo, 
    
    # Standard Math
    'sqrt': sympy.sqrt,
    'cbrt': sympy.cbrt,
    'abs': sympy.Abs,
    'exp': sympy.exp,
    'ln': sympy.log,
    'log': lambda x: sympy.log(x, 10),
    'sin': sympy.sin,
    'cos': sympy.cos,
    'tan': sympy.tan,
    'asin': sympy.asin,
    'acos': sympy.acos,
    'atan': sympy.atan,
    'sinh': sympy.sinh,
    'cosh': sympy.cosh,
    'tanh': sympy.tanh,
    'factorial': sympy.factorial,
    
    # Calculus & Algebra
    'diff': diff,
    'derive': diff,
    'integrate': integrate,
    'limit': limit,
    'simplify': simplify,
    'expand': expand,
    'factor': factor,
    'solve': solve,
    
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
        self.mode = mode  # 'float' or 'fraction'
        self.show_steps = show_steps
        self.stateless_mode = stateless_mode # New flag for stateless operation
        self.variables = {} 
        self.log = []

    def _log(self, msg):
        if self.show_steps:
            self.log.append(msg)

    def _format_result(self, result):
        """Formats the SymPy result into LaTeX wrapped in $$ delimiters."""
        if result is None:
            return ""
        
        # Handle Lists (e.g. multiple solutions)
        if isinstance(result, list):
            items = [self._format_result(x).replace("$$", "") for x in result]
            return "$$" + ", ".join(items) + "$$"
            
        # Handle Dicts
        if isinstance(result, dict):
            items = []
            for k, v in result.items():
                val_str = self._format_result(v).replace("$$", "")
                items.append(f"{k} = {val_str}")
            return "$$" + ", ".join(items) + "$$"

        try:
            # Helper to round floats before LaTeX conversion
            def clean_val(val):
                if hasattr(val, "is_number") and val.is_number and not val.is_imaginary:
                    try:
                        # Round to 10 decimal places to fix floating point artifacts
                        val_rounded = round(float(val), 10)
                        if val_rounded == int(val_rounded):
                            return Integer(int(val_rounded))
                        return Float(val_rounded)
                    except:
                        return val
                return val

            final_val = result
            
            if self.mode == "fraction":
                if isinstance(result, Float):
                    final_val = clean_val(result)
            else:
                # Float mode: Evaluate first, then clean
                if hasattr(result, "evalf"):
                    final_val = clean_val(result.evalf())

            return f"$${latex(final_val)}$$"

        except Exception:
            return str(result)

    def process_input_line(self, line):
        """
        Parses and executes a single line of input.
        """
        line = line.strip()
        if not line:
            return None

        # 1. Handle Comments
        if line.startswith("#") or line.startswith("//"):
            return None

        # ============================================================
        # SECURITY FIXES
        # ============================================================
        
        # 1. Unicode Normalization (Fixes Homoglyph Attacks)
        # Converts fullwidth chars like 'ｌ' to 'l' and '＿' to '_'
        line = unicodedata.normalize('NFKC', line)

        # 2. Block Obfuscation
        # Backslashes allow hex escapes like \x5f which hide keywords
        if "\\" in line:
             raise CalculationError("Security Error: Backslashes are forbidden to prevent obfuscation.")

        # 3. Block Introspection & Private Attributes
        # "__" catches dunder methods (__class__)
        # "._" catches private attributes (obj._private or obj._class_)
        if "__" in line or "._" in line:
            raise CalculationError("Security Error: Direct access to internal attributes is forbidden.")
        
        # 4. Block Injection
        if ".format(" in line:
            raise CalculationError("Security Error: String formatting is forbidden.")
            
        # 5. Block Dangerous Functions
        if "lambda" in line:
            raise CalculationError("Security Error: Lambda functions are forbidden.")

        # ============================================================

        # 2. Setup Environment
        local_env = SAFE_LOCALS.copy()
        
        # Only load saved variables if not in stateless mode
        if not self.stateless_mode: 
            local_env.update(self.variables)

        try:
            # 3. Handle Assignments vs Equations vs Expressions
            
            # Case A: Equality Check (Double Equals) -> Boolean Evaluation
            if "==" in line:
                expr = parse_expr(line, local_dict=local_env, global_dict=SAFE_GLOBALS, transformations=TRANSFORMATIONS)
                return f"Result: {self._format_result(expr)}"

            # Case B: Assignment or Equation (Single Equals)
            if "=" in line:
                # Split only on the first '='
                parts = line.split("=", 1)
                lhs_str = parts[0].strip()
                rhs_str = parts[1].strip()

                # Check if LHS is a valid variable name (Identifier)
                if lhs_str.isidentifier():
                    
                    if not self.stateless_mode:
                        # --- ASSIGNMENT LOGIC (Stateful Mode) ---
                        self._log(f"Detected assignment: {lhs_str} = {rhs_str}")
                        rhs_val = parse_expr(rhs_str, local_dict=local_env, global_dict=SAFE_GLOBALS, transformations=TRANSFORMATIONS)
                        
                        # Store result in memory
                        self.variables[lhs_str] = rhs_val
                        
                        if self.show_steps:
                            return f"Assigned: {lhs_str} = {self._format_result(rhs_val)}"
                        return None
                    else:
                        # --- EQUATION LOGIC (Stateless Mode) ---
                        # In stateless mode, treat x=5 as an equation to solve for x.
                        pass # Fall through to equation solving logic below
                
                # --- EQUATION SOLVING LOGIC (Used if LHS is not identifier OR in Stateless Mode) ---
                self._log(f"Detected equation: {lhs_str} = {rhs_str}")
                
                # Use base SAFE_LOCALS for equation parsing if in stateless mode
                equation_env = local_env if not self.stateless_mode else SAFE_LOCALS
                
                lhs_expr = parse_expr(lhs_str, local_dict=equation_env, global_dict=SAFE_LOCALS, transformations=TRANSFORMATIONS)
                rhs_expr = parse_expr(rhs_str, local_dict=equation_env, global_dict=SAFE_LOCALS, transformations=TRANSFORMATIONS)
                
                # Find free symbols to solve for
                free_symbols = lhs_expr.free_symbols.union(rhs_expr.free_symbols)
                
                if not free_symbols:
                    return "Result: " + ("True" if lhs_expr == rhs_expr else "False")
                
                # Prefer solving for 'x' if present, otherwise the first symbol found
                symbol_to_solve = list(free_symbols)[0]
                if symbols('x') in free_symbols:
                    symbol_to_solve = symbols('x')
                
                solution = solve(Eq(lhs_expr, rhs_expr), symbol_to_solve)
                return f"Result: {symbol_to_solve} = {self._format_result(solution)}"

            # Case C: Standard Expression Evaluation
            else:
                expr = parse_expr(line, local_dict=local_env, global_dict=SAFE_GLOBALS, transformations=TRANSFORMATIONS)
                
                result = expr
                
                # Check for Division by Zero
                if result == zoo or result == oo or result == -oo:
                    raise CalculationError("Division by zero")

                # FIX 2: Check for Complex Domain Errors
                if hasattr(result, "is_real") and result.is_real is False:
                    # Check for imaginary part presence (e.g., sqrt(-1) = I, log(-5) = 1.6 + 3.14I)
                    if result.has(I) or result.is_imaginary:
                        raise CalculationError("Domain error: result is not real.")

                return f"Result: {self._format_result(result)}"

        except Exception as e:
            # Check for SymPy specific errors that should be mapped to CalculationError
            error_message = str(e)
            if "argument of type 'int' is not iterable" in error_message or "Invalid parameters" in error_message:
                raise CalculationError(f"Function input error: {error_message}")
            if "NotImplementedError" in error_message:
                raise CalculationError(f"Feature not implemented: {error_message}")
            
            if "Security Error" in error_message:
                 raise CalculationError(error_message)

            # Default fallback for all other exceptions
            raise CalculationError(error_message)

# ============================================================
#               MAIN PUBLIC INTERFACE
# ============================================================

def run_calculator(mode, expression_lines, show_steps=False, stateless_mode=False):
    """
    Entry point called by app.py or tests
    """
    calc = Calculator(mode, show_steps, stateless_mode)
    full_output = []
    
    for i, line in enumerate(expression_lines):
        line = line.strip()
        if not line: continue
            
        try:
            result = calc.process_input_line(line)
            if result:
                full_output.append(result)
        except CalculationError as e:
            full_output.append(f"Error: {str(e)}")

    return "\n".join(full_output)