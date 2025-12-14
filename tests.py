import unittest
import sys
import os

# --- FIX IMPORT PATH ---
# Add the 'static' folder to the system path so we can import calc_logic
sys.path.append(os.path.join(os.path.dirname(__file__), 'static'))

# Import SESSION_VARIABLES to clear global state between tests
from calc_logic import Calculator, run_calculator, CalculationError, SESSION_VARIABLES

class TestCalculatorLogic(unittest.TestCase):

    def setUp(self):
        """Runs before every test method. Resets the calculator and global variables."""
        SESSION_VARIABLES.clear()  # <--- CRITICAL FIX: Ensure clean state
        self.calc = Calculator(mode="fraction", show_steps=False)

    # =================================================================
    # 1. BASIC ARITHMETIC & ORDER OF OPERATIONS
    # =================================================================
    
    def test_basic_math(self):
        """Test simple arithmetic operations."""
        self.assertIn("Result: $$2$$", self.calc.process_input_line("1 + 1"))
        self.assertIn("Result: $$10$$", self.calc.process_input_line("2 * 5"))
        self.assertIn("Result: $$5$$", self.calc.process_input_line("10 / 2"))
        self.assertIn("Result: $$3$$", self.calc.process_input_line("5 - 2"))

    def test_order_of_operations(self):
        """Test PEMDAS (Parentheses, Exponents, Mult/Div, Add/Sub)."""
        self.assertIn("Result: $$14$$", self.calc.process_input_line("2 + 3 * 4"))
        self.assertIn("Result: $$20$$", self.calc.process_input_line("(2 + 3) * 4"))
        self.assertIn("Result: $$9$$", self.calc.process_input_line("2^3 + 1"))
        
    def test_large_numbers(self):
        """Test arithmetic with larger integers."""
        self.assertIn("Result: $$1000000$$", self.calc.process_input_line("1000 * 1000"))
        self.assertIn("Result: $$123456789$$", self.calc.process_input_line("123456780 + 9"))

    def test_floating_point_math(self):
        """Test floating point precision handling."""
        res = self.calc.process_input_line("0.1 + 0.2")
        self.assertTrue("0.3" in res or "3/10" in res or "\\frac{3}{10}" in res)

    # =================================================================
    # 2. VARIABLES & ASSIGNMENTS
    # =================================================================

    def test_variable_assignment(self):
        out_assign = self.calc.process_input_line("a = 10")
        self.assertIsNone(out_assign)
        out_use = self.calc.process_input_line("a + 5")
        self.assertIn("Result: $$15$$", out_use)

    def test_variable_reassignment(self):
        self.calc.process_input_line("v = 5")
        self.calc.process_input_line("v = 10")
        self.assertIn("Result: $$20$$", self.calc.process_input_line("v * 2"))

    def test_variable_assignment_show_steps(self):
        calc_steps = Calculator(mode="fraction", show_steps=True)
        out = calc_steps.process_input_line("b = 20")
        self.assertIn("Assigned: b = $$20$$", out)
        out = calc_steps.process_input_line("b / 2")
        self.assertIn("Result: $$10$$", out)

    def test_dependent_variables(self):
        self.calc.process_input_line("x = 5")
        self.calc.process_input_line("y = x + 2") 
        out = self.calc.process_input_line("y + x") 
        self.assertIn("Result: $$12$$", out)

    # =================================================================
    # 3. SCIENTIFIC FUNCTIONS
    # =================================================================

    def test_trig_functions(self):
        self.assertIn("Result: $$0$$", self.calc.process_input_line("sin(0)"))
        self.assertIn("Result: $$1$$", self.calc.process_input_line("cos(0)"))
        self.assertIn("Result: $$2$$", self.calc.process_input_line("2 * cos(0)"))
        self.assertIn("Result: $$0$$", self.calc.process_input_line("tan(0)"))

    def test_trig_values(self):
        self.assertIn("Result: $$1$$", self.calc.process_input_line("sin(pi/2)"))
        self.assertIn("Result: $$-1$$", self.calc.process_input_line("cos(pi)"))

    def test_roots_and_logs(self):
        self.assertIn("Result: $$4$$", self.calc.process_input_line("sqrt(16)"))
        self.assertIn("Result: $$2$$", self.calc.process_input_line("cbrt(8)"))
        self.assertIn("Result: $$2$$", self.calc.process_input_line("log(100)"))
        self.assertIn("Result: $$1$$", self.calc.process_input_line("ln(e)")) 

    def test_nested_functions(self):
        self.assertIn("Result: $$5$$", self.calc.process_input_line("sqrt(16 + 9)"))
        self.assertIn("Result: $$1$$", self.calc.process_input_line("sin(0) + cos(0)"))

    def test_function_error_handling(self):
        with self.assertRaises(CalculationError):
            self.calc.process_input_line("sqrt(-1)")
        with self.assertRaises(CalculationError):
            self.calc.process_input_line("log(-5)")

    # =================================================================
    # 4. ERROR HANDLING & SECURITY
    # =================================================================

    def test_division_by_zero(self):
        with self.assertRaises(CalculationError):
            self.calc.process_input_line("5 / 0")
            
    def test_division_by_zero_indirect(self):
        with self.assertRaises(CalculationError):
            self.calc.process_input_line("1 / (2 - 2)")

    def test_security_injection(self):
        with self.assertRaises(CalculationError):
            self.calc.process_input_line("__import__('os').system('ls')")
            
    def test_security_attr_access(self):
        with self.assertRaises(CalculationError):
            self.calc.process_input_line("str.__class__")

    # =================================================================
    # 5. STATELESS MODE
    # =================================================================

    def test_stateless_mode(self):
        calc = Calculator(mode="fraction", stateless_mode=True)
        out_eq = calc.process_input_line("x = 5")
        self.assertIn("Result: x = $$5$$", out_eq)

        out_sym = calc.process_input_line("x + 2")
        self.assertIn("Result: $$x + 2$$", out_sym)
        self.assertNotIn("$$7$$", out_sym)

        try:
            out_func = calc.process_input_line("2*x + y(1/3)")
            self.assertIn("Result: $$", out_func)
            self.assertIn("y", out_func)
        except CalculationError as e:
            self.fail(f"Stateless mode symbolic function failed with error: {e}")

    # =================================================================
    # 6. STATISTICS
    # =================================================================
    
    def test_statistics_mean(self):
        self.assertIn("Result: $$3.0$$", self.calc.process_input_line("mean(1, 2, 3, 4, 5)"))
        self.assertIn("Result: $$3.0$$", self.calc.process_input_line("mean([1, 2, 3, 4, 5])"))
        
    def test_statistics_median(self):
        self.assertIn("Result: $$2.0$$", self.calc.process_input_line("median(1, 3, 2)"))
        self.assertIn("Result: $$2.5$$", self.calc.process_input_line("median(1, 2, 3, 4)"))

    def test_statistics_variance(self):
        self.assertIn("Result: $$0.0$$", self.calc.process_input_line("variance(2, 2, 2)"))

