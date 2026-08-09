// ==========================================
// SEND MESSAGE
// ==========================================

async function sendMessage() {

    const input = document.getElementById("user-input");
    const chatBox = document.getElementById("chat-box");
    const sendButton = document.getElementById("send-btn");

    const message = input.value.trim();

    if (message === "") {
        return;
    }


    // --------------------------------------
    // Show user message
    // --------------------------------------

    const userRow = document.createElement("div");

    userRow.className = "message-row user-row";

    const userMessage = document.createElement("div");

    userMessage.className = "user-message";

    userMessage.innerHTML =
        `<span class="avatar">👤</span>
         <span>${escapeHTML(message)}</span>`;

    userRow.appendChild(userMessage);

    chatBox.appendChild(userRow);


    // Remove welcome screen if present

    const welcome = document.querySelector(".welcome-message");

    if (welcome) {
        welcome.remove();
    }


    chatBox.scrollTop = chatBox.scrollHeight;


    // Clear input

    input.value = "";


    // Disable send

    sendButton.disabled = true;


    // --------------------------------------
    // Create AI message
    // --------------------------------------

    const botRow = document.createElement("div");

    botRow.className = "message-row bot-row";


    const botMessage = document.createElement("div");

    botMessage.className = "bot-message";

    botMessage.innerHTML =
        `<span class="avatar">🤖</span>
         <span class="bot-text">Thinking...</span>`;


    botRow.appendChild(botMessage);

    chatBox.appendChild(botRow);


    const botText =
        botMessage.querySelector(".bot-text");


    chatBox.scrollTop = chatBox.scrollHeight;


    try {

        // ----------------------------------
        // Send request
        // ----------------------------------

        const response = await fetch("/chat", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                message: message
            })

        });


        if (!response.ok) {

            throw new Error(
                "Server returned " + response.status
            );

        }


        if (!response.body) {

            throw new Error(
                "Streaming is not supported by this response."
            );

        }


        // ----------------------------------
        // Read stream
        // ----------------------------------

        const reader =
            response.body.getReader();

        const decoder =
            new TextDecoder("utf-8");

        let fullText = "";

        let firstChunk = true;


        while (true) {

            const result =
                await reader.read();

            if (result.done) {
                break;
            }


            const text =
                decoder.decode(
                    result.value,
                    {
                        stream: true
                    }
                );


            if (firstChunk) {

                botText.textContent = "";

                firstChunk = false;
            }


            fullText += text;


            botText.innerHTML =
                formatMessage(fullText);


            chatBox.scrollTop =
                chatBox.scrollHeight;
        }


        // Finish decoder

        const remaining =
            decoder.decode();

        if (remaining) {

            fullText += remaining;

            botText.innerHTML =
                formatMessage(fullText);
        }


        // If nothing came back

        if (fullText.trim() === "") {

            botText.textContent =
                "No response received.";
        }

    }

    catch (error) {

        console.error(
            "Chat error:",
            error
        );


        botText.textContent =
            "Sorry, I couldn't connect to the AI.";
    }


    finally {

        sendButton.disabled = false;

        input.focus();

    }
}


// ==========================================
// ENTER KEY
// ==========================================

document.addEventListener(
    "DOMContentLoaded",
    function () {

        const input =
            document.getElementById("user-input");


        if (!input) {
            return;
        }


        input.addEventListener(
            "keydown",
            function (event) {

                if (
                    event.key === "Enter" &&
                    !event.shiftKey
                ) {

                    event.preventDefault();

                    sendMessage();

                }

            }
        );


        // Auto resize textarea

        input.addEventListener(
            "input",
            function () {

                this.style.height = "auto";

                this.style.height =
                    Math.min(
                        this.scrollHeight,
                        150
                    ) + "px";

            }
        );

    }
);


// ==========================================
// ESCAPE HTML
// ==========================================

function escapeHTML(text) {

    const div =
        document.createElement("div");

    div.textContent = text;

    return div.innerHTML;
}


// ==========================================
// FORMAT AI MESSAGE
// ==========================================

function formatMessage(text) {

    return escapeHTML(text)
        .replace(/\n/g, "<br>");
}