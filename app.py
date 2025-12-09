# app.py
from flask import Flask, request, jsonify, render_template
from calc_logic import run_calculator
import os

# Initialize the Flask app
# Flask automatically looks for the 'templates' folder
# and the 'static' folder in the same directory.
app = Flask(__name__)

# Route 1: Serve the static frontend application (index.html)
@app.route("/", methods=["GET"])
def index():
    """
    Serves the main index.html file from the 'templates' folder.
    """
    return render_template("index.html")

# Route 2: The API endpoint for calculations
@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    """
    Handles the POST request from the frontend, runs the calculator,
    and returns the result as JSON.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"output": "ERROR: No JSON data received."}), 400
        
        mode = data.get("mode", "fraction")
        expression_lines = data.get("inputs", []) # Expecting a list of strings
        show_steps = data.get("show_steps", False) # Expecting a boolean

        if not expression_lines:
            return jsonify({"output": "ERROR: No input provided."}), 400

        # Run the refactored calculator function.
        # This function is now safe and self-contained.
        output = run_calculator(mode, expression_lines, show_steps=show_steps)
        
        # Return the result as a JSON object
        return jsonify({"output": output})

    except Exception as e:
        # Catch any unexpected server errors
        # The run_calculator function already formats known errors,
        # so this is a fallback for programming errors.
        app.logger.error(f"Unexpected server error: {e}")
        return jsonify({"output": f"SERVER ERROR: {str(e)}"}), 500

if __name__ == "__main__":
    # We'll serve the HTML from the 'templates' folder
    # and any JS/CSS from the 'static' folder (a Flask convention)
    app.run(debug=True)