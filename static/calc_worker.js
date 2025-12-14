// static/calc_worker.js
importScripts("https://cdn.jsdelivr.net/pyodide/v0.23.4/full/pyodide.js");

let pyodide = null;
let pyodideReady = false;

async function loadEngine() {
    try {
        // 1. Initialize Pyodide
        pyodide = await loadPyodide();
        
        // 2. Load SymPy (This is the heavy part)
        await pyodide.loadPackage("sympy");
        
        // 3. Fetch custom logic from server
        const response = await fetch("/static/calc_logic.py");
        if (!response.ok) throw new Error("Could not fetch calc_logic.py");
        const pythonCode = await response.text();
        
        // 4. Write file and import
        pyodide.FS.writeFile("calc_logic.py", pythonCode);
        
        // Import the updated logic (run_calculator AND delete_variable)
        // We define a wrapper to handle JSON serialization of variables
        // This ensures complex nested dictionaries are passed to JS as plain objects,
        // preventing "undefined" values in the UI and cloning errors.
        pyodide.runPython(`
            from calc_logic import run_calculator, delete_variable
            import sys
            import json
            sys.setrecursionlimit(2000)

            def run_wrapper(mode, expression_lines, show_steps, stateless_mode):
                output_html, variables_dict = run_calculator(mode, expression_lines, show_steps, stateless_mode)
                # Serialize variables to JSON string to ensure safe transport to JS
                return output_html, json.dumps(variables_dict)
        `);

        pyodideReady = true;
        postMessage({ status: "ready" });
        
    } catch (err) {
        postMessage({ status: "error", message: err.message });
    }
}

// Start loading immediately
loadEngine();

// Listen for calculation requests from app.js
onmessage = async function(e) {
    const data = e.data;
    
    if (data.type === "CALCULATE") {
        if (!pyodideReady) {
            postMessage({ status: "error", message: "Engine still loading..." });
            return;
        }

        try {
            // Use the wrapper function
            const runCalc = pyodide.globals.get("run_wrapper");
            
            // Run the Python function
            // Returns a Python Tuple: (output_html, variables_json_string)
            const resultTuple = runCalc(
                data.mode, 
                data.expression_lines, 
                data.show_steps, 
                data.stateless_mode
            );
            
            // Unpack Tuple using .get()
            const outputHtml = resultTuple.get(0);
            const variablesJson = resultTuple.get(1);
            
            // Parse JSON string back to JS Object
            const variables = JSON.parse(variablesJson);
            
            // Cleanup proxies
            runCalc.destroy(); 
            resultTuple.destroy();

            // Send back HTML + Variables
            postMessage({ 
                status: "success", 
                output: outputHtml,
                variables: variables 
            });
            
        } catch (err) {
            postMessage({ status: "error", message: err.message });
        }
    }
    
    else if (data.type === "DELETE_VAR") {
        if (!pyodideReady) return;
        try {
            const delVar = pyodide.globals.get("delete_variable");
            delVar(data.name);
            delVar.destroy();
            // No response needed, UI update is optimistic or handled by next calc
        } catch(err) {
            console.error("Delete failed", err);
        }
    }
};