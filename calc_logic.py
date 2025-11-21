# calc_logic.py
import re
from fractions import Fraction
import io
import sys

# ============================================================
#                 INPUT SANITIZATION (NEW)
# ============================================================

def sanitize_input(expr_str):
    """
    Replaces common Unicode math symbols and full-width characters
    with their ASCII equivalents before processing.
    """
    if not isinstance(expr_str, str):
        return expr_str  # Safety check

    replacements = {
        # Math Operators
        "\u2212": "-",  # Minus Sign (−)
        "\u22C5": "*",  # Dot Operator (⋅)
        "\u00D7": "*",  # Multiplication Sign (×)
        "\u00F7": "/",  # Division Sign (÷)

        # Full-width Brackets
        "\uFF08": "(",  # Full-width (
        "\uFF09": ")",  # Full-width )
        "\uFF3B": "[",  # Full-width [
        "\uFF3D": "]",  # Full-width ]
        "\uFF5B": "{",  # Full-width {
        "\uFF5D": "}",  # Full-width }
        
        # Common Spaces
        "\u3000": " ",  # Ideographic Space
        "\u00A0": " "   # Non-breaking Space
    }

    for uni, asc in replacements.items():
        expr_str = expr_str.replace(uni, asc)
    
    return expr_str

# ============================================================
#                 FRACTION OUTPUT SWITCH
# ============================================================

# This will be set by user input inside the main loop
RETURN_FRACTION = True

# Global variable to store assignments during the current execution flow
_CURRENT_VARIABLE_ASSIGNMENTS = {}  # Stores var_name -> Fraction value


# ============================================================
#                   BASIC NUMERIC EVAL
# ============================================================

def calculate_standard_expression(expr):
    """Evaluates a simple numeric expression string."""
    expr = expr.replace(" ", "")

    # Basic validation for allowed characters
    if not re.fullmatch(r"[0-9+\-*/.]+", expr):
        return None  # Not purely numeric

    try:
        # Use eval for simple math
        value = eval(expr)

        if RETURN_FRACTION:
            # Convert to fraction and limit denominator for cleaner output
            return Fraction(value).limit_denominator()

        # In float mode, just return the evaluated value
        return value

    except:
        # Catch errors like division by zero
        return None


# ============================================================
#         MIXED FRACTIONS: "4 1/2" → "(4 + (1/2))"
# ============================================================

def convert_mixed_numbers(expr):
    """Converts mixed number notations (e.g., '1 1/2') to parsable expressions."""
    # Pattern: one or more digits, whitespace, one or more digits/one or more digits
    pattern = r"(\d+)\s+(\d+/\d+)"

    def repl(match):
        """Replacement function to format as (whole + (fraction))."""
        whole = match.group(1)
        fraction = match.group(2)
        return f"({whole}+({fraction}))"

    # Use regex substitution to find all occurrences
    return re.sub(pattern, repl, expr)


# ============================================================
#            PERCENTAGE CONVERSION: 'X% of Y' → '((X/100)*Y)'
# ============================================================

def convert_percentages_in_expr(expr):
    """
    Converts 'X% of Y' or 'X% Y' to '((X/100)*Y)' form for numeric X and Y.
    This function performs a single pass of conversion, matching the leftmost occurrence.
    It expects X and Y to be numeric literals (possibly negative/decimal).
    """
    # Pattern to match:
    # Group 1: A number (integer or float, possibly negative). This is 'X'.
    # `%`
    # Optional `of` with spaces
    # Group 2: Another number (integer or float, possibly negative). This is 'Y'.
    # Word boundaries (\b) are crucial to ensure it matches whole numbers.
    pattern = r"(\b-?\d+(?:\.\d+)?)\s*%\s*(?:of\s*)?\s*(\b-?\d+(?:\.\d+)?\b)"

    # Use re.sub with a replacer function to perform the conversion
    def repl(match):
        percent_val = match.group(1)
        base_val = match.group(2)
        # Use parentheses around `percent_val` and `base_val` in the generated expression
        # to correctly handle negative numbers or complex terms if they were already simplified.
        return f"((({percent_val})/100)*({base_val}))"

    new_expr = re.sub(pattern, repl, expr, count=1)  # Only replace the first match
    return new_expr, (new_expr != expr)


# ============================================================
#            GLOBAL STEP COUNTER (FOR PRINTING)
# ============================================================

GLOBAL_STEP = 0


