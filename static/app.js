document.addEventListener("DOMContentLoaded", () => {
    
    // --- Elements ---
    const calcForm = document.getElementById("calc-form");
    const outputPre = document.getElementById("output-pre");
    const submitButton = document.getElementById("submit-button");
    const textarea = document.getElementById("inputs-textarea");
    const themeToggle = document.getElementById("theme-toggle");
    const clearHistoryBtn = document.getElementById("btn-clear-history");
    
    // --- Constants ---
    const STORAGE_KEY = "big_calc_session";

    // --- 0. Session History ---
    function loadSession() {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved !== null) {
            textarea.value = saved;
        }
    }

    function saveSession() {
        localStorage.setItem(STORAGE_KEY, textarea.value);
    }

    // Load history immediately
    loadSession();

    // Save on physical typing
    textarea.addEventListener("input", saveSession);

    // Clear History Button Logic
    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener("click", () => {
            if (confirm("Are you sure you want to clear your calculation history?")) {
                textarea.value = "";
                outputPre.textContent = "Ready to calculate.";
                outputPre.classList.add("output-placeholder");
                localStorage.removeItem(STORAGE_KEY);
            }
        });
    }

    // --- 1. Dark Mode Logic ---
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

    // --- 2. Virtual Keypad Logic ---
    const keys = document.querySelectorAll(".k-btn");
    
    // Detect if we are on a touch device to optimize keyboard handling
    const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

    if (isTouchDevice) {
        textarea.setAttribute("readonly", "readonly"); 
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
        
        let startPos = textarea.selectionStart;
        let endPos = textarea.selectionEnd;
        let text = textarea.value;

        textarea.focus();

        if (id === "btn-clear") {
            textarea.value = "";
        } else if (id === "btn-backspace") {
            if (startPos > 0 || startPos !== endPos) {
                const deleteCount = (startPos === endPos) ? 1 : 0;
                const newText = text.substring(0, startPos - deleteCount) + text.substring(endPos);
                textarea.value = newText;
                textarea.setSelectionRange(startPos - deleteCount, startPos - deleteCount);
            }
        } 
        else if (id === "btn-left") {
            const newPos = (startPos !== endPos) ? startPos : Math.max(0, startPos - 1);
            textarea.setSelectionRange(newPos, newPos);
        }
        else if (id === "btn-right") {
            const newPos = (startPos !== endPos) ? endPos : Math.min(text.length, endPos + 1);
            textarea.setSelectionRange(newPos, newPos);
        }
        else if (id === "btn-newline") {
            insertAtCursor("\n");
        } else if (val) {
            insertAtCursor(val);
        }

        // Save session after every virtual key press
        saveSession();
    }

    function insertAtCursor(char) {
        let startPos = textarea.selectionStart;
        let endPos = textarea.selectionEnd;
        let text = textarea.value;

        textarea.value = text.substring(0, startPos) + char + text.substring(endPos);
        textarea.setSelectionRange(startPos + char.length, startPos + char.length);
    }

    // --- 3. Calculation Logic (API) ---
    calcForm.addEventListener("submit", (event) => {
        event.preventDefault();

        const formData = new FormData(calcForm);
        const mode = formData.get("output_mode");
        const show_steps = formData.get("show_steps") === "true";
        const text = textarea.value;

        const expression_lines = text.split('\n').filter(line => line.trim().length > 0);

        outputPre.textContent = "Calculating...";
        outputPre.classList.remove("output-placeholder");
        submitButton.disabled = true;
        submitButton.textContent = "...";

        fetch("/api/calculate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                mode: mode,
                inputs: expression_lines,
                show_steps: show_steps
            }),
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(errData => { throw new Error(errData.output); });
            }
            return response.json(); 
        })
        .then(data => {
            outputPre.textContent = data.output;
        })
        .catch(error => {
            outputPre.textContent = `Error: ${error.message}`;
        })
        .finally(() => {
            submitButton.disabled = false;
            submitButton.textContent = "RUN";
        });
    });
});