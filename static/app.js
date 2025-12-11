document.addEventListener("DOMContentLoaded", () => {
    
    // --- Elements ---
    const calcForm = document.getElementById("calc-form");
    const outputDiv = document.getElementById("output-div"); 
    const submitButton = document.getElementById("submit-button");
    const textareaRaw = document.getElementById("inputs-textarea");
    const themeToggle = document.getElementById("theme-toggle");
    const clearHistoryBtn = document.getElementById("btn-clear-history");
    
    // --- Constants ---
    const STORAGE_KEY = "big_calc_session";

    // --- 0. Initialize CodeMirror ---
    // This replaces the raw textarea with the code editor
    const editor = CodeMirror.fromTextArea(textareaRaw, {
        mode: "python", // Python mode matches SymPy/Calculator syntax
        theme: "default", // We override colors in CSS via variables
        lineNumbers: true,
        lineWrapping: true,
        matchBrackets: true,
        styleActiveLine: true,
        viewportMargin: Infinity // Auto-resize height logic if needed
    });

    // --- 1. Session History ---
    function loadSession() {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved !== null) {
            editor.setValue(saved);
        }
    }

    function saveSession() {
        localStorage.setItem(STORAGE_KEY, editor.getValue());
    }

    // Load history immediately
    loadSession();

    // Save on any change in the editor
    editor.on("change", saveSession);

    // Clear History Button Logic
    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener("click", () => {
            // IMPORTANT: Use custom modal UI instead of confirm() in production
            if (window.confirm("Are you sure you want to clear your calculation history?")) {
                editor.setValue("");
                editor.focus();
                outputDiv.textContent = "Ready to calculate.";
                outputDiv.classList.add("output-placeholder");
                localStorage.removeItem(STORAGE_KEY);
            }
        });
    }

    // --- 2. Dark Mode Logic ---
    let isDark = localStorage.getItem("theme") === "dark";
    updateTheme();

    themeToggle.addEventListener("click", () => {
        isDark = !isDark;
        localStorage.setItem("theme", isDark ? "dark" : "light");
        updateTheme();
    });

    function updateTheme() {
        document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
    }

    // --- 3. Virtual Keypad Logic (Refactored for CodeMirror) ---
    const keys = document.querySelectorAll(".k-btn");
    
    // Detect touch device
    const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

    if (isTouchDevice) {
        // Optional: Can add specific touch handling here if needed
    }

    keys.forEach(btn => {
        btn.addEventListener("click", (e) => {
            // Prevent form submit for non-submit buttons
            if (btn.type !== "submit") {
                e.preventDefault();
                handleKeyInput(btn);
            }
        });
    });

    function handleKeyInput(btn) {
        const val = btn.dataset.val;
        const id = btn.id;
        
        editor.focus();
        
        // Get current cursor position
        const doc = editor.getDoc();
        const cursor = doc.getCursor(); 

        if (id === "btn-clear") {
            editor.setValue("");
        } 
        else if (id === "btn-backspace") {
            // If something is selected, delete selection
            if (doc.somethingSelected()) {
                doc.replaceSelection("");
            } else {
                // Delete one character before cursor
                editor.execCommand("delCharBefore");
            }
        } 
        else if (id === "btn-left") {
            editor.execCommand("goCharLeft");
        }
        else if (id === "btn-right") {
            editor.execCommand("goCharRight");
        }
        else if (id === "btn-newline") {
            editor.execCommand("newlineAndIndent");
        } 
        else if (val) {
            doc.replaceRange(val, cursor);
        }
    }

    // --- 4. Calculation Logic (API) ---
    calcForm.addEventListener("submit", (event) => {
        event.preventDefault();

        const formData = new FormData(calcForm);
        const mode = formData.get("output_mode");
        const show_steps = formData.get("show_steps") === "true";
        // Get the new setting
        const stateless_mode = formData.get("stateless_mode") === "true";
        
        // Get value directly from CodeMirror
        const text = editor.getValue();

        const expression_lines = text.split('\n').filter(line => line.trim().length > 0);

        outputDiv.innerHTML = "Calculating..."; 
        outputDiv.classList.remove("output-placeholder");
        submitButton.disabled = true;
        submitButton.textContent = "...";

        fetch("/api/calculate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                mode: mode,
                inputs: expression_lines,
                show_steps: show_steps,
                stateless_mode: stateless_mode // Pass the new setting
            }),
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(errData => { throw new Error(errData.output); });
            }
            return response.json(); 
        })
        .then(data => {
            // Replace newlines with HTML breaks
            const formattedOutput = data.output.replace(/\n/g, "<br>");
            outputDiv.innerHTML = formattedOutput;

            // Trigger MathJax
            if (window.MathJax) {
                MathJax.typesetPromise([outputDiv]).catch((err) => console.log(err));
            }
        })
        .catch(error => {
            outputDiv.textContent = `Error: ${error.message}`;
        })
        .finally(() => {
            submitButton.disabled = false;
            submitButton.textContent = "RUN";
        });
    });
});