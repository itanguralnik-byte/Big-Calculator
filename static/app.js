document.addEventListener("DOMContentLoaded", () => {
    
    // --- Elements ---
    const calcForm = document.getElementById("calc-form");
    const outputDiv = document.getElementById("output-div"); 
    const submitButton = document.getElementById("submit-button");
    const textareaRaw = document.getElementById("inputs-textarea");
    const themeToggle = document.getElementById("theme-toggle");
    const clearHistoryBtn = document.getElementById("btn-clear-history");
    const engineStatus = document.getElementById("engine-status");

    // --- Service Worker Registration (Caching) ---
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/sw.js')
            .then(() => console.log("Service Worker Registered (Caching Enabled)"))
            .catch(err => console.log("SW Registration Failed:", err));
    }

    // --- Web Worker Initialization (Background Thread) ---
    const worker = new Worker("/static/calc_worker.js");
    let engineReady = false;

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
            // Handle successful calculation
            const formattedOutput = data.output.replace(/\n/g, "<br>");
            outputDiv.innerHTML = formattedOutput;
            if (window.MathJax) MathJax.typesetPromise([outputDiv]);
            
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

    // --- CodeMirror & UI Logic (Same as before) ---
    const STORAGE_KEY = "big_calc_session";
    const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

    const editor = CodeMirror.fromTextArea(textareaRaw, {
        mode: "python", theme: "default", lineNumbers: true, 
        lineWrapping: true, matchBrackets: true, styleActiveLine: true,
        viewportMargin: Infinity, readOnly: isTouchDevice ? "nocursor" : false 
    });

    // History Logic
    function loadSession() {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved !== null) editor.setValue(saved);
    }
    loadSession();
    editor.on("change", () => localStorage.setItem(STORAGE_KEY, editor.getValue()));

    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener("click", () => {
            if (window.confirm("Clear history?")) {
                editor.setValue("");
                if (!isTouchDevice) editor.focus();
                outputDiv.textContent = "Ready.";
                localStorage.removeItem(STORAGE_KEY);
            }
        });
    }

    // Theme Logic
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

    // Keypad Logic
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
        const val = btn.dataset.val;
        const id = btn.id;
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

    // --- Submit Logic (Sends message to Worker) ---
    calcForm.addEventListener("submit", (event) => {
        event.preventDefault();

        if (!engineReady) {
            outputDiv.textContent = "Engine is still loading resources...";
            return;
        }

        const formData = new FormData(calcForm);
        const text = editor.getValue();
        const expression_lines = text.split('\n').filter(line => line.trim().length > 0);

        outputDiv.innerHTML = "Calculating..."; 
        outputDiv.classList.remove("output-placeholder");
        submitButton.disabled = true;
        submitButton.textContent = "...";

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