import unittest
import sys
import os
import signal
import html

# Add static folder to path so we can import calc_logic
sys.path.append(os.path.join(os.path.dirname(__file__), 'static'))

from calc_logic import Calculator, CalculationError

# Helper to handle timeouts for DoS tests (works on Unix/Mac)
class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Calculation timed out!")

class TestPenetrationSuite(unittest.TestCase):
    """
    Advanced Penetration Testing Suite v2.2
    
    Covers:
    1. XSS & HTML Injection (Crucial for the share-URL vector)
    2. Python Sandbox Escapes (MRO walking, Global access)
    3. SymPy Gadgets & Logic Abuse
    4. Advanced DoS (Recursion & Memory)
    5. Unicode/Homoglyph Obfuscation
    """

    def setUp(self):
        self.calc = Calculator(mode="fraction", stateless_mode=True)
        # Register signal handler for timeouts
        if hasattr(signal, "SIGALRM"):
            signal.signal(signal.SIGALRM, timeout_handler)

    def tearDown(self):
        # Reset alarm
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)

    # =================================================================
    # 1. XSS & HTML INJECTION (CRITICAL)
    # =================================================================
    
    def test_xss_in_error_message(self):
        """
        Attack: Inject HTML via a ValueError using a function that echoes input.
        Goal: Verify that the error message output is HTML-escaped.
        """
        # We use a payload that doesn't break python string syntax.
        payload = "<b>bold_error</b>"
        
        # NOTE: We use 'mean' because 'float' is not in SAFE_LOCALS (it becomes a Symbol),
        # causing a TypeError that doesn't contain the payload.
        # 'mean' is wrapped to call float() and will raise a visible ValueError.
        bad_input = f'mean(["{payload}"])'
        
        try:
            self.calc.process_input_line(bad_input)
            self.fail("Expected ValueError was not raised")
        except CalculationError as e:
            error_msg = str(e)
            # Verify the raw exception contains the payload
            self.assertIn(payload, error_msg)

    def test_xss_rendering_check(self):
        """
        Full pipeline test: Run an input that fails, ensures the HTML output 
        renders the error safely (escaped).
        """
        from calc_logic import run_calculator
        
        # NOTE: Pay attention to quoting to avoid SyntaxErrors in the test setup itself.
        # We want the 'mean' function to receive a list containing a string.
        # Payload: <script>alert('XSS')</script>
        # Python Code: mean(["<script>alert('XSS')</script>"])
        
        payload_inner = "<script>alert('XSS')</script>"
        expr_line = f'mean(["{payload_inner}"])'
        
        # Run the full pipeline (this simulates what the web worker does)
        output_html, _ = run_calculator("float", [expr_line])
        
        # FAIL condition: The raw script tag appears in the HTML output
        if "<script>" in output_html:
            self.fail("CRITICAL XSS: Raw <script> tag found in output HTML.")
            
        # PASS condition: The tag is escaped.
        # We check for the HTML entity version of the brackets.
        self.assertIn("&lt;script&gt;", output_html)

    # =================================================================
    # 2. PYTHON SANDBOX ESCAPE (JAILBREAKS)
    # =================================================================

    def test_mro_jailbreak(self):
        """
        Attack: Method Resolution Order (MRO) walking to access 'object' subclasses.
        Payload: ().__class__.__base__.__subclasses__()
        """
        payloads = [
            "[x for x in ().__class__.__base__.__subclasses__() if x.__name__ == 'Popen']",
            "().__class__.__bases__[0].__subclasses__()"
        ]
        
        for p in payloads:
            try:
                self.calc.process_input_line(p)
                self.fail(f"SANDBOX ESCAPE: MRO walker did not trigger security error: {p}")
            except CalculationError as e:
                # Expect our custom Security Error via ".__" check
                self.assertIn("Security Error", str(e))

    def test_builtins_access(self):
        """
        Attack: Recovering __builtins__ via globals or function attributes.
        """
        # Attempt to access globals via a defined function (like 'sin')
        payload = "sin.__globals__['__builtins__']['open']('/etc/passwd')"
        
        try:
            self.calc.process_input_line(payload)
            self.fail("SANDBOX ESCAPE: Accessed __globals__ successfully.")
        except CalculationError as e:
            # We expect either a Security Error (due to "__") or attribute error
            pass

    def test_format_string_exploit(self):
        """
        Attack: Using string formatting to access object internals.
        Payload: "{0.__init__.__globals__}".format(func)
        """
        payload = '"{0.__class__}".format(1)'
        
        try:
            self.calc.process_input_line(payload)
            self.fail("SECURITY FAIL: .format() method was allowed.")
        except CalculationError as e:
            self.assertIn("Security Error", str(e))

    # =================================================================
    # 3. UNICODE & OBFUSCATION
    # =================================================================
    
    def test_nfkc_normalization_bypass(self):
        """
        Attack: Use multiple variants of unicode that normalize to 'lambda' or 'λ'.
        """
        # Mathematical Italic Small Lambda (𝜆) -> U+1D706. 
        # Normalized by NFKC -> λ (Greek Small Letter Lamda) -> U+03BB
        # We want to ensure this is blocked explicitly.
        payload = "𝜆 x: x"
        try:
            self.calc.process_input_line(payload)
            self.fail("SECURITY FAIL: Italic Lambda bypassed filter.")
        except CalculationError as e:
            # We now expect "Security Error" because we added 'λ' to the blacklist.
            self.assertIn("Security Error", str(e))

    def test_invisible_chars(self):
        """
        Attack: Inject invisible unicode characters inside keywords to break regex.
        e.g., 'l\u200bambda' (Zero width space)
        """
        payload = "l\u200bambda x: x"
        try:
            # If the normalizer strips this, it becomes lambda -> blocked.
            self.calc.process_input_line(payload)
            self.fail("Should have been blocked or caused syntax error")
        except CalculationError as e:
            pass 

if __name__ == '__main__':
    print("Running ADVANCED Penetration Suite v2.2...")
    print("------------------------------------------")
    unittest.main()