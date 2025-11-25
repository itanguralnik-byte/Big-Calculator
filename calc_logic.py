# calc_logic.py
import re
from fractions import Fraction
import io
import sys

# ============================================================
#                 INPUT SANITIZATION (FIXED)
# ============================================================

# --- START OF MODIFICATION ---
# Compile the regex for allowed characters for efficiency.
# We allow:
# a-z (lowercase letters)
# 0-9 (numbers)
# + - * / % (operators)
# ( ) [ ] { } (brackets)
# = (assignment)
# ; (separator)
# . (decimal point)
# _ (variable underscore)
# \s (whitespace)
# This regex matches any character NOT in this set.
DISALLOWED_CHARS_REGEX = re.compile(r"[^a-z0-9+\-*/%()[\]{}=;._\s]")
# --- END OF MODIFICATION ---


def sanitize_input(expr_str):
    """
    Replaces common Unicode math symbols, full-width characters,
    converts to lowercase, and strips any disallowed characters.
    """
    if not isinstance(expr_str, str):
        return expr_str  # Safety check

    # --- START OF MODIFICATION (Force Lowercase) ---
    # Convert entire expression to lowercase first.
    expr_str = expr_str.lower()
    # --- END OF MODIFICATION ---

    replacements = {
        # Math Operators
        "\u2212": "-",  # Minus Sign (−)
        "\u22C5": "*",  # Dot Operator (⋅)
        "\u00D7": "*",  # Multiplication Sign (×)
        "\u00F7": "/",  # Division Sign (÷)

        # --- START OF MODIFICATION (Add Exponents) ---
        "\u005E": "**", # Caret (^)
        "\u00B2": "**2", # Superscript Two (²)
        "\u00B3": "**3", # Superscript Three (³)
        "\u00B9": "**1", # Superscript One (¹)
        # --- END OF MODIFICATION ---

        # Full-width Math Operators
        "\uFF0B": "+",  # Full-width Plus
        "\uFF0D": "-",  # Full-width Hyphen-Minus
        "\uFF0A": "*",  # Full-width Asterisk
        "\uFF0F": "/",  # Full-width Solidus (slash)
        "\uFF1D": "=",  # Full-width Equals Sign
        "\uFF05": "%",  # Full-width Percent
        "\uFF0E": ".",  # Full-width Dot

        # Full-width Brackets
        "\uFF08": "(",  # Full-width (
        "\uFF09": ")",  # Full-width )
        "\uFF3B": "[",  # Full-width [
        "\uFF3D": "]",  # Full-width ]
        "\uFF5B": "{",  # Full-width {
        "\uFF5D": "}",  # Full-width }

        # Full-width Semicolon
        "\uFF1B": ";",  # Full-width Semicolon
        
        # Full-width Numbers (0-9)
        "\uFF10": "0", "\uFF11": "1", "\uFF12": "2", "\uFF13": "3", "\uFF14": "4",
        "\uFF15": "5", "\uFF16": "6", "\uFF17": "7", "\uFF18": "8", "\uFF19": "9",
        
        # Common Spaces
        "\u3000": " ",  # Ideographic Space
        "\u00A0": " "   # Non-breaking Space
    }

    for uni, asc in replacements.items():
        expr_str = expr_str.replace(uni, asc)
    
    # --- START OF MODIFICATION (Filter "Strange" Characters) ---
    # Remove any character that is not on our whitelist
    expr_str = DISALLOWED_CHARS_REGEX.sub("", expr_str)
    # --- END OF MODIFICATION ---
    
    # --- START OF FIX (Bug C: Percentages) ---
    # Add spaces around '%' to make parsing '10%of200' easier
    expr_str = expr_str.replace("%", " % ")
    # --- END OF FIX ---
    
    return expr_str

# ============================================================
#                 FRACTION OUTPUT SWITCH
# ============================================================

# This will be set by user input inside the main loop
RETURN_FRACTION = True

# Global variable to store assignments during the current execution flow
_CURRENT_VARIABLE_ASSIGNMENTS = {}  # Stores var_name -> Fraction value


# ============================================================
#           BASIC NUMERIC EVAL (MODIFIED FOR ERRORS)
# ============================================================

