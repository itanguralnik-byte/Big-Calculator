# app.py
from flask import Flask, render_template

app = Flask(__name__)

# Basic security: Prevent massive header attacks, though less critical now
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

if __name__ == "__main__":
    # Disable debug in production
    app.run(debug=False, host='0.0.0.0', port=5000)