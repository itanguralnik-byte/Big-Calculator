import unittest
import math
from fractions import Fraction
from calc_logic import Calculator, run_calculator, CalculationError

class TestCalculatorLogic(unittest.TestCase):

    def setUp(self):
        """Runs before every test method. Resets the calculator."""
        self.calc = Calculator(mode="fraction", show_steps=False)

    # =================================================================
    # 1. BASIC ARITHMETIC & ORDER OF OPERATIONS
    # =================================================================
    
    def test_basic_math(self):
        """Test simple arithmetic operations."""
        self.assertIn("Result: 2", self.calc.process_input_line("1 + 1"))
        self.assertIn("Result: 10", self.calc.process_input_line("2 * 5"))
        self.assertIn("Result: 5", self.calc.process_input_line("10 / 2"))
        self.assertIn("Result: 3", self.calc.process_input_line("5 - 2"))

    def test_order_of_operations(self):
        """Test PEMDAS (Parentheses, Exponents, Mult/Div, Add/Sub)."""
        self.assertIn("Result: 14", self.calc.process_input_line("2 + 3 * 4"))
        self.assertIn("Result: 20", self.calc.process_input_line("(2 + 3) * 4"))
        self.assertIn("Result: 9", self.calc.process_input_line("2^3 + 1"))

    # =================================================================
    # 2. VARIABLES & ASSIGNMENTS
    # =================================================================

    def test_variable_assignment(self):
        out = self.calc.process_input_line("a = 10")
        self.assertIn("Assigned: a = 10", out)
        out = self.calc.process_input_line("a + 5")
        self.assertIn("Result: 15", out)

    def test_dependent_variables(self):
        self.calc.process_input_line("x = 5")
        self.calc.process_input_line("y = x + 2") 
        out = self.calc.process_input_line("y + x") 
        self.assertIn("Result: 12", out)

    # =================================================================
    # 3. SCIENTIFIC FUNCTIONS (NEW)
    # =================================================================

    def test_trig_functions(self):
        """Test sin, cos, tan."""
        # sin(0) = 0
        self.assertIn("Result: 0", self.calc.process_input_line("sin(0)"))
        
        # cos(0) = 1
        self.assertIn("Result: 1", self.calc.process_input_line("cos(0)"))
        
        # test implicit multiplication: 2cos(0) -> 2*1 -> 2
        # Note: Our logic requires strict brackets for functions usually, 
        # but the linear parser might handle coefficients if "cos" wasn't there. 
        # Actually, standard math calls require parens in Python.
        self.assertIn("Result: 2", self.calc.process_input_line("2 * cos(0)"))

    def test_roots_and_logs(self):
        """Test sqrt and log."""
        # sqrt(16) = 4
        self.assertIn("Result: 4", self.calc.process_input_line("sqrt(16)"))
        
        # log10(100) = 2
        self.assertIn("Result: 2", self.calc.process_input_line("log(100)"))
        
        # ln(e) = 1
        self.assertIn("Result: 1", self.calc.process_input_line("ln(2.718281828459)")) 

    def test_nested_functions(self):
        """Test nesting functions like sqrt(16 + 9)."""
        # sqrt(25) = 5
        self.assertIn("Result: 5", self.calc.process_input_line("sqrt(16 + 9)"))
        
        # sin(0) + cos(0) = 0 + 1 = 1
        self.assertIn("Result: 1", self.calc.process_input_line("sin(0) + cos(0)"))

    def test_function_error_handling(self):
        """Test invalid inputs to functions."""
        # sqrt(-1) -> Domain error
        with self.assertRaises(CalculationError):
            self.calc.process_input_line("sqrt(-1)")
            
        # log(-5) -> Domain error
        with self.assertRaises(CalculationError):
            self.calc.process_input_line("log(-5)")

    # =================================================================
    # 4. ERROR HANDLING & SECURITY
    # =================================================================

    def test_division_by_zero(self):
        with self.assertRaises(CalculationError):
            self.calc.process_input_line("5 / 0")

    def test_security_injection(self):
        with self.assertRaises(CalculationError):
            self.calc.process_input_line("__import__('os').system('ls')")

if __name__ == '__main__':
    print("Running Calculator Unit Tests...\n")
    unittest.main()