def calculate_standard_expression(expr, log_buffer=None):
    """
    Evaluates a simple numeric expression string.
    Returns a number (Fraction or float) on success.
    Returns an 'ERROR: ...' string on failure.
    """
    expr = expr.replace(" ", "")

    # --- [DEBUG] ADDED PRINT ---
    if log_buffer:
        log_buffer.append(f"[DEBUG] calculate_standard_expression attempting: '{expr}'")

    # --- START OF FIX ---
    # This regex checks for any character that is NOT an allowed one.
    # NOTE: Since we convert '^' to '**' earlier, and '*' is allowed,
    # this check does not need to be modified for exponents.

    # --- START OF MODIFICATION (Allow Parentheses for eval) ---
    # We MUST allow ( and ) for eval() to handle negative bases, e.g., (-2)**4
    if re.search(r"[^0-9+\-*/.()]", expr):
    # --- END OF MODIFICATION ---
    
        # We re-run normalize just in case it's a recursive call
        # that didn't get it, e.g., from parse_linear
        expr = normalize_unary_minus(expr, log_buffer=log_buffer)
        
        # Check again after normalization
        # --- START OF MODIFICATION (Allow Parentheses for eval) ---
        if re.search(r"[^0-9+\-*/.()]", expr):
        # --- END OF MODIFICATION ---
             if log_buffer:
                 log_buffer.append(f"[DEBUG] calculate_standard_expression REJECTED: '{expr}'")
             # --- START OF MODIFICATION (User-friendly Error) ---
             return f"ERROR: Invalid characters in numeric expression '{expr}'"
             # --- END OF MODIFICATION ---
    # --- END OF FIX ---

    try:
        # Use eval for simple math
        # eval() already understands Python's '**' operator
        value = eval(expr)

        if RETURN_FRACTION:
            # Convert to fraction and limit denominator for cleaner output
            return Fraction(value).limit_denominator()

        # In float mode, just return the evaluated value
        return value

    # --- START OF MODIFICATION (User-friendly Errors) ---
    except ZeroDivisionError:
        if log_buffer:
            log_buffer.append(f"[DEBUG] calculate_standard_expression FAILED: Division by zero")
        return "ERROR: Cannot divide by zero"

    except SyntaxError as e:
        msg = str(e).lower()
        # Check for messages typical of missing/mismatched brackets
        if "unexpected eof" in msg or "unmatched" in msg or "expected" in msg:
            if log_buffer:
                log_buffer.append(f"[DEBUG] calculate_standard_expression FAILED: Mismatched bracket")
            return "ERROR: Mismatched or missing brackets"
        else:
            # Other syntax errors like '5 * / 2'
            if log_buffer:
                log_buffer.append(f"[DEBUG] calculate_standard_expression FAILED: Syntax error {e}")
            return f"ERROR: Invalid syntax in expression (e.g., '5 * / 2')"

    except Exception as e:
        # Catch other errors like "ValueError: math domain error"
        if log_buffer:
            log_buffer.append(f"[DEBUG] calculate_standard_expression FAILED eval: {e}")
        return f"ERROR: An unexpected error occurred during calculation: {e}"
    # --- END OF MODIFICATION ---


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

def convert_percentages_in_expr(expr, log_buffer=None):
    """
    Converts 'X% of Y' or 'X% Y' to '((X/100)*Y)' form for numeric X and Y.
    This function performs a single pass of conversion, matching the leftmost occurrence.
    It expects X and Y to be numeric literals (possibly negative/decimal).
    """
    # --- START OF FIX (Bug D: Percentages) ---
    # We use 'of' here because sanitize_input has already lowercased everything.
    pattern = r"((?<![\d.])-?\d+(?:\.\d+)?)\s*%\s*(?:of\s*)?(-?\d+(?:\.\d+)?)"
    # --- END OF FIX ---


    # Use re.sub with a replacer function to perform the conversion
    def repl(match):
        percent_val = match.group(1)
        base_val = match.group(2)
        # Use parentheses around `percent_val` and `base_val` in the generated expression
        # to correctly handle negative numbers or complex terms if they were already simplified.
        return f"((({percent_val})/100)*({base_val}))"

    new_expr = re.sub(pattern, repl, expr, count=1)  # Only replace the first match
    
    if new_expr != expr:
        if GLOBAL_STEP >= 0:
            print_step("Percentage Conversion", new_expr, log_buffer=log_buffer)
        return new_expr, True
        
    return new_expr, False


# ============================================================
#            NORMALIZE UNARY MINUS & CLEANUP (FIXED)
# ============================================================

def normalize_unary_minus(expr: str, log_buffer=None) -> str:
    """
    Normalize unary minus occurrences so the parser can handle them uniformly.
    This function:
    - Adds a leading 0 if the expression starts with '-' (e.g., '-5' -> '0-5').
    - Converts '(-5' -> '(0-5)'
    - Removes stray spaces
    - eval() is smart enough to handle '5*-2', '5--2', '5+-2', etc.
      so we do *not* need to add 0s after other operators.
    """
    if not isinstance(expr, str):
        return expr
        
    original_expr = expr # For debug

    # Remove redundant spaces around operators for consistent regex handling
    expr = re.sub(r"\s+", "", expr)

    # If expression starts with a unary minus, prefix with 0
    expr = re.sub(r"^\-", "0-", expr)
    
    # If a bracket is immediately followed by a minus, insert a 0 to make it binary:
    # '(-5' -> '(0-5)'; same for '[' and '{'
    expr = re.sub(r"([\(\[\{])\-", r"\g<1>0-", expr)
    
    # --- ALGAB PARANDUS ---
    # See vana loogika põhjustas vea -2**4 arvutamisel.
    # eval() saab ise hakkama '5--2' ja '5+-2' operaatoritega.
    # Probleem '5*--2' (SyntaxError) lahendatakse sulgude lisamisega
    # funktsioonis find_and_solve_innermost.
    # Selle tsükli eemaldamine parandab vea, kus '-(-2)**4' muudeti
    # valesti '+2**4'-ks.
    
    # previous = None
    # while previous != expr:
    #     previous = expr
    #     expr = expr.replace("--", "+") # <--- VIGANE LOOGIKA
    #     expr = expr.replace("+-", "-")
    #     expr = expr.replace("++", "+")
    #     expr = expr.replace("-+", "-")
    # --- LÕPEB PARANDUS ---
    
    # --- [DEBUG] ADDED PRINT ---
    if log_buffer and original_expr != expr:
        log_buffer.append(f"[DEBUG] normalize_unary_minus: '{original_expr}' -> '{expr}'")
    return expr