def print_step(bracket_name, updated):
    """Prints a formatted step in the bracket resolution process."""
    global GLOBAL_STEP
    GLOBAL_STEP += 1
    print(f"  ({GLOBAL_STEP}) Resolved {bracket_name}: {updated}")


# ============================================================
#        SPLIT ON '=' ONLY AT TOP LEVEL (NOT IN BRACKETS)
# ============================================================

def split_top_level_equation(expr):
    """Splits an equation at the main '=' sign, ignoring '=' inside brackets."""
    level = 0
    for i, ch in enumerate(expr):
        if ch in "([{":
            level += 1
        elif ch in ")]}":
            level -= 1
        elif ch == "=" and level == 0:
            # Found top-level '=', return left and right parts
            return expr[:i], expr[i + 1 :]
    # No top-level '=' found
    return None


# ============================================================
#       FIND & SOLVE INNER BRACKETS FIRST (ANY TYPE)
# ============================================================

def find_and_solve_innermost(expr, open_c, close_c, name):
    """
    Finds the first innermost bracket pair of a specific type (e.g., '()')
    and solves the expression inside it.
    """
    open_re = re.escape(open_c)
    close_re = re.escape(close_c)

    # Pattern: open_char, followed by any characters NOT open or close, then close_char
    # This finds the innermost pair.
    pattern = rf"{open_re}([^ {open_re}{close_re}]+){close_re}"
    m = re.search(pattern, expr)
    if not m:
        return expr, False  # No brackets of this type found

    inner = m.group(1)  # The content inside the brackets
    full = m.group(0)  # The full bracket expression, e.g., "(2+2)"

    # Recursively solve the inner part, indicating this is a recursive call
    solved = solve_expression(inner, print_steps=False, _is_recursive_call=True)
    if isinstance(solved, str) and solved.startswith("ERROR"):
        return solved, True  # Propagate errors

    # Replace the bracketed expression with its solved value
    new_expr = expr.replace(full, str(solved), 1)

    # Print the step if enabled
    if GLOBAL_STEP >= 0:
        print_step(name, new_expr)

    return new_expr, True


# ============================================================
#             PARSE LINEAR EXPRESSIONS (ax + b)
# ============================================================

def parse_linear(expr):
    """
    Parses a linear expression string (e.g., '2x - 5 + x')
    and returns the total 'a' (coefficient of x) and 'b' (constant) as Fractions.
    
    NOTE: This function *always* uses Fractions internally for precision
    during the solving steps. The final result is formatted based on RETURN_FRACTION.
    """
    expr = expr.replace(" ", "")
    # Add '1' to standalone 'x' for easier parsing (e.g., 'x' → '1x')
    expr = re.sub(r"(?<![\d.])x", "1x", expr)
    # Standardize subtraction to "add negative"
    expr = expr.replace("-", "+-")

    parts = expr.split("+")
    a = Fraction(0)
    b = Fraction(0)

    for p in parts:
        if p == "":
            continue

        if "x" in p:
            # This part has an 'x'
            coef = p.replace("x", "")
            if coef == "" or coef == "+":
                coef = "1"
            elif coef == "-":
                coef = "-1"
            # Convert coefficient to Fraction for precise math
            a += Fraction(coef)
        else:
            # This part is a constant
            # Convert constant to Fraction for precise math
            b += Fraction(p)

    return a, b


# ============================================================
#                  SOLVE LINEAR EQUATION
# ============================================================

def solve_equation(left, right):
    """
    Solves a linear equation in the form 'ax + b = cx + d'.
    'left' and 'right' are the simplified string expressions from each side.
    """
    # Parse both sides to get their 'a' and 'b' components (as Fractions)
    a1, b1 = parse_linear(left)
    a2, b2 = parse_linear(right)

    # Combine terms: (a1 - a2)x = (b2 - b1)
    A = a1 - a2  # Final 'a' (as Fraction)
    B = b2 - b1  # Final 'b' (as Fraction)

    if A == 0:
        if B == 0:
            return "All real numbers satisfy the equation"
        return "No solution"

    # Solve for x: x = B / A
    x = B / A  # x is now a Fraction object

    # --- THIS IS THE FIX ---
    # Now, format the final Fraction 'x' based on the global mode
    if RETURN_FRACTION:
        x = x.limit_denominator()
    else:
        # Convert the final Fraction object to a float for float mode
        x = float(x)
    # --- END OF FIX ---

    return f"x = {x}"


# ============================================================
#                   MAIN EXPRESSION SOLVER
# ============================================================

