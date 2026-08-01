function sendMessage(){

    let input = document.getElementById("user-input");

    let message = input.value.trim();

    if(message === ""){
        return;
    }


    let chatBox = document.getElementById("chat-box");


    // show user message
    chatBox.innerHTML += `
        <div class="user-message">
            👤 ${message}
        </div>
    `;


    fetch("/chat", {

        method: "POST",

        headers:{
            "Content-Type":"application/json"
        },

        body: JSON.stringify({
            message: message
        })

    })

    .then(response => response.json())

    .then(data => {

        chatBox.innerHTML += `
            <div class="bot-message">
                🤖 ${data.reply}
            </div>
        `;

    });


    input.value = "";

}