# ============================================================
#            GLOBAL STEP COUNTER (FOR PRINTING)
# ============================================================

GLOBAL_STEP = 0


def print_step(bracket_name, updated, log_buffer=None):
    """Prints a formatted step in the bracket resolution process."""
    global GLOBAL_STEP
    GLOBAL_STEP += 1
    if log_buffer:
        log_buffer.append(f"  ({GLOBAL_STEP}) Resolved {bracket_name}: {updated}")


# ============================================================
#        SPLIT ON '=' ONLY AT TOP LEVEL (NOT IN BRACKETS)
# ============================================================

def split_top_level_equation(expr):
    """Splits an equation at the main '=' sign, newglecting '=' inside brackets."""
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
#       FIND & SOLVE INNER BRACKETS FIRST (ANY TYPE) (FIXED)
# ============================================================

def find_and_solve_innermost(expr, open_c, close_c, name, log_buffer=None):
    """
    Finds the first innermost bracket pair of a specific type (e.g., '()')
    and solves the expression inside it.
    """
    # Build a pattern that finds the innermost pair by disallowing the open or close characters
    # inside the content. Use non-greedy qualifier to be safe.
    # Note: open_c and close_c are single characters like '(' and ')'.
    open_re = re.escape(open_c)
    close_re = re.escape(close_c)

    # --- START OF FIX (Bug A/B: Nested Brackets) ---
    pattern = rf"{open_re}([^{re.escape(open_c)}{re.escape(close_c)}]+?){close_re}"
    # --- END OF FIX ---
    
    m = re.search(pattern, expr)
    if not m:
        return expr, False  # No brackets of this type found

    inner = m.group(1)  # The content inside the brackets
    full = m.group(0)  # The full bracket expression, e.g., "(2+2)"

    # --- [DEBUG] ADDED PRINT ---
    if log_buffer:
        log_buffer.append(f"[DEBUG] find_and_solve_innermost: Found '{full}'. Solving inner: '{inner}'")

    # --- START OF BUG FIX (GLOBAL_STEP) ---
    # Save the global step value, because the recursive call
    # with print_steps=False will set it to -1.
    global GLOBAL_STEP
    current_step_mode = GLOBAL_STEP
    # --- END OF BUG FIX ---

    # Recursively solve the inner part, indicating this is a recursive call
    solved = solve_expression(inner, print_steps=False, _is_recursive_call=True, log_buffer=log_buffer)
    
    # --- START OF BUG FIX (GLOBAL_STEP) ---
    # Restore the global step value
    GLOBAL_STEP = current_step_mode
    # --- END OF BUG FIX ---
    
    if isinstance(solved, str) and solved.startswith("ERROR"):
        return solved, True  # Propagate errors

    # --- START OF MODIFICATION (Show Calculation Step) ---
    # We need the global counter to add our new step
    # global GLOBAL_STEP  <- Already declared above
    if GLOBAL_STEP >= 0: # Check if steps are enabled
        GLOBAL_STEP += 1
        if log_buffer:
            # Log the specific calculation: e.g., "Solve Parentheses (): 3+4 = 7"
            log_buffer.append(f"  ({GLOBAL_STEP}) Solve {name}: {inner} = {solved}")
    # --- END OF MODIFICATION ---

    # --- ALGAB PARANDUS ---
    # Muudame lahendatud väärtuse (mis on number) lihtsalt stringiks.
    # ME KEEPERIME SULGUD KUI VAJALIK: kui lahendatud väärtus on negatiivne
    # või kui see on baas eksponendile (järgnev '**'), siis pange see sulgudesse
    # et vältida tähenduse muutumist (näiteks '(-2)**4' -> '-2**4' oleks vale).
    solved_str = str(solved)

    # Decide whether to parenthesize the replacement:
    start_idx, end_idx = m.span()
    need_paren = False

    # If the solved string starts with a minus, parentheses are required to preserve base.
    if solved_str.startswith("-"):
        need_paren = True

    # If the character(s) after the closing bracket are '**' (exponent), parentheses needed.
    if end_idx < len(expr) and expr[end_idx:end_idx+2] == "**":
        need_paren = True

    # Also, if the solved string contains operators (e.g., '+', '-', '*', '/'),
    # it's safer to keep parentheses when embedding into the larger expression.
    if re.search(r"[+\-*/]", solved_str) and not solved_str.isdigit():
        need_paren = True

    if need_paren:
        replacement = f"({solved_str})"
    else:
        replacement = solved_str
    # --- LÕPEB PARANDUS ---

    # Replace only the first occurrence (the match we found)
    new_expr = expr[:start_idx] + replacement + expr[end_idx:]

    # --- START OF FIX (Infinite Loop) ---
    # Check if the expression actually changed.
    # If we replaced "(-2)" with "(-2)", this will be False.
    # If we replaced "(0-2)" with "(-2)", this will be True.
    did_change = (new_expr != expr)
    # --- END OF FIX ---

    # Print the step if enabled
    if GLOBAL_STEP >= 0 and did_change: # Only print if it changed
        # We call print_step WITHOUT incrementing GLOBAL_STEP here,
        # because the "Solve" step above already incremented it.
        # We just want to log the *resolution*
        if log_buffer:
            log_buffer.append(f"  ... Resolved {name}: {new_expr}")
        # ---
        # Original: print_step(name, new_expr, log_buffer=log_buffer)
        # ---

    # --- START OF FIX (Infinite Loop) ---
    return new_expr, did_change
    # --- END OF FIX ---


