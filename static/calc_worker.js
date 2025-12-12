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
        pyodide.runPython(`
            from calc_logic import run_calculator
            import sys
            sys.setrecursionlimit(2000)
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
            const runCalc = pyodide.globals.get("run_calculator");
            
            // Run the Python function
            const result = runCalc(
                data.mode, 
                data.expression_lines, 
                data.show_steps, 
                data.stateless_mode
            );
            
            runCalc.destroy(); // Cleanup handle
            postMessage({ status: "success", output: result });
            
        } catch (err) {
            postMessage({ status: "error", message: err.message });
        }
    }
};