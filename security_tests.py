import unittest
import sys
import os
import time
import signal
import unicodedata

# Add static folder to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'static'))

from calc_logic import Calculator, CalculationError

# Helper to handle timeouts for DoS tests
class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Calculation timed out!")

class TestAdvancedSecurity(unittest.TestCase):
    """
    Advanced Security & Penetration Testing Suite.
    
    Covers:
    1. Homoglyph/Unicode Attacks (Bypassing keyword filters)
    2. Resource Exhaustion (CPU/Memory Bombs)
    3. Information Leakage (Path exposure)
    4. Obfuscation Techniques
    """

    def setUp(self):
        self.calc = Calculator(mode="fraction", stateless_mode=True)
        # Register signal handler for timeouts (Works on Linux/Mac)
        if hasattr(signal, "SIGALRM"):
            signal.signal(signal.SIGALRM, timeout_handler)

    def tearDown(self):
        # Reset alarm
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)

    # =================================================================
    # 1. UNICODE & NORMALIZATION ATTACKS
    # =================================================================
    
    def test_homoglyph_keyword_bypass(self):
        """
        Attack: Use look-alike Unicode characters to bypass 'lambda' or '__' filters.
        Python 3 normalizes identifiers (NFKC), so 'ｌａｍｂｄａ' (Fullwidth) executes as 'lambda'.
        """
        # Fullwidth 'lambda' (Ｕ＋ＦＦ４Ｃ ...)
        malicious_input = "ｌａｍｂｄａ x: x" 
        
        # Verify that the filter catches this normalization
        # If this fails, the filter checks the raw string but Python executes the normalized version.
        try:
            self.calc.process_input_line(malicious_input)
            self.fail("SECURITY FAIL: Fullwidth 'lambda' bypassed the filter!")
        except CalculationError as e:
            self.assertIn("Security Error", str(e))

    def test_homoglyph_dunder_bypass(self):
        """
        Attack: Use Fullwidth underscores '＿' to access internals.
        """
        # "test".__class__ using fullwidth underscores
        malicious_input = "'test'.＿class＿"
        
        try:
            self.calc.process_input_line(malicious_input)
            self.fail("SECURITY FAIL: Fullwidth underscores bypassed the filter!")
        except CalculationError as e:
            self.assertIn("Security Error", str(e))

    # =================================================================
    # 2. RESOURCE EXHAUSTION (DoS)
    # =================================================================

    def test_factorial_bomb(self):
        """
        Attack: Calculate a massive factorial to hang the CPU/Memory.
        Expected: The sandbox should either error out or the test limits must catch it.
        """
        # factorial(1000000) produces a number with ~5.5 million digits.
        # This usually hangs standard parsers or consumes massive RAM.
        try:
            # Set a 2-second alarm (Strict time limit)
            if hasattr(signal, "SIGALRM"): signal.alarm(2)
            
            self.calc.process_input_line("factorial(1000000)")
            
        except TimeoutError:
            self.fail("DoS FAIL: factorial(1000000) caused a timeout/hang.")
        except CalculationError:
            pass # Acceptable result (e.g. "Integer too large")
        finally:
            if hasattr(signal, "SIGALRM"): signal.alarm(0)

    def test_expansion_bomb(self):
        """
        Attack: '10**10**5' create numbers larger than available memory.
        """
        try:
            if hasattr(signal, "SIGALRM"): signal.alarm(2)
            self.calc.process_input_line("10^(10^5)")
        except TimeoutError:
            self.fail("DoS FAIL: Massive exponentiation caused a hang.")
        except CalculationError:
            pass 
        except MemoryError:
            pass # Acceptable if handled gracefully
        finally:
             if hasattr(signal, "SIGALRM"): signal.alarm(0)

    def test_container_bomb(self):
        """
        Attack: Create a list so large it exhausts RAM.
        [1] * 100,000,000
        """
        try:
            # Note: SymPy might handle this lazily, but standard python lists won't.
            # We try to force evaluation using statistics functions if lists are supported
            if hasattr(signal, "SIGALRM"): signal.alarm(2)
            self.calc.process_input_line("mean([1] * 10000000)")
        except TimeoutError:
            self.fail("DoS FAIL: Massive list creation caused a hang.")
        except CalculationError:
            pass
        finally:
             if hasattr(signal, "SIGALRM"): signal.alarm(0)

    # =================================================================
    # 3. INFORMATION LEAKAGE
    # =================================================================

    def test_error_message_path_leak(self):
        """
        Attack: Force a syntax error or runtime error and check if it leaks server paths.
        (e.g., '/home/ubuntu/app/calc_logic.py')
        """
        try:
            # Force a recursion error or similar internal failure
            self.calc.process_input_line("1 / 0")
        except CalculationError as e:
            msg = str(e)
            # Check for common path separators that shouldn't be there
            if "/" in msg and ".py" in msg:
                # Allow relative paths like "calc_logic.py", block absolute "/Users/..."
                if msg.startswith("/"): 
                    self.fail(f"INFO LEAK: Error message contains absolute file path: {msg}")

    # =================================================================
    # 4. GADGET CHAINS & OBFUSCATION
    # =================================================================

    def test_getattr_bypass(self):
        """
        Attack: Use getattr() to access attributes without using the dot notation.
        e.g. getattr(obj, "class") instead of obj.class (if blocked)
        """
        # We need to ensure 'getattr' is NOT available in the function whitelist.
        with self.assertRaises(CalculationError):
            self.calc.process_input_line("getattr(1, 'real')")

    def test_encoded_strings(self):
        """
        Attack: Hex encoded strings to hide keywords.
        eval('\x5f\x5fimport\x5f\x5f')
        """
        # This relies on the 'eval' or 'exec' function being blocked, 
        # but also tests if the parser unescapes string literals before checking.
        with self.assertRaises(CalculationError):
            # Hex for __import__
            self.calc.process_input_line("'\\x5f\\x5fimport\\x5f\\x5f'")

if __name__ == '__main__':
    print("Running ADVANCED Penetration Tests...\n")
    unittest.main()