# ============================================================
#        PARSE LINEAR EXPRESSIONS (ax + b) (MODIFIED)
# ============================================================

def parse_linear(expr, log_buffer=None):
    """
    Parses a linear expression string (e.g., '2x - 5 + x')
    and returns the total 'a' (coefficient of x) and 'b' (constant) as Fractions.
    
    NOTE: This function *always* uses Fractions internally for precision
    during the solving steps. The final result is formatted based on RETURN_FRACTION.
    
    Raises:
        ValueError: If a constant part contains an invalid expression.
    """
    # --- [DEBUG] ADDED PRINT ---
    if log_buffer:
        log_buffer.append(f"[DEBUG] parse_linear called with: '{expr}'")
    
    # We must normalize *before* parsing
    expr = normalize_unary_minus(expr.replace(" ", ""), log_buffer=log_buffer)
    
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
            
            # --- START OF MODIFICATION (Handle Errors) ---
            # The constant part 'p' might be a simple number ('5')
            # or a complex numeric expression ('10*20') left over
            # from bracket resolution. We must evaluate it.
            evaluated_constant = calculate_standard_expression(p, log_buffer=log_buffer)
            
            # Check if calculate_standard_expression returned an error string
            if isinstance(evaluated_constant, str) and evaluated_constant.startswith("ERROR"):
                # Raise an exception with the user-friendly error message
                error_msg = evaluated_constant.replace("ERROR: ", "")
                if log_buffer:
                    log_buffer.append(f"[DEBUG] parse_linear: Invalid constant part: '{p}' -> {error_msg}")
                raise ValueError(f"In constant part '{p}': {error_msg}")
                
            # Add the result (which is a Fraction or float)
            b += evaluated_constant
            # --- END OF MODIFICATION ---
            
    if log_buffer:
        log_buffer.append(f"[DEBUG] parse_linear result: a={a}, b={b}")
    return a, b


# ============================================================
#                  SOLVE LINEAR EQUATION
# ============================================================

def solve_equation(left, right, log_buffer=None):
    """
    Solves a linear equation in the form 'ax + b = cx + d'.
    'left' and 'right' are the simplified string expressions from each side.
    
    Note: This function can raise ValueError if parse_linear fails.
    """
    # --- [DEBUG] ADDED PRINT ---
    if log_buffer:
        log_buffer.append(f"[DEBUG] solve_equation: L='{left}' R='{right}'")
    
    # Parse both sides to get their 'a' and 'b' components (as Fractions)
    # This will raise ValueError if parsing fails (e.g., 'x + (5/0)')
    a1, b1 = parse_linear(left, log_buffer=log_buffer)
    a2, b2 = parse_linear(right, log_buffer=log_buffer)

    # Combine terms: (a1 - a2)x = (b2 - b1)
    A = a1 - a2  # Final 'a' (as Fraction)
    B = b2 - b1  # Final 'b' (as Fraction)

    if A == 0:
        if B == 0:
            return "all real numbers satisfy the equation"
        return "no solution"

    # Solve for x: x = B / A
    x = B / A  # x is now a Fraction object

    # Now, format the final Fraction 'x' based on the global mode
    if RETURN_FRACTION:
        x = x.limit_denominator()
    else:
        # Convert the final Fraction object to a float for float mode
        x = float(x)

    return f"x = {x}"


# ============================================================
#               MAIN EXPRESSION SOLVER (MODIFIED)
# ============================================================

def solve_expression(expr_str, print_steps=True, _is_recursive_call=False, log_buffer=None):
    """
    Main function to solve a mathematical expression or equation.
    Automatically applies global variable substitutions before evaluation for non-recursive calls.
    """
    global GLOBAL_STEP
    global _CURRENT_VARIABLE_ASSIGNMENTS

    # --- [DEBUG] ADDED PRINT ---
    if log_buffer and print_steps:
        log_buffer.append(f"[DEBUG] solve_expression called with: '{expr_str}' (Recursive: {_is_recursive_call})")

    # --- Sanitize all incoming strings to use ASCII equivalents, force lowercase, and strip invalid chars
    expr_str = sanitize_input(expr_str)
    # --- END SANITIZE ---

    expr = convert_mixed_numbers(expr_str).replace(" ", "")

    # --- ALGAB PARANDUS ---
    # Väldime lõputut tsüklit. Kui see on rekursiivne kutse
    # ja sisend on juba lahendatud arv sulgudes (nt '(-2)'),
    # siis me ei normaliseeri seda uuesti (mis muudaks selle '(0-2)'-ks).
    # KUID: me peame siiski normaliseerima, kui see on '(2+2)' vms.
    # Vana kontroll 're.fullmatch(r"\([\-0-9\./]+\)", expr)' oli liiga lihtne.
    # Loobume sellest spetsiifilisest kontrollist, kuna 'find_and_solve_innermost'
    # parandus lahendab lõputu tsükli probleemi juurprobleemi.
    
    # if _is_recursive_call and re.fullmatch(r"\([\-0-9\./]+\)", expr):
    #     pass # Jäta normaliseerimine vahele
    # else:
    expr = normalize_unary_minus(expr, log_buffer=log_buffer if print_steps else None)
    # --- LÕPEB PARANDUS ---


    # Apply variable assignments only for the initial, top-level call to solve_expression
    # or if explicitly flagged as needing substitution (e.g., when evaluating assignment values).
    if not _is_recursive_call and _CURRENT_VARIABLE_ASSIGNMENTS:
        original_expr = expr
        substituted_expr = expr

        # Sort variable assignments by length of variable name (descending)
        sorted_assignments = sorted(
            _CURRENT_VARIABLE_ASSIGNMENTS.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )

        # ==================================================================
        #                 --- START OF LOGIC FIX ---
        # ==================================================================
        for var_name, var_value in sorted_assignments:
            val_str = str(var_value)
            # Always parenthesize substitution for safety
            val_str_paren = f"({val_str})"
            var_name_re = re.escape(var_name)
            
            # --- START OF MODIFICATION (Lowercase) ---
            word_chars = r"a-z0-9_" 
            # --- END OF MODIFICATION ---

            # --- FIX 2: Corrected Coefficient Regex ---
            coef_regex = rf"\b(?P<coef>(\d+(\.\d*)?|\.\d+)){var_name_re}\b"
            substituted_expr = re.sub(
                coef_regex,
                rf"\g<coef>*({val_str})", # No extra parens on coef
                substituted_expr,
            )

            # --- FIX 1 (Bug C): Implicit Multiplication (Case A: Preceding) ---
            # SYNTAXERROR FIX: Escaped literal braces with {{ and }}
            pre_regex = rf"(?P<pre>[{word_chars}\)\]\}}]}}])(\s*)\b{var_name_re}\b"
            substituted_expr = re.sub(
                pre_regex,
                rf"\g<pre>*{val_str_paren}",
                substituted_expr
            )

            # --- FIX 1 (Bug C): Implicit Multiplication (Case B: Following) ---
            # SYNTAXERROR FIX: Escaped literal braces with {{ and }}
            post_regex = rf"\b{var_name_re}\b(\s*)(?P<post>[{word_chars}\(\[\{{{{])"
            substituted_expr = re.sub(
                post_regex,
                rf"{val_str_paren}*\g<post>",
                substituted_expr
            )

            # --- Standard Standalone Replacement ---
            # This MUST run last
            standalone_regex = rf"\b{var_name_re}\b"
            substituted_expr = re.sub(
                standalone_regex,
                val_str_paren,
                substituted_expr
            )
        # ==================================================================
        #                   --- END OF LOGIC FIX ---
        # ==================================================================

        if substituted_expr != original_expr:
            if print_steps and log_buffer:
                log_buffer.append(f"  (Auto) Substituted variables: {original_expr} -> {substituted_expr}")
        expr = substituted_expr

    # After substitution, normalize unary minus again in case substitutions produced new patterns
    expr = normalize_unary_minus(expr, log_buffer=log_buffer if print_steps else None)


    # Disable step-by-step printing if not requested
    if not print_steps:
        GLOBAL_STEP = -1
    # Enable step-by-step printing, but only if complex ops exist
    elif print_steps and all(ch not in expr for ch in "()[]{}") and not re.search(r"%\s*(?:of\b\s*)?", expr):
        GLOBAL_STEP = -1 # No complex ops, no steps needed
    # Enable step-by-step printing
    else:
        # --- START OF MODIFICATION (Fix) ---
        # Only set GLOBAL_STEP to 0 if it's not a recursive call.
        # If it is recursive, we leave GLOBAL_STEP alone.
        if not _is_recursive_call:
            GLOBAL_STEP = 0
        # --- END OF MODIFICATION ---


    # First, check if it's an equation (after substitution)
    eq = split_top_level_equation(expr)
    if eq is not None:
        L, R = eq
        try:
            # Solve left and right sides independently first, indicating recursive calls
            # Pass log_buffer only if steps are requested
            log_buffer_recursive = log_buffer if print_steps else None
            
            LS = solve_expression(L, print_steps=False, _is_recursive_call=True, log_buffer=log_buffer_recursive)
            if isinstance(LS, str) and LS.startswith("ERROR"):
                return LS # Propagate error
            
            RS = solve_expression(R, print_steps=False, _is_recursive_call=True, log_buffer=log_buffer_recursive)
            if isinstance(RS, str) and RS.startswith("ERROR"):
                return RS # Propagate error

            # Then, use the simplified linear expressions to solve for 'x'
            # This can raise a ValueError if parse_linear fails (e.g., 'x = 1/0')
            return solve_equation(str(LS), str(RS), log_buffer=log_buffer_recursive)
            
        except ValueError as e:
            # Catch errors from parse_linear (via solve_equation)
            if log_buffer:
                log_buffer.append(f"[DEBUG] solve_equation failed: {e}")
            return f"ERROR: {e}"
        except Exception as e:
            # Catch any other unexpected errors during equation solving
            if log_buffer:
                log_buffer.append(f"[DEBUG] solve_expression (equation) failed: {e}")
            return f"ERROR: An unexpected error occurred while solving equation: {e}"

    # --- No equation, so solve as a single expression ---
    if GLOBAL_STEP == 0 and log_buffer: # Only print header if steps are enabled
        log_buffer.append("\n--- Start Iterative Bracket/Percentage Resolution ---")

    # --- START OF MODIFICATION (Reversed Precedence) ---
    # We must solve from the inside out: () -> [] -> {}
    precedence = [
        ("(", ")", "Parentheses ()"),
        ("[", "]", "Square Brackets []"),
        ("{", "}", "Curly Braces {}"),
    ]
    # --- END OF MODIFICATION ---

    changed = True
    while changed:
        changed = False
        # Try resolving brackets first, in order of precedence
        for o, c, n in precedence:
            # Pass log_buffer only if steps are enabled (GLOBAL_STEP >= 0)
            log_buffer_steps = log_buffer if GLOBAL_STEP >= 0 else None
            expr, updated = find_and_solve_innermost(expr, o, c, n, log_buffer=log_buffer_steps)
            
            if isinstance(expr, str) and expr.startswith("ERROR"):
                return expr  # Propagate error
            if updated:
                changed = True
                break  # Break from inner for loop, re-enter while loop

        # If no brackets were resolved in this pass, try to resolve percentages
        if not changed:
            old_expr = expr
            # Pass log_buffer only if steps are enabled (GLOBAL_STEP >= 0)
            log_buffer_steps = log_buffer if GLOBAL_STEP >= 0 else None
            expr, updated_percentage = convert_percentages_in_expr(expr, log_buffer=log_buffer_steps)
            
            if updated_percentage:
                # print_step is already called inside convert_percentages_in_expr
                changed = True
                # Continue the while loop
        
        # After each change, re-normalize
        if changed:
            # --- START OF FIX (Infinite Loop) ---
            # This re-normalization caused an infinite loop where:
            # 1. (0-2) was solved to (-2) [changed=True]
            # 2. This line normalized (-2) back to (0-2)
            # 3. Loop repeated
            # We must remove this. Normalization now only happens
            # at the start of solve_expression and after variable substitution.
            # expr = normalize_unary_minus(expr, log_buffer=log_buffer)
            # --- END OF FIX ---
            pass # Keep the if block structure

    if GLOBAL_STEP == 0 and log_buffer: # Only print if steps were enabled
        log_buffer.append("--- Finished Bracket/Percentage Resolution ---")
        log_buffer.append("\n--- Final Calculation ---")

    # Pass log_buffer only if steps are enabled (GLOBAL_STEP >= 0)
    log_buffer_steps = log_buffer if GLOBAL_STEP >= 0 else None

    # If 'x' remains after all brackets and substitutions are done,
    if "x" in expr:
        # --- START OF MODIFICATION (Handle Errors) ---
        # Try to parse and rebuild it for a cleaner look.
        try:
            a, b = parse_linear(expr, log_buffer=log_buffer_steps) # This will use Fractions
            
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

        except ValueError as e:
             # This catches user-friendly errors from parse_linear
             if log_buffer:
                log_buffer.append(f"[DEBUG] parse_linear failed on final 'x' expression: {e}")
             return f"ERROR: {e}" # Return the friendly error
        except Exception as e:
             # Catch-all for other parsing errors
             if log_buffer:
                log_buffer.append(f"[DEBUG] Failed to parse final 'x' expression: {e}")
             return f"ERROR: Could not parse final expression '{expr}'"
        # --- END OF MODIFICATION ---


    # --- START OF MODIFICATION (Handle Errors) ---
    # No 'x', so it's a purely numeric expression
    # calculate_standard_expression now returns a number or an "ERROR:" string
    numeric = calculate_standard_expression(expr, log_buffer=log_buffer_steps)
    
    # If it's an error string, return it directly.
    # Otherwise, it's the valid numeric result.
    return numeric
    # --- END OF MODIFICATION ---


# ============================================================
#               WEB APP INTERFACE FUNCTION (MODIFIED)
# ============================================================

def run_calculator(mode, expression_lines, show_steps=False):
    """
    Takes a single mode ('fraction' or 'float'), a list of expression strings,
    and a boolean 'show_steps'.
    Returns the captured print output for all expressions.
    """
    global RETURN_FRACTION
    global _CURRENT_VARIABLE_ASSIGNMENTS

    # --- ALGAB PARANDUS ---
    # Eemaldame sys.stdout ümbersuunamise, et vältida deadlock'i veebiserveris.
    # Selle asemel kogume kõik väljundid listi.
    log_buffer = []
    # --- LÕPEB PARANDUS ---

    try:
        # --- Set the output mode ONCE based on the argument ---
        if mode in ["float", "f"]:
            RETURN_FRACTION = False
            log_buffer.append("Output mode set to FLOAT.") # Vana: print
        else:
            RETURN_FRACTION = True
            log_buffer.append("Output mode set to FRACTION.") # Vana: print
        
        log_buffer.append("\n" + "=" * 40 + "\n") # Vana: print

        # --- Loop through each expression provided ---
        for raw in expression_lines:
            if not raw.strip():
                log_buffer.append("Skipped empty line.") # Vana: print
                log_buffer.append("\n" + "-" * 40 + "\n") # Vana: print
                continue

            # Reset global assignments for each new expression line
            _CURRENT_VARIABLE_ASSIGNMENTS = {}
            expression_to_solve = ""

            try:
                # --- Sanitize the *raw* input line *before* splitting by semicolon ---
                raw = sanitize_input(raw)
                
                # Split by semicolon, clean whitespace
                parts = [p.strip() for p in raw.split(";") if p.strip()]
                is_equation_for_x = False

                for i, part in enumerate(parts):
                    # Check if it's an assignment (e.g., 'a = 5')
                    # --- START OF MODIFICATION (Lowercase) ---
                    match = re.match(r"^\s*([a-z_][a-z0-9_]*)\s*=(.*)", part)
                    # --- END OF MODIFICATION ---
                    if match:
                        var_name = match.group(1)
                        value_expr_str = match.group(2).strip()
                        
                        if not value_expr_str:
                             # --- START OF MODIFICATION (User-friendly Error) ---
                             err_msg = f"ERROR: No value provided for assignment of '{var_name}'"
                             log_buffer.append(f"\n{err_msg}") # Vana: print
                             raise ValueError(err_msg)
                             # --- END OF MODIFICATION ---

                        # Substitute any *already defined* variables into this assignment
                        temp_value_expr_str = value_expr_str
                        sorted_current_assignments = sorted(
                            _CURRENT_VARIABLE_ASSIGNMENTS.items(), key=lambda item: len(item[0]), reverse=True
                        )
                        for existing_var, existing_val in sorted_current_assignments:
                            existing_val_str = str(existing_val)
                            
                            # --- Use the same logic as the main solver for consistency ---
                            existing_var_re = re.escape(existing_var)
                            # --- START OF MODIFICATION (Lowercase) ---
                            word_chars = r"a-z0-9_" 
                            # --- END OF MODIFICATION ---
                            
                            # Coef
                            coef_regex = rf"\b(?P<coef>(\d+(\.\d*)?|\.\d+)){existing_var_re}\b"
                            temp_value_expr_str = re.sub(
                                coef_regex, rf"\g<coef>*({existing_val_str})", temp_value_expr_str
                            )
                            # Pre
                            # SYNTAXERROR FIX: Escaped literal braces with {{ and }}
                            pre_regex = rf"(?P<pre>[{word_chars}\)\]\}}]}}])(\s*)\b{existing_var_re}\b"
                            temp_value_expr_str = re.sub(
                                pre_regex, rf"\g<pre>*({existing_val_str})", temp_value_expr_str
                            )
                            # Post
                            # SYNTAXERROR FIX: Escaped literal braces with {{ and }}
                            post_regex = rf"\b{existing_var_re}\b(\s*)(?P<post>[{word_chars}\(\[\{{{{])"
                            temp_value_expr_str = re.sub(
                                post_regex, rf"({existing_val_str})*\g<post>", temp_value_expr_str
                            )
                            # Standalone
                            standalone_regex = rf"\b{existing_var_re}\b"
                            temp_value_expr_str = re.sub(
                                standalone_regex, rf"({existing_val_str})", temp_value_expr_str
                            )

                        # --- START OF MODIFICATION (User-friendly Error) ---
                        # Solve the expression for the assignment
                        # We add a try...except block here to catch errors from solve_expression
                        # (like ValueErrors from parse_linear)
                        try:
                            # Pass log_buffer only if steps are requested
                            log_buffer_steps = log_buffer if show_steps else None
                            solved_value = solve_expression(temp_value_expr_str, print_steps=False, _is_recursive_call=True, log_buffer=log_buffer_steps)
                        except Exception as e:
                            # Catch any unexpected exceptions during assignment solving
                            err_msg = f"ERROR: Invalid assignment for '{var_name}'. Could not solve '{temp_value_expr_str}': {e}"
                            log_buffer.append(f"\n{err_msg}") # Vana: print
                            raise ValueError(err_msg)
                        
                        if isinstance(solved_value, str) and solved_value.startswith("ERROR"):
                            err_msg = f"ERROR: Invalid assignment for '{var_name}'. {solved_value.replace('ERROR: ', '')}"
                            log_buffer.append(f"\n{err_msg}") # Vana: print
                            raise ValueError(err_msg)
                        # --- END OF MODIFICATION ---
                        
                        elif isinstance(solved_value, str) and "x" in solved_value and var_name == "x":
                            # This is an equation for x, e.g., 'x = 2x + 5'
                            expression_to_solve = part
                            is_equation_for_x = True
                            break # This is the final expression
                        elif isinstance(solved_value, str) and "x" in solved_value:
                            # --- START OF MODIFICATION (User-friendly Error) ---
                            err_msg = f"ERROR: Invalid assignment for '{var_name}'. Result '{solved_value}' still contains 'x'. Only 'x' can be defined by an equation."
                            log_buffer.append(f"\n{err_msg}") # Vana: print
                            raise ValueError(err_msg)
                            # --- END OF MODIFICATION ---
                        else:
                            # Store the solved value (will be Fraction or float)
                            _CURRENT_VARIABLE_ASSIGNMENTS[var_name] = solved_value
                            log_buffer.append(f"\nAssigned: {var_name} = {solved_value}") # Vana: print
                    else:
                        # Not an assignment, so this is the final expression to solve
                        expression_to_solve = part.rstrip("?")
                        # If it's the last part or contains an '=', solve it
                        if i == len(parts) - 1 or "=" in part:
                            break
                        else:
                            # This part is intermediate noise, newglect it
                            expression_to_solve = ""

                # After the loop, check what to do
                if not is_equation_for_x and not expression_to_solve and parts:
                    # Only assignments were provided (e.g., 'a=5; b=3')
                    if _CURRENT_VARIABLE_ASSIGNMENTS:
                        log_buffer.append("\nNo explicit expression to evaluate. Final assignments:") # Vana: print
                        for var, val in _CURRENT_VARIABLE_ASSIGNMENTS.items():
                            log_buffer.append(f"  {var} = {val}") # Vana: print
                    else:
                        log_buffer.append(f"ERROR: Could not parse expression or assignments: '{raw}'") # Vana: print
                
                elif not parts:
                    continue
                else:
                    # We have an expression_to_solve
                    log_buffer.append(f"\nProcessing: {expression_to_solve}") # Vana: print
                    
                    # --- START: Modified line ---
                    # Pass the show_steps boolean to the print_steps argument
                    # If show_steps is False, solve_expression won't add debug steps
                    result = solve_expression(expression_to_solve, print_steps=show_steps, log_buffer=log_buffer)
                    # --- END: Modified line ---
                    
                    log_buffer.append("\n" + "=" * 40) # Vana: print
                    log_buffer.append(f"RESULT: {result}") # Vana: print
                    log_buffer.append("=" * 40) # Vana: print

            except Exception as e:
                # This catches the ValueErrors we raised during assignment
                # or any other unexpected error.
                # The 'e' object now contains our user-friendly message.
                log_buffer.append(f"\nAN ERROR OCCURRED: {e}") # Vana: print
                log_buffer.append("=" * 40) # Vana: print

            # Add a separator for multiple batches of input
            log_buffer.append("\n" + "-" * 40 + "\n") # Vana: print

    finally:
        # --- ALGAB PARANDUS ---
        # Enam ei ole vaja stdout'i taastada.
        pass
        # --- LÕPEB PARANDUS ---

    # --- ALGAB PARANDUS ---
    # Tagastame kogutud logi ühe stringina
    return "\n".join(log_buffer)
    # --- LÕPEB PARANDUS ---


# ============================================================
#                 COMMAND LINE INTERFACE
# ============================================================

if __name__ == "__main__":
    # See plokk on skripti käivitamiseks otse käsurealt.
    # Siin on 'print' käskude kasutamine ohutu, kuna see ei
    # jookse veebiserveri kontekstis.
    
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
        
        # --- Ask for steps ---
        steps_choice = input("Show steps? (y/n): ").strip().lower()
        show_steps_cli = steps_choice in ['y', 'yes']

        # --- Get expression ---
        raw = input("Enter expression: ")

        if raw.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        if not raw.strip():
            continue  # Skip empty input

        # --- Use the run_calculator function to process the input ---
        # run_calculator tagastab nüüd kogu väljundi stringina
        # Pass the show_steps_cli boolean
        output_string = run_calculator(mode, [raw], show_steps=show_steps_cli)
        
        # Prindime selle stringi konsooli
        print(output_string)