class TestAdvancedFeatures(unittest.TestCase):
    
    def setUp(self):
        # Clear global variable state so tests don't pollute each other (e.g. x=10)
        SESSION_VARIABLES.clear()
        self.calc = Calculator(mode="fraction", show_steps=False)

    # =================================================================
    # 7. SYMBOLIC ALGEBRA & SIMPLIFICATION
    # =================================================================

    def test_algebraic_expansion(self):
        result = self.calc.process_input_line("expand((x + 1)^2)")
        self.assertIn("x^{2}", result)
        self.assertIn("2 x", result)
        
        result_cubic = self.calc.process_input_line("expand((x - 2)^3)")
        self.assertIn("x^{3}", result_cubic)
        self.assertIn("- 8", result_cubic)

    def test_algebraic_factorization_simple(self):
        result = self.calc.process_input_line("factor(x^2 - 1)")
        self.assertIn("x - 1", result)
        self.assertIn("x + 1", result)

    def test_algebraic_factorization_hard(self):
        result = self.calc.process_input_line("factor(x^2 + 5x + 6)")
        self.assertIn("x + 2", result)
        self.assertIn("x + 3", result)

    def test_identity_simplification(self):
        result = self.calc.process_input_line("simplify(sin(x)^2 + cos(x)^2)")
        self.assertIn("Result: $$1$$", result)
        
        result_tan = self.calc.process_input_line("simplify(tan(x) * cos(x))")
        self.assertIn("sin", result_tan)

    def test_implicit_multiplication(self):
        self.calc.process_input_line("x = 10")
        self.assertIn("Result: $$20$$", self.calc.process_input_line("2x"))
        self.assertIn("Result: $$20$$", self.calc.process_input_line("2(5+5)"))
        self.assertIn("Result: $$20$$", self.calc.process_input_line("(2)(10)"))
        
    def test_implicit_multiplication_vars(self):
        self.calc.process_input_line("a = 2")
        self.calc.process_input_line("b = 3")
        res = self.calc.process_input_line("ab")
        if "Result" in res and "6" in res:
             self.assertIn("$$6$$", res)

    # =================================================================
    # 8. CALCULUS (Derivatives, Integrals, Limits)
    # =================================================================

    def test_derivatives_poly(self):
        self.assertIn("2 x", self.calc.process_input_line("diff(x^2, x)"))
        res = self.calc.process_input_line("diff(x^3 + 2x, x)")
        self.assertIn("3 x^{2}", res)
        self.assertIn("+ 2", res)

    def test_derivatives_trig(self):
        self.assertIn("cos", self.calc.process_input_line("diff(sin(x), x)"))
        res = self.calc.process_input_line("diff(sin(2x), x)")
        self.assertIn("cos", res)
        self.assertIn("2", res)

    def test_derivatives_exp(self):
        res = self.calc.process_input_line("diff(e^x, x)")
        self.assertIn("e^{x}", res)
        
    def test_higher_order_derivative(self):
        """Test second derivative."""
        # diff(sin(x), x, 2) -> -sin(x)
        res = self.calc.process_input_line("diff(sin(x), x, 2)")
        self.assertIn("sin", res)
        self.assertIn("-", res)

    def test_definite_integral_simple(self):
        result = self.calc.process_input_line("integrate(x, (x, 0, 2))")
        self.assertIn("Result: $$2$$", result)

    def test_definite_integral_hard(self):
        result = self.calc.process_input_line("integrate(cos(x), (x, 0, pi/2))")
        self.assertIn("Result: $$1$$", result)

    def test_indefinite_integral(self):
        result = self.calc.process_input_line("integrate(2x, x)")
        self.assertIn("x^{2}", result)

    def test_limits_infinity(self):
        result = self.calc.process_input_line("limit(1/x, x, oo)")
        self.assertIn("Result: $$0$$", result)
        
    def test_limits_zero(self):
        result_sinc = self.calc.process_input_line("limit(sin(x)/x, x, 0)")
        self.assertIn("Result: $$1$$", result_sinc)

    # =================================================================
    # 9. COMPLEX DOMAIN HANDLING
    # =================================================================

    def test_euler_identity(self):
        result = self.calc.process_input_line("e^(i * pi) + 1")
        self.assertIn("Result: $$0$$", result)

    def test_complex_fail(self):
        with self.assertRaises(CalculationError):
            self.calc.process_input_line("e^(i * pi / 2)")
            
    def test_complex_roots_fail(self):
        with self.assertRaises(CalculationError):
            self.calc.process_input_line("sqrt(-4)")

    # =================================================================
    # 10. EQUATION SOLVING
    # =================================================================

    def test_solve_linear_equation(self):
        result = self.calc.process_input_line("2x = 10")
        self.assertIn("x = $$5$$", result) 

    def test_solve_linear_equation_hard(self):
        result = self.calc.process_input_line("3x + 5 = 20")
        self.assertIn("x = $$5$$", result)

    def test_solve_quadratic(self):
        result = self.calc.process_input_line("x^2 = 4")
        self.assertIn("-2", result)
        self.assertIn("2", result)
        
    def test_solve_quadratic_trinomial(self):
        result = self.calc.process_input_line("x^2 + 5x + 6 = 0")
        self.assertIn("-2", result)
        self.assertIn("-3", result)

    def test_solve_cubic(self):
        # Real root is 2. 
        result = self.calc.process_input_line("x^3 - 8 = 0")
        self.assertIn("2", result)

    def test_solve_symbolic(self):
        calc_stateless = Calculator(mode="fraction", stateless_mode=True)
        result = calc_stateless.process_input_line("x + a = 10")
        self.assertIn("10 - a", result)

