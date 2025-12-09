document.addEventListener("DOMContentLoaded", () => {
    
    // --- Elements ---
    const calcForm = document.getElementById("calc-form");
    const outputPre = document.getElementById("output-pre");
    const submitButton = document.getElementById("submit-button");
    const textarea = document.getElementById("inputs-textarea");
    const themeToggle = document.getElementById("theme-toggle");
    
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
        // On mobile, prevent the native keyboard from showing up when touching the textarea
        // We want the user to use OUR keypad.
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
        
        // Get current cursor position
        let startPos = textarea.selectionStart;
        let endPos = textarea.selectionEnd;
        let text = textarea.value;

        // Focus logic: Keep focus on textarea so we can keep typing
        // On desktop this is fine. On mobile, 'readonly' keeps native keyboard away.
        textarea.focus();

        if (id === "btn-clear") {
            textarea.value = "";
        } else if (id === "btn-backspace") {
            if (startPos > 0 || startPos !== endPos) {
                // If selection, delete selection. If cursor, delete char before.
                const deleteCount = (startPos === endPos) ? 1 : 0;
                const newText = text.substring(0, startPos - deleteCount) + text.substring(endPos);
                textarea.value = newText;
                // Move cursor back
                textarea.setSelectionRange(startPos - deleteCount, startPos - deleteCount);
            }
        } else if (id === "btn-newline") {
            insertAtCursor("\n");
        } else if (val) {
            insertAtCursor(val);
        }
    }

    function insertAtCursor(char) {
        let startPos = textarea.selectionStart;
        let endPos = textarea.selectionEnd;
        let text = textarea.value;

        textarea.value = text.substring(0, startPos) + char + text.substring(endPos);
        // Move cursor after the inserted character
        textarea.setSelectionRange(startPos + char.length, startPos + char.length);
    }

    // --- 3. Calculation Logic (API) ---
    calcForm.addEventListener("submit", (event) => {
        event.preventDefault();

        const formData = new FormData(calcForm);
        const mode = formData.get("output_mode");
        const show_steps = formData.get("show_steps") === "true";
        const text = textarea.value; // Get value directly from element to be safe

        const expression_lines = text.split('\n').filter(line => line.trim().length > 0);

        // UI Loading State
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