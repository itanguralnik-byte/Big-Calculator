# app.py
from flask import Flask, request, jsonify, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from calc_logic import run_calculator, CalculationError
import os
import logging

# ============================================================
#                  SECURITY CONFIGURATION
# ============================================================

app = Flask(__name__)

# 1. LIMIT PAYLOAD SIZE
# Reject any request body larger than 16KB immediately.
# This prevents users from uploading massive text files to crash memory.
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 

# 2. RATE LIMITING
# Initialize Limiter to track requests by IP address.
# Storage is in-memory by default (good for single server).
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Configure logging to catch attack attempts
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SecurityLog")

# ============================================================
#                  ERROR HANDLERS
# ============================================================

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handles uploads that exceed MAX_CONTENT_LENGTH."""
    logger.warning(f"DoS Attempt: Payload too large from {request.remote_addr}")
    return jsonify({"output": "ERROR: Request too large (Max 16KB)."}), 413

@app.errorhandler(429)
def ratelimit_handler(e):
    """Handles users hitting the rate limit."""
    logger.warning(f"DoS Attempt: Rate limit exceeded from {request.remote_addr}")
    return jsonify({"output": f"ERROR: Rate limit exceeded. {e.description}"}), 429

# ============================================================
#                  ROUTES
# ============================================================

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/api/calculate", methods=["POST"])
# 3. STRICTER RATE LIMIT FOR CALCULATION
# Calculating is CPU expensive, so we limit it strictly (e.g., 1 request per second).
@limiter.limit("60 per minute") 
def api_calculate():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"output": "ERROR: No JSON data received."}), 400
        
        mode = data.get("mode", "fraction")
        expression_lines = data.get("inputs", [])
        show_steps = data.get("show_steps", False)
        # Get the new stateless mode flag
        stateless_mode = data.get("stateless_mode", False) 

        # 4. INPUT COMPLEXITY LIMITS (The "Logic Firewall")
        # Even if payload is small, a user could send 1000 tiny lines 
        # or one incredibly complex line to hang the CPU.
        
        # Limit A: Max number of lines
        if len(expression_lines) > 30:
            return jsonify({"output": "ERROR: Too many lines (Max 30)."}), 400

        # Limit B: Max characters per line
        for i, line in enumerate(expression_lines):
            if len(line) > 500:
                return jsonify({"output": f"ERROR: Line {i+1} is too long (Max 500 chars)."}), 400

        # Run the calculator logic, passing the new flag
        output = run_calculator(mode, expression_lines, show_steps=show_steps, stateless_mode=stateless_mode)
        return jsonify({"output": output})

    except Exception as e:
        logger.error(f"Server Error: {str(e)}")
        # Return a generic error to the user to avoid leaking system info
        return jsonify({"output": "SERVER ERROR: Calculation failed."}), 500

if __name__ == "__main__":
    # 5. DISABLE DEBUG MODE
    # Never run with debug=True in production. It allows remote code execution.
    app.run(debug=False, host='0.0.0.0', port=5000)