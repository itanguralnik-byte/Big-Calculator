# calc_logic.py
import sys
import math
import statistics
import re
import unicodedata 
import html  # [CRITICAL] Needed for XSS protection
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

# This dictionary holds variables across multiple "RUN" clicks.
SESSION_VARIABLES = {}

# ============================================================
#                  CONFIGURATION & SECURITY
# ============================================================

TRANSFORMATIONS = (
    standard_transformations + 
    (implicit_multiplication_application, convert_xor, split_symbols)
)

class CalculationError(Exception):
    """Custom exception for calculator errors."""
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
        self.stateless_mode = stateless_mode
        self.log = []
        
        # Link to the global session or use a fresh dict if stateless
        if self.stateless_mode:
            self.variables = {}
        else:
            self.variables = SESSION_VARIABLES

    def _log(self, msg):
        """Appends a message to the step log if steps are enabled."""
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
            # [Patch] Escape the fallback string to prevent XSS if latex() fails
            return html.escape(str(result))

    def _get_step_wrappers(self):
        """Returns custom wrappers for calculus functions to log steps."""
        
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

        return {
            "diff": tracked_diff,
            "derive": tracked_diff,
            "integrate": tracked_integrate
        }

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
        # SECURITY CHECKS
        # ============================================================
        line = unicodedata.normalize('NFKC', line)
        
        if "\\" in line: raise CalculationError("Security Error: Backslashes forbidden.")
        if "__" in line or "._" in line: raise CalculationError("Security Error: Internal access forbidden.")
        if ".format(" in line: raise CalculationError("Security Error: Formatting forbidden.")
        
        # Block 'lambda' keywords
        if "lambda" in line: raise CalculationError("Security Error: Lambda forbidden.")
        
        # [Patch] Explicitly block the Greek character 'λ' (lambda)
        # because NFKC normalization turns 𝜆 (U+1D706) into λ (U+03BB), 
        # and we must ensure no variant bypasses the logic.
        if "λ" in line: raise CalculationError("Security Error: Greek Lambda forbidden.") 
        # ============================================================

        # 2. Setup Environment
        local_env = SAFE_LOCALS.copy()
        
        # Inject Step Wrappers if enabled
        if self.show_steps:
            local_env.update(self._get_step_wrappers())

        if not self.stateless_mode: 
            local_env.update(self.variables)

        try:
            # 3. Parsing Logic
            
            # Equality Check (==)
            if "==" in line:
                expr = parse_expr(line, local_dict=local_env, global_dict=SAFE_GLOBALS, transformations=TRANSFORMATIONS)
                return f"Result: {self._format_result(expr)}"

            # Assignment or Equation (=)
            if "=" in line:
                parts = line.split("=", 1)
                lhs_str = parts[0].strip()
                rhs_str = parts[1].strip()

                if lhs_str.isidentifier():
                    if not self.stateless_mode:
                        # Assignment
                        self._log(f"Assigning variable: {lhs_str}...")
                        rhs_val = parse_expr(rhs_str, local_dict=local_env, global_dict=SAFE_GLOBALS, transformations=TRANSFORMATIONS)
                        self.variables[lhs_str] = rhs_val
                        if self.show_steps:
                            return f"Assigned: {lhs_str} = {self._format_result(rhs_val)}"
                        return None # No output for simple assignments unless steps shown
                    else:
                        # Fallthrough to Equation Solving in Stateless
                        pass 
                
                # Equation Solving
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

            # Expression Evaluation
            else:
                expr = parse_expr(line, local_dict=local_env, global_dict=SAFE_GLOBALS, transformations=TRANSFORMATIONS)
                
                # Validation
                if expr == zoo or expr == oo or expr == -oo: raise CalculationError("Division by zero")
                if hasattr(expr, "is_real") and expr.is_real is False:
                    if expr.has(I) or expr.is_imaginary: raise CalculationError("Domain error: result is not real.")

                return f"Result: {self._format_result(expr)}"

        except Exception as e:
            error_message = str(e)
            if "argument of type 'int' is not iterable" in error_message or "Invalid parameters" in error_message:
                raise CalculationError(f"Function input error: {error_message}")
            if "NotImplementedError" in error_message:
                raise CalculationError(f"Feature not implemented: {error_message}")
            if "Security Error" in error_message:
                 raise CalculationError(error_message)
            raise CalculationError(error_message)

# ============================================================
#               MAIN PUBLIC INTERFACE
# ============================================================

def run_calculator(mode, expression_lines, show_steps=False, stateless_mode=False):
    """
    Entry point called by app.py or tests.
    RETURNS: A Tuple (HTML_Output_String, Variables_Dict)
    """
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
            # [CRITICAL PATCH] Escape the error message to prevent XSS via exception injection
            # e.g. if user inputs <img src=x>, python error might contain the raw string.
            safe_error = html.escape(str(e))
            full_output.append(f"<span style='color:red'>Error: {safe_error}</span>")

    # Serialize Variables for the Sidebar
    vars_out = {}
    if not stateless_mode:
        for name, val in SESSION_VARIABLES.items():
            try:
                # Create a simple preview string (limit length)
                display_str = latex(val)
                # Truncate extremely long latex strings for the sidebar
                if len(display_str) > 100: 
                    display_str = display_str[:97] + "..."
                
                vars_out[name] = {
                    "display": f"$${display_str}$$",
                    "raw": str(val) # For insertion back into code
                }
            except:
                vars_out[name] = {"display": "Error", "raw": ""}

    return "\n".join(full_output), vars_out

def delete_variable(var_name):
    """Helper to remove a variable from the persistent session."""
    if var_name in SESSION_VARIABLES:
        del SESSION_VARIABLES[var_name]
        return True
    return False