def solve_expression(expr_str, print_steps=True, _is_recursive_call=False):
    """
    Main function to solve a mathematical expression or equation.
    Automatically applies global variable substitutions before evaluation for non-recursive calls.
    """
    global GLOBAL_STEP
    global _CURRENT_VARIABLE_ASSIGNMENTS

    # --- THIS IS THE FIX ---
    # Sanitize all incoming strings to use ASCII equivalents first
    expr_str = sanitize_input(expr_str)
    # --- END OF FIX ---

    expr = convert_mixed_numbers(expr_str).replace(" ", "")

    # Apply variable assignments only for the initial, top-level call to solve_expression
    # or if explicitly flagged as needing substitution (e.g., when evaluating assignment values).
    if not _is_recursive_call and _CURRENT_VARIABLE_ASSIGNMENTS:
        original_expr = expr
        substituted_expr = expr

        # Sort variable assignments by length of variable name (descending)
        # to ensure longer variable names are substituted before shorter ones that might be substrings
        sorted_assignments = sorted(
            _CURRENT_VARIABLE_ASSIGNMENTS.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )

        for var_name, var_value in sorted_assignments:
            # Convert the stored value (which might be a Fraction) to string
            # In float mode, this might be a float, in fraction mode, a Fraction string
            # We will rely on the str() representation for substitution.
            val_str = str(var_value)
            
            # Handle cases like '2x', '3.5y', etc. (numeric coefficient + variable)
            # Use word boundaries \b to ensure full variable name matching
            substituted_expr = re.sub(
                rf"(?P<coef>\b\d+(?:\.\d+)?){re.escape(var_name)}\b",
                rf"\g<coef>*({val_str})",
                substituted_expr,
            )
            # Handle standalone variable names with word boundaries
            substituted_expr = re.sub(
                rf"\b{re.escape(var_name)}\b", rf"({val_str})", substituted_expr
            )

        if substituted_expr != original_expr:
            if print_steps:  # Only print this step if print_steps is enabled for the top-level call
                print(f"  (Auto) Substituted variables: {original_expr} -> {substituted_expr}")
        expr = substituted_expr

    # Disable step-by-step printing if there are no brackets or percentage operators
    if print_steps and all(ch not in expr for ch in "()[]{}") and not re.search(r"\d+%", expr):
        print_steps = False

    if print_steps:
        GLOBAL_STEP = 0
    else:
        GLOBAL_STEP = -1

    # First, check if it's an equation (after substitution)
    eq = split_top_level_equation(expr)
    if eq is not None:
        L, R = eq
        # Solve left and right sides independently first, indicating recursive calls
        # We pass print_steps=False to silence the step-by-step output for these
        # intermediate recursive calls.
        LS = solve_expression(L, print_steps=False, _is_recursive_call=True)
        RS = solve_expression(R, print_steps=False, _is_recursive_call=True)

        # Check for errors from recursive calls
        if isinstance(LS, str) and LS.startswith("ERROR"):
            return LS
        if isinstance(RS, str) and RS.startswith("ERROR"):
            return RS

        # Then, use the simplified linear expressions to solve for 'x'
        # Note: LS and RS will be string representations (e.g., "5.0+2x" or "10/3")
        return solve_equation(str(LS), str(RS))

    # --- No equation, so solve as a single expression ---
    if print_steps:
        print("\n--- Start Iterative Bracket/Percentage Resolution ---")

    precedence = [
        ("{", "}", "Curly Braces {}"),
        ("[", "]", "Square Brackets []"),
        ("(", ")", "Parentheses ()"),
    ]

    changed = True
    while changed:
        changed = False
        # Try resolving brackets first, in order of precedence
        for o, c, n in precedence:
            expr, updated = find_and_solve_innermost(expr, o, c, n)
            if isinstance(expr, str) and expr.startswith("ERROR"):
                return expr  # Propagate error
            if updated:
                changed = True
                break  # Break from inner for loop, re-enter while loop

        # If no brackets were resolved in this pass, try to resolve percentages
        if not changed:
            old_expr = expr
            expr, updated_percentage = convert_percentages_in_expr(expr)
            if updated_percentage:
                if GLOBAL_STEP >= 0:
                    print_step("Percentage Conversion", expr)
                changed = True
                # Continue the while loop

    if print_steps:
        print("--- Finished Bracket/Percentage Resolution ---")
        print("\n--- Final Calculation ---")

    # If 'x' remains after all brackets and substitutions are done,
    # it's a symbolic expression (e.g., from 'a=2; a+x' -> '2+x')
    if "x" in expr:
        # We can try to "parse" it to clean it up (e.g., '2+x+5' -> '7+1x')
        # but for now, just return the simplified string expression.
        # Let's try to parse and rebuild it for a cleaner look.
        try:
            a, b = parse_linear(expr) # This will use Fractions
            
            # Format 'a' and 'b' based on the output mode
            if RETURN_FRACTION:
                a = a.limit_denominator()
                b = b.limit_denominator()
            else:
                a = float(a)
                b = float(b)

            # Rebuild the string
            ax = ""
            if a == 1:
                ax = "x"
            elif a == -1:
                ax = "-x"
            elif a != 0:
                ax = f"{a}x"
            
            bs = ""
            if b > 0:
                bs = f"+{b}"
            elif b < 0:
                bs = f"{b}" # Sign is already included
            
            if ax and bs:
                return f"{ax}{bs}"
            elif ax:
                return ax
            elif b != 0:
                return str(b)
            elif b == 0:
                return "0"
            else: # Failsafe
                return expr

        except Exception:
             return expr # Return the raw string if parsing fails


    # No 'x', so it's a purely numeric expression
    numeric = calculate_standard_expression(expr)
    if numeric is None:
        # Failsafe: if the expression was just a sanitized bracket, e.g. "{"
        # which becomes "(", the numeric calc will fail.
        # Give a clearer error message than just "(", which might have been "{"
        if expr_str.strip() != expr.strip() and not re.search(r'\d', expr):
             return f"ERROR: Invalid expression after sanitizing '{expr_str}'"
        
        return f"ERROR: Invalid numeric expression '{expr}'"

    return numeric


# ============================================================
#               WEB APP INTERFACE FUNCTION
# ============================================================

def run_calculator(mode, expression_lines):
    """
    Takes a single mode ('fraction' or 'float') and a list of expression strings.
    Returns the captured print output for all expressions.
    """
    global RETURN_FRACTION
    global _CURRENT_VARIABLE_ASSIGNMENTS

    # Redirect stdout to capture all print() statements
    old_stdout = sys.stdout
    redirected_output = io.StringIO()
    sys.stdout = redirected_output

    try:
        # --- Set the output mode ONCE based on the argument ---
        if mode in ["float", "f"]:
            RETURN_FRACTION = False
            print("Output mode set to FLOAT.")
        else:
            RETURN_FRACTION = True
            print("Output mode set to FRACTION.")
        
        print("\n" + "=" * 40 + "\n")

        # --- Loop through each expression provided ---
        for raw in expression_lines:
            if not raw.strip():
                print("Skipped empty line.")
                print("\n" + "-" * 40 + "\n")
                continue

            # Reset global assignments for each new expression line
            _CURRENT_VARIABLE_ASSIGNMENTS = {}
            expression_to_solve = ""

            try:
                # --- Sanitize the *raw* input line *before* splitting by semicolon ---
                # This ensures "a=5；b=3" (with a full-width semicolon) also works.
                # We add '；' (U+FF1B) to the sanitizer for this.
                
                raw = sanitize_input(raw).replace("\uFF1B", ";") # Full-width semicolon
                
                # Split by semicolon, clean whitespace
                parts = [p.strip() for p in raw.split(";") if p.strip()]
                is_equation_for_x = False

                for i, part in enumerate(parts):
                    # Check if it's an assignment (e.g., 'a = 5')
                    match = re.match(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=(.*)", part)
                    if match:
                        var_name = match.group(1)
                        value_expr_str = match.group(2).strip()

                        # Substitute any *already defined* variables into this assignment
                        temp_value_expr_str = value_expr_str
                        sorted_current_assignments = sorted(
                            _CURRENT_VARIABLE_ASSIGNMENTS.items(), key=lambda item: len(item[0]), reverse=True
                        )
                        for existing_var, existing_val in sorted_current_assignments:
                            existing_val_str = str(existing_val)
                            # Handle '2var'
                            temp_value_expr_str = re.sub(
                                rf"(?P<coef>\b\d+(?:\.\d+)?){re.escape(existing_var)}\b",
                                rf"\g<coef>*({existing_val_str})",
                                temp_value_expr_str,
                            )
                            # Handle 'var'
                            temp_value_expr_str = re.sub(
                                rf"\b{re.escape(existing_var)}\b", rf"({existing_val_str})", temp_value_expr_str
                            )

                        # Solve the expression for the assignment
                        # Pass _is_recursive_call=True to prevent double-substitution
                        # solve_expression will sanitize the temp_value_expr_str automatically
                        solved_value = solve_expression(temp_value_expr_str, print_steps=False, _is_recursive_call=True)

                        if isinstance(solved_value, str) and solved_value.startswith("ERROR"):
                            print(f"\nERROR in assignment for {var_name}: {solved_value}")
                            raise ValueError(f"Invalid assignment for {var_name}")
                        elif isinstance(solved_value, str) and "x" in solved_value and var_name == "x":
                            # This is an equation for x, e.g., 'x = 2x + 5'
                            expression_to_solve = part
                            is_equation_for_x = True
                            break # This is the final expression
                        elif isinstance(solved_value, str) and "x" in solved_value:
                            # Error: assigning an 'x' expression to another variable
                            print(
                                f"\nERROR: Variable '{var_name}' assignment '{value_expr_str}' resolved to '{solved_value}', which still contains 'x'. Only 'x' can be implicitly defined via equation."
                            )
                            raise ValueError(f"Invalid assignment for {var_name}")
                        elif solved_value is None:
                            print(
                                f"\nERROR: Invalid assignment for {var_name}: '{value_expr_str}' did not resolve to a numeric value."
                            )
                            raise ValueError(f"Invalid assignment for {var_name}")
                        else:
                            # Store the solved value (will be Fraction or float)
                            _CURRENT_VARIABLE_ASSIGNMENTS[var_name] = solved_value
                            print(f"\nAssigned: {var_name} = {solved_value}")
                    else:
                        # Not an assignment, so this is the final expression to solve
                        expression_to_solve = part.rstrip("?")
                        # If it's the last part or contains an '=', solve it
                        if i == len(parts) - 1 or "=" in part:
                            break
                        else:
                            # This part is intermediate noise, ignore it
                            expression_to_solve = ""

                # After the loop, check what to do
                if not is_equation_for_x and not expression_to_solve and parts:
                    # Only assignments were provided (e.g., 'a=5; b=3')
                    if _CURRENT_VARIABLE_ASSIGNMENTS:
                        print("\nNo explicit expression to evaluate. Final assignments:")
                        for var, val in _CURRENT_VARIABLE_ASSIGNMENTS.items():
                            print(f"  {var} = {val}")
                        # continue # This would skip the ----- separator, let's print it
                    else:
                        print(f"ERROR: Could not parse expression or assignments: '{raw}'")
                        # continue
                elif not parts:
                    # This case should be caught by the 'if not raw.strip()' at the start
                    continue
                else:
                    # We have an expression_to_solve
                    print(f"\nProcessing: {expression_to_solve}")
                    # This is a top-level call, so print_steps=True (it will auto-disable if simple)
                    # solve_expression will sanitize the expression_to_solve string
                    result = solve_expression(expression_to_solve, print_steps=True)
                    print("\n" + "=" * 40)
                    print("RESULT:", result)
                    print("=" * 40)

            except Exception as e:
                print(f"\nAN ERROR OCCURRED: {e}")
                print("=" * 40)
                # continue # Let the separator print

            # Add a separator for multiple batches of input
            print("\n" + "-" * 40 + "\n")

    finally:
        # Restore stdout
        sys.stdout = old_stdout

    # Return the captured output
    return redirected_output.getvalue()

# ============================================================
#                 COMMAND LINE INTERFACE
# ============================================================

if __name__ == "__main__":
    # This block is for running the script directly from the command line
    # It mimics the logic of the web app's run_calculator function
    
    print("Custom Precedence Calculator with Linear Equation Solver")
    print(
        "Supports (), [], {} brackets, mixed numbers (e.g., '1 1/2'), percentages (e.g., '10% of 200'), and multiple variables (a, b, x, etc.)."
    )
    print("Type 'quit' to exit.")

    while True:
        # --- Ask user for output style EACH time ---
        choice = input("\nOutput type? (fraction/float): ").strip().lower()

        # Use the same logic as run_calculator to set the global
        if choice in ["float", "f"]:
            mode = "float"
        else:
            mode = "fraction"

        # --- Get expression ---
        raw = input("Enter expression: ")

        if raw.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        if not raw.strip():
            continue  # Skip empty input

        # --- Use the run_calculator function to process the input ---
        # We pass the mode and the raw string as a single-item list
        # The run_calculator function handles all the logic and printing
        
        # We don't need to redirect stdout here, because run_calculator
        # will redirect it, capture the output, and then return it as a string.
        # We just need to print that string.
        
        # The `raw` string will be sanitized *inside* run_calculator/solve_expression
        output_string = run_calculator(mode, [raw])
        
        # Print the captured output from run_calculator
        print(output_string)