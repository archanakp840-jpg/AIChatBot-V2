from flask import Flask, render_template, request, redirect, session, jsonify

import ollama

from chatbot.database import (
    create_tables,
    create_conversation,
    get_conversations,
    save_message,
    get_messages
)

from chatbot.auth import register_user, login_user


app = Flask(__name__)

app.secret_key = "change_this_to_a_secure_secret_key"


create_tables()



@app.route("/")
def home():

    if "user" in session:

        chats = get_conversations(session["user"])

        return render_template(
            "index.html",
            chats=chats
        )

    return redirect("/login")



@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        user = login_user(username, password)


        if user:

            session["user"] = user[0]
            session["username"] = user[1]

            # create first chat
            session["conversation_id"] = create_conversation(
                user[0],
                "New Chat"
            )

            return redirect("/")


        return "Invalid username or password"


    return render_template("login.html")



@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]


        if register_user(username, password):

            return redirect("/login")


        return "Username already exists"


    return render_template("register.html")



@app.route("/new_chat")
def new_chat():

    if "user" in session:

        session["conversation_id"] = create_conversation(
            session["user"],
            "New Chat"
        )

    return redirect("/")



@app.route("/chat", methods=["POST"])
def chat():

    data = request.json

    user_message = data.get("message")


    conversation_id = session.get("conversation_id")


    if not conversation_id:

        conversation_id = create_conversation(
            session["user"],
            "New Chat"
        )

        session["conversation_id"] = conversation_id



    # save user message
    save_message(
        conversation_id,
        "user",
        user_message
    )


    response = ollama.chat(

        model="llama3.2",

        messages=[
            {
                "role":"user",
                "content":user_message
            }
        ]
    )


    reply = response["message"]["content"]



    # save AI response
    save_message(
        conversation_id,
        "assistant",
        reply
    )


    return jsonify({

        "reply":reply

    })

@app.route("/conversation/<int:id>")
def conversation(id):

    if "user" not in session:
        return redirect("/login")


    chats = get_conversations(session["user"])

    messages = get_messages(id)


    session["conversation_id"] = id


    return render_template(
        "index.html",
        chats=chats,
        messages=messages
    )



@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")



if __name__ == "__main__":

    app.run(debug=True)