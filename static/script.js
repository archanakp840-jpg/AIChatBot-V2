let currentController = null;
let isGenerating = false;
let recognition = null;
let isListening = false;


// ==========================================
// SEND MESSAGE
// ==========================================

async function sendMessage() {

    const input = document.getElementById("user-input");
    const chatBox = document.getElementById("chat-box");
    const sendButton = document.getElementById("send-btn");

    const message = input.value.trim();

    if (message === "" || isGenerating) {
        return;
    }

    currentController = new AbortController();

    isGenerating = true;

    // Show user message
    chatBox.innerHTML += `
        <div class="message-row user-row">
            <div class="user-message">
                <span class="avatar">👤</span>
                <span>${escapeHTML(message)}</span>
            </div>
        </div>
    `;

    chatBox.scrollTop = chatBox.scrollHeight;

    input.value = "";

    // Change Send → Stop
    sendButton.classList.add("stop-btn");

    sendButton.innerHTML = `
        <span class="stop-icon">■</span>
    `;

    sendButton.title = "Stop generating";


    // Thinking indicator
    const thinkingMessage = document.createElement("div");

    thinkingMessage.className =
        "message-row bot-row thinking-container";

    thinkingMessage.innerHTML = `
        <div class="thinking-message">

            <span class="avatar">🤖</span>

            <span>Thinking</span>

            <div class="thinking-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>

        </div>
    `;

    chatBox.appendChild(thinkingMessage);

    chatBox.scrollTop = chatBox.scrollHeight;


    try {

        const response = await fetch("/chat", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                message: message
            }),

            signal: currentController.signal

        });


        if (!response.ok) {
            throw new Error(
                "Server error: " + response.status
            );
        }


        thinkingMessage.remove();


        // AI message container
        const botMessage =
            document.createElement("div");

        botMessage.className =
            "message-row bot-row";

        botMessage.innerHTML = `
            <div class="bot-message">

                <span class="avatar">🤖</span>

                <span class="bot-text"></span>

            </div>
        `;

        chatBox.appendChild(botMessage);


        const botText =
            botMessage.querySelector(".bot-text");


        // Read stream
        const reader =
            response.body.getReader();

        const decoder =
            new TextDecoder();

        let fullText = "";


        while (true) {

            const {
                value,
                done
            } = await reader.read();


            if (done) {
                break;
            }


            const text =
                decoder.decode(value, {
                    stream: true
                });


            fullText += text;


            botText.innerHTML =
                formatMessage(fullText);


            chatBox.scrollTop =
                chatBox.scrollHeight;
        }


    } catch (error) {

        if (error.name === "AbortError") {
            console.log("Generation stopped.");
            return;
        }


        console.error(error);


        thinkingMessage.remove();


        chatBox.innerHTML += `
            <div class="message-row bot-row">

                <div class="bot-message">

                    <span class="avatar">🤖</span>

                    <span>
                        Sorry, I couldn't connect
                        to the AI.
                    </span>

                </div>

            </div>
        `;


    } finally {

        isGenerating = false;

        currentController = null;

        sendButton.classList.remove("stop-btn");

        sendButton.innerHTML = "➤";

        sendButton.title = "Send";

        input.focus();
    }
}


// ==========================================
// STOP GENERATING
// ==========================================

function stopGenerating() {

    if (currentController && isGenerating) {

        currentController.abort();

        currentController = null;

        isGenerating = false;

        const sendButton =
            document.getElementById("send-btn");

        sendButton.classList.remove("stop-btn");

        sendButton.innerHTML = "➤";

        sendButton.title = "Send";
    }
}


// ==========================================
// VOICE INPUT
// ==========================================

function setupVoiceRecognition() {

    const voiceButton =
        document.getElementById("voice-btn");

    const input =
        document.getElementById("user-input");


    if (!voiceButton) {
        return;
    }


    const SpeechRecognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;


    if (!SpeechRecognition) {

        voiceButton.disabled = true;

        voiceButton.title =
            "Voice input is not supported by this browser";

        return;
    }


    recognition =
        new SpeechRecognition();


    recognition.continuous = false;

    recognition.interimResults = true;

    recognition.lang = "en-IN";


    recognition.onstart = function () {

        isListening = true;

        voiceButton.classList.add("listening");

        voiceButton.innerHTML = "🔴";

        voiceButton.title = "Listening...";
    };


    recognition.onresult = function (event) {

        let transcript = "";

        for (
            let i = event.resultIndex;
            i < event.results.length;
            i++
        ) {

            transcript +=
                event.results[i][0].transcript;
        }


        input.value = transcript;
    };


    recognition.onerror = function (event) {

        console.error(
            "Voice error:",
            event.error
        );
    };


    recognition.onend = function () {

        isListening = false;

        voiceButton.classList.remove(
            "listening"
        );

        voiceButton.innerHTML = "🎤";

        voiceButton.title = "Voice";
    };


    voiceButton.addEventListener(
        "click",
        function () {

            if (isListening) {

                recognition.stop();

            } else {

                recognition.start();

            }

        }
    );
}


// ==========================================
// BUTTONS + ENTER KEY
// ==========================================

document.addEventListener(
    "DOMContentLoaded",
    function () {

        const input =
            document.getElementById("user-input");

        const sendButton =
            document.getElementById("send-btn");


        // Send / Stop
        sendButton.addEventListener(
            "click",
            function () {

                if (isGenerating) {

                    stopGenerating();

                } else {

                    sendMessage();

                }

            }
        );


        // Enter
        input.addEventListener(
            "keydown",
            function (event) {

                if (
                    event.key === "Enter" &&
                    !event.shiftKey
                ) {

                    event.preventDefault();

                    if (!isGenerating) {
                        sendMessage();
                    }

                }

            }
        );


        // Voice
        setupVoiceRecognition();

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
// FORMAT MESSAGE
// ==========================================

function formatMessage(text) {

    return escapeHTML(text)
        .replace(/\n/g, "<br>");
}