# app.py
from flask import Flask, request, render_template
from calc_logic import run_calculator

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    output = ""
    # Store request.form in a variable to avoid multiple calls
    form_data = request.form
    
    if request.method == "POST":
        # 1. Get the single output mode from the radio buttons
        mode = form_data.get("output_mode", "fraction")
        
        # 2. Get the text from the textarea
        text = form_data.get("inputs", "")
        
        # 3. Split expressions by line (ignoring empty lines)
        expression_lines = [line for line in text.splitlines() if line and line.strip()]
        
        # 4. Run calculator with the single mode and the list of expressions
        if expression_lines:
            output = run_calculator(mode, expression_lines)

    # Pass the full request.form to template for repopulating fields
    return render_template("index.html", output=output, request=request)

if __name__ == "__main__":
    app.run(debug=True)