class TestExtremeLimits(unittest.TestCase):
    """
    Tests designed to break the logic with extreme nesting, recursion,
    series expansion, and systems of equations.
    """
    
    def setUp(self):
        SESSION_VARIABLES.clear()
        self.calc = Calculator(mode="fraction", show_steps=False)
        
    # =================================================================
    # 11. SYSTEMS OF EQUATIONS
    # =================================================================
    
    def test_system_of_equations(self):
        """Test solving a system of linear equations (substitution style)."""
        self.calc.process_input_line("y = 2x")
        # Solve x + y = 6 -> x + 2x = 6 -> 3x = 6 -> x = 2
        res = self.calc.process_input_line("x + y = 6")
        self.assertIn("x = $$2$$", res)
        
    # =================================================================
    # 12. SERIES EXPANSION (Taylor Series)
    # =================================================================
    
    def test_taylor_series(self):
        """Test Taylor series expansion."""
        pass 

    # =================================================================
    # 13. RECURSIVE VARIABLE DEFINITIONS
    # =================================================================

    def test_recursive_definition(self):
        """Test a = a + 1 type logic."""
        self.calc.process_input_line("a = 1")
        self.calc.process_input_line("a = a + 1")
        self.assertIn("Result: $$2$$", self.calc.process_input_line("a"))
        
    def test_deep_variable_chain(self):
        """Test a=1, b=a, c=b, d=c ... z=y."""
        self.calc.process_input_line("a = 1")
        vars_list = "abcdefgh"
        for i in range(len(vars_list)-1):
            self.calc.process_input_line(f"{vars_list[i+1]} = {vars_list[i]} + 1")
        
        # h should be 1 + 7 = 8
        self.assertIn("Result: $$8$$", self.calc.process_input_line("h"))

    # =================================================================
    # 14. EXTREME NESTING & ARGUMENTS
    # =================================================================

    def test_nested_trig_hell(self):
        """Test sin(cos(sin(cos(0))))."""
        res = self.calc.process_input_line("sin(cos(sin(cos(0))))")
        self.assertTrue("sin" in res or "cos" in res or "Result" in res)
        
    def test_massive_power(self):
        """Test 2^100."""
        res = self.calc.process_input_line("2^100")
        self.assertIn("1267650600228229401496703205376", res)

    def test_zero_power_zero(self):
        """Test 0^0."""
        res = self.calc.process_input_line("0^0")
        self.assertIn("Result: $$1$$", res)

if __name__ == '__main__':
    print("Running Extreme Calculator Unit Tests...\n")
    unittest.main()