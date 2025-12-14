document.addEventListener("DOMContentLoaded", () => {
    
    // --- Elements ---
    const calcForm = document.getElementById("calc-form");
    const outputDiv = document.getElementById("output-div"); 
    const submitButton = document.getElementById("submit-button");
    const textareaRaw = document.getElementById("inputs-textarea");
    const themeToggle = document.getElementById("theme-toggle");
    const clearHistoryBtn = document.getElementById("btn-clear-history");
    const shareBtn = document.getElementById("btn-share");
    const engineStatus = document.getElementById("engine-status");
    
    const btnLatex = document.getElementById("btn-export-latex");
    const btnPng = document.getElementById("btn-export-png");
    const btnPdf = document.getElementById("btn-export-pdf");

    // Sidebar Elements
    const varListDiv = document.getElementById("var-list");
    const varCountSpan = document.getElementById("var-count");

    // Visual/Code Toggle Elements
    const inputModeRadios = document.querySelectorAll('input[name="input_mode"]');
    const mqContainer = document.getElementById("mathquill-container");
    const cmContainer = document.getElementById("codemirror-container");
    const mqInputDiv = document.getElementById("mq-input-field");

    const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

    // --- Service Worker Registration (Caching) ---
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/sw.js')
            .then(() => console.log("Service Worker Registered (Caching Enabled)"))
            .catch(err => console.log("SW Registration Failed:", err));
    }

    // --- Web Worker Initialization (Background Thread) ---
    const worker = new Worker("/static/calc_worker.js");
    let engineReady = false;
    let currentRawOutput = "";

    submitButton.disabled = true;
    submitButton.textContent = "Loading Engine...";

    worker.onmessage = (e) => {
        const data = e.data;
        
        if (data.status === "ready") {
            engineReady = true;
            submitButton.disabled = false;
            submitButton.textContent = "RUN";
            if(engineStatus) engineStatus.textContent = "Engine Ready (Background Thread)";
        } 
        else if (data.status === "success") {
            // Store raw output for LaTeX export
            currentRawOutput = data.output;
            
            // Handle successful calculation
            const formattedOutput = data.output.replace(/\n/g, "<br>");
            outputDiv.innerHTML = formattedOutput;
            if (window.MathJax) MathJax.typesetPromise([outputDiv]);
            
            // --- Update Sidebar ---
            updateVariableSidebar(data.variables);
            
            submitButton.disabled = false;
            submitButton.textContent = "RUN";
            outputDiv.classList.remove("output-placeholder");
        } 
        else if (data.status === "error") {
            console.error("Worker Error:", data.message);
            outputDiv.textContent = "Error: " + data.message;
            submitButton.disabled = false;
            submitButton.textContent = "RUN";
        }
    };

    // --- CodeMirror Setup ---
    const editor = CodeMirror.fromTextArea(textareaRaw, {
        mode: "python", theme: "default", lineNumbers: true, 
        lineWrapping: true, matchBrackets: true, styleActiveLine: true,
        viewportMargin: Infinity, readOnly: isTouchDevice ? "nocursor" : false 
    });

    // --- MathQuill Setup ---
    const MQ = MathQuill.getInterface(2);
    const mathQuillInstance = MQ.MathField(mqInputDiv, {
        spaceBehavesLikeTab: true,
        autoCommands: 'pi theta sqrt sum int', 
        handlers: {
            edit: function() {
                // Optional: sync logic if needed continuously
            }
        }
    });

    // FIX: Allow clicking anywhere in the container to focus MathQuill
    mqContainer.addEventListener("click", (e) => {
        // We only force focus if the click wasn't already on the inner field
        // This ensures the cursor goes to the clicked position if they clicked text
        if (!e.target.classList.contains('mq-textarea')) {
             mathQuillInstance.focus();
        }
    });

    // --- Latex -> SymPy Translator ---
    function latexToSympy(latex) {
        let s = latex;
        // 1. Basic Replacements
        // Fixed: Removed erroneous \s replacement that broke \sqrt and \sin
        
        // 2. Remove \left and \right scaling commands
        s = s.replace(/\\left\(/g, "(").replace(/\\right\)/g, ")");
        s = s.replace(/\\left\[/g, "[").replace(/\\right\]/g, "]");
        s = s.replace(/\\left/g, "").replace(/\\right/g, "");

        // 3. Greek Letters
        s = s.replace(/\\pi/g, "pi");
        s = s.replace(/\\theta/g, "theta");
        s = s.replace(/\\lambda/g, "lambda");
        s = s.replace(/\\alpha/g, "alpha");
        s = s.replace(/\\beta/g, "beta");

        // 3.5 Mixed Fractions: 1\frac{1}{2} -> 1+1/2
        // If a digit is immediately followed by a fraction, treat as addition (Mixed Number)
        s = s.replace(/(\d)\s*\\frac/g, "$1+\\frac");

        // 4. Fractions: \frac{a}{b} -> (a)/(b)
        while (s.includes("\\frac{")) {
            let oldS = s;
            s = s.replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, "($1)/($2)");
            if (s === oldS) break; 
        }

        // 5. Roots: \sqrt{x} -> sqrt(x)
        while (s.includes("\\sqrt")) {
            let oldS = s;
            s = s.replace(/\\sqrt\{([^{}]+)\}/g, "sqrt($1)");
            s = s.replace(/\\sqrt\[([^{}]+)\]\{([^{}]+)\}/g, "($2)^(1/$1)");
            if (s === oldS) break;
        }

        // 6. Operators & Powers
        s = s.replace(/\\cdot/g, "*");
        s = s.replace(/\\times/g, "*");
        s = s.replace(/\\div/g, "/");
        s = s.replace(/\^/g, "**");
        s = s.replace(/\*\*\{([^{}]+)\}/g, "**($1)");

        // 7. Trig & Logs
        const funcs = ["sin", "cos", "tan", "asin", "acos", "atan", "log", "ln", "exp", "sinh", "cosh", "tanh"];
        funcs.forEach(f => {
            const re = new RegExp("\\\\" + f + "(?![a-zA-Z])", "g");
            s = s.replace(re, f);
        });

        // 8. Cleanup Braces
        while (s.match(/\{([^{}]+)\}/)) {
             let oldS = s;
             s = s.replace(/\{([^{}]+)\}/g, "($1)"); 
             if (s === oldS) break;
        }

        s = s.replace(/\\/g, ""); 
        return s;
    }

    // --- Input Mode Toggle Logic ---
    function switchInputMode(mode) {
        if (mode === "visual") {
            mqContainer.style.display = "block";
            cmContainer.style.display = "none";
            
            // Only auto-focus on desktop to avoid keyboard popping up on mobile 
            // immediately when switching tabs
            if (!isTouchDevice) {
                mathQuillInstance.focus();
            }
        } else {
            mqContainer.style.display = "none";
            cmContainer.style.display = "block";
            
            // Sync: Visual -> Code
            const visualCode = latexToSympy(mathQuillInstance.latex());
            if (visualCode && visualCode !== "") {
                editor.setValue(visualCode);
            }
            editor.refresh();
        }
    }

    inputModeRadios.forEach(radio => {
        radio.addEventListener("change", (e) => switchInputMode(e.target.value));
    });

    // Default to visual
    switchInputMode("visual");


    // --- History & Shared URL Logic ---
    const STORAGE_KEY = "big_calc_session";

    function loadFromHash() {
        const hash = window.location.hash;
        if (hash && hash.startsWith("#code=")) {
            try {
                const compressed = hash.substring(6); 
                const decompressed = LZString.decompressFromEncodedURIComponent(compressed);
                if (decompressed) {
                    editor.setValue(decompressed);
                    document.querySelector('input[name="input_mode"][value="code"]').checked = true;
                    switchInputMode("code");

                    outputDiv.innerHTML = "Loaded shared calculation.";
                    outputDiv.classList.remove("output-placeholder");
                    return true;
                }
            } catch (e) {
                console.error("Failed to decompress URL state", e);
            }
        }
        return false;
    }

    if (!loadFromHash()) {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved !== null) editor.setValue(saved);
    }

    editor.on("change", () => {
        localStorage.setItem(STORAGE_KEY, editor.getValue());
    });

    // Share Button
    if (shareBtn) {
        shareBtn.addEventListener("click", () => {
            const mode = document.querySelector('input[name="input_mode"]:checked').value;
            let code = editor.getValue();
            if (mode === "visual") {
                code = latexToSympy(mathQuillInstance.latex());
            }

            if (!code.trim()) return;

            const compressed = LZString.compressToEncodedURIComponent(code);
            const newUrl = `${window.location.origin}${window.location.pathname}#code=${compressed}`;
            history.pushState(null, null, newUrl);

            navigator.clipboard.writeText(newUrl).then(() => {
                const originalText = shareBtn.textContent;
                shareBtn.textContent = "Copied!";
                setTimeout(() => shareBtn.textContent = originalText, 2000);
            }).catch(err => {
                console.error("Failed to copy: ", err);
                alert("URL updated! Copy it from the address bar.");
            });
        });
    }

    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener("click", () => {
            if (window.confirm("Clear history?")) {
                editor.setValue("");
                mathQuillInstance.latex("");
                if (!isTouchDevice) mathQuillInstance.focus();
                
                outputDiv.textContent = "Ready.";
                outputDiv.classList.add("output-placeholder");
                localStorage.removeItem(STORAGE_KEY);
                currentRawOutput = "";
                history.pushState(null, null, window.location.pathname);
            }
        });
    }

    // --- Export Logic ---
    btnLatex.addEventListener("click", () => {
        if (!currentRawOutput) return alert("No results to export.");
        navigator.clipboard.writeText(currentRawOutput).then(() => {
            const original = btnLatex.textContent;
            btnLatex.textContent = "Copied!";
            setTimeout(() => btnLatex.textContent = original, 2000);
        });
    });

    btnPng.addEventListener("click", () => {
        if (outputDiv.classList.contains("output-placeholder")) return;
        html2canvas(outputDiv, {
            backgroundColor: getComputedStyle(document.body).getPropertyValue('--bg-card').trim(), 
            scale: 2 
        }).then(canvas => {
            const link = document.createElement('a');
            link.download = 'calc_result.png';
            link.href = canvas.toDataURL();
            link.click();
        });
    });

    btnPdf.addEventListener("click", () => {
        if (outputDiv.classList.contains("output-placeholder")) return;
        const { jsPDF } = window.jspdf;
        html2canvas(outputDiv, {
            scale: 2,
            backgroundColor: "#ffffff"
        }).then(canvas => {
            const imgData = canvas.toDataURL('image/png');
            const pdf = new jsPDF('p', 'mm', 'a4');
            const imgProps = pdf.getImageProperties(imgData);
            const pdfWidth = pdf.internal.pageSize.getWidth();
            const pdfHeight = (imgProps.height * pdfWidth) / imgProps.width;
            pdf.addImage(imgData, 'PNG', 0, 0, pdfWidth, pdfHeight);
            pdf.save("calc_result.pdf");
        });
    });

    // --- Theme Logic ---
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

    // --- Sidebar Logic ---
    function updateVariableSidebar(variablesMap) {
        varListDiv.innerHTML = "";
        
        let vars = [];
        if (variablesMap instanceof Map) {
            variablesMap.forEach((val, key) => vars.push({ key, ...val }));
        } else {
            vars = Object.entries(variablesMap).map(([key, val]) => ({ key, ...val }));
        }

        varCountSpan.textContent = vars.length;

        if (vars.length === 0) {
            varListDiv.innerHTML = '<div class="empty-state">No variables defined.</div>';
            return;
        }

        vars.forEach(v => {
            const card = document.createElement("div");
            card.className = "var-card";
            card.title = "Click to insert into editor";
            
            const displayVal = v.display; 
            
            card.innerHTML = `
                <div class="var-top">
                    <span class="var-name">${v.key}</span>
                    <div class="var-actions">
                        <button class="btn-icon-small delete-var" data-name="${v.key}" title="Delete Variable">
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                        </button>
                    </div>
                </div>
                <div class="var-value">${displayVal}</div>
            `;

            // Click to Insert
            card.addEventListener("click", (e) => {
                if (e.target.closest('.delete-var')) return;
                
                const mode = document.querySelector('input[name="input_mode"]:checked').value;

                if (mode === "visual") {
                    mathQuillInstance.write(v.key);
                    // Only focus on desktop to prevent keyboard popup on mobile
                    if (!isTouchDevice) mathQuillInstance.focus();
                } else {
                    if (!isTouchDevice) editor.focus();
                    const doc = editor.getDoc();
                    const cursor = doc.getCursor();
                    doc.replaceRange(v.key, cursor);
                }
            });

            // Click to Delete
            const delBtn = card.querySelector(".delete-var");
            delBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                if (confirm(`Delete variable '${v.key}'?`)) {
                    card.remove();
                    worker.postMessage({ type: "DELETE_VAR", name: v.key });
                    varCountSpan.textContent = parseInt(varCountSpan.textContent) - 1;
                }
            });

            varListDiv.appendChild(card);
        });

        if (window.MathJax) MathJax.typesetPromise([varListDiv]);
    }

    // --- Keypad Logic ---
    const keys = document.querySelectorAll(".k-btn");
    keys.forEach(btn => {
        btn.addEventListener("click", (e) => {
            if (btn.type !== "submit") {
                e.preventDefault();
                handleKeyInput(btn);
            }
        });
    });

    function handleKeyInput(btn) {
        const mode = document.querySelector('input[name="input_mode"]:checked').value;
        const val = btn.dataset.val;
        const id = btn.id;

        if (mode === "visual") {
            // --- MathQuill Keypad Handling ---
            if (id === "btn-clear") mathQuillInstance.latex("");
            else if (id === "btn-backspace") mathQuillInstance.keystroke("Backspace");
            else if (id === "btn-left") mathQuillInstance.keystroke("Left");
            else if (id === "btn-right") mathQuillInstance.keystroke("Right");
            else if (id === "btn-newline") {
                // Not supported for single-line visual math
            }
            else {
                // Mapping complex buttons to MQ Commands
                if (val === "sin(") { mathQuillInstance.cmd("sin"); mathQuillInstance.cmd("("); }
                else if (val === "cos(") { mathQuillInstance.cmd("cos"); mathQuillInstance.cmd("("); }
                else if (val === "sqrt(") mathQuillInstance.cmd("sqrt");
                else if (val === "log(") { mathQuillInstance.cmd("log"); mathQuillInstance.cmd("("); }
                // FIX: Use typedText("/") for smart fraction wrapping instead of cmd("frac")
                else if (val === "/") mathQuillInstance.cmd("\\div");
                else if (val === "^") mathQuillInstance.cmd("^");
                else if (val === "π") mathQuillInstance.cmd("pi");
                else {
                    mathQuillInstance.write(val);
                }
            }
            
            // FIX: Only focus on Desktop to keep the mobile keyboard hidden
            if (!isTouchDevice) {
                mathQuillInstance.focus();
            }
        } 
        else {
            // --- CodeMirror Keypad Handling (Original) ---
            if (!isTouchDevice) editor.focus();
            const doc = editor.getDoc();
            const cursor = doc.getCursor(); 

            if (id === "btn-clear") editor.setValue("");
            else if (id === "btn-backspace") {
                if (doc.somethingSelected()) doc.replaceSelection("");
                else editor.execCommand("delCharBefore");
            } 
            else if (id === "btn-left") editor.execCommand("goCharLeft");
            else if (id === "btn-right") editor.execCommand("goCharRight");
            else if (id === "btn-newline") editor.execCommand("newlineAndIndent");
            else if (val) doc.replaceRange(val, cursor);
        }
    }

    // --- Submit Logic (Sends message to Worker) ---
    calcForm.addEventListener("submit", (event) => {
        event.preventDefault();

        if (!engineReady) {
            outputDiv.textContent = "Engine is still loading resources...";
            return;
        }

        // Determine input source
        const mode = document.querySelector('input[name="input_mode"]:checked').value;
        let expression_lines = [];

        if (mode === "visual") {
            const rawLatex = mathQuillInstance.latex();
            const pyCode = latexToSympy(rawLatex);
            // We treat visual input as a single line expression for now
            if (pyCode.trim()) expression_lines = [pyCode];
        } else {
            const text = editor.getValue();
            expression_lines = text.split('\n').filter(line => line.trim().length > 0);
        }

        const formData = new FormData(calcForm);

        outputDiv.innerHTML = "Calculating..."; 
        outputDiv.classList.remove("output-placeholder");
        submitButton.disabled = true;
        submitButton.textContent = "...";
        currentRawOutput = ""; // Reset export buffer

        // Send data to worker
        worker.postMessage({
            type: "CALCULATE",
            mode: formData.get("output_mode"),
            show_steps: formData.get("show_steps") === "true",
            stateless_mode: formData.get("stateless_mode") === "true",
            expression_lines: expression_lines
        });
    });
});