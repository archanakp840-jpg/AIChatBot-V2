from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    jsonify,
    Response,
    stream_with_context
)

import ollama

from chatbot.database import (
    create_tables,
    create_conversation,
    get_conversations,
    save_message,
    get_messages,
    get_conversation_title,
    update_conversation_title,
    delete_conversation
)

from chatbot.auth import register_user, login_user


app = Flask(__name__)

app.secret_key = "change_this_to_a_secure_secret_key"

create_tables()


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    if "user" not in session:
        return redirect("/login")

    user_id = session["user"]

    chats = get_conversations(user_id)

    conversation_id = session.get("conversation_id")

    messages = []

    if conversation_id:

        # Make sure the conversation belongs to this user
        chat_ids = [chat[0] for chat in chats]

        if conversation_id in chat_ids:
            messages = get_messages(conversation_id)

        else:
            conversation_id = None
            session.pop("conversation_id", None)

    # If there is no active conversation,
    # select an existing one or create a new one
    if not conversation_id:

        if chats:

            conversation_id = chats[0][0]
            session["conversation_id"] = conversation_id

            messages = get_messages(conversation_id)

        else:

            conversation_id = create_conversation(
                user_id,
                "New Chat"
            )

            session["conversation_id"] = conversation_id

            chats = get_conversations(user_id)

    return render_template(
        "index.html",
        chats=chats,
        messages=messages
    )


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        user = login_user(username, password)

        if user:

            session["user"] = user[0]
            session["username"] = user[1]

            # Get existing chats
            chats = get_conversations(user[0])

            if chats:

                # Open latest chat
                session["conversation_id"] = chats[0][0]

            else:

                # Create first chat
                session["conversation_id"] = create_conversation(
                    user[0],
                    "New Chat"
                )

            return redirect("/")

        return "Invalid username or password"

    return render_template("login.html")


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        if register_user(username, password):

            return redirect("/login")

        return "Username already exists"

    return render_template("register.html")


# ============================================================
# NEW CHAT
# ============================================================

@app.route("/new_chat")
def new_chat():

    if "user" not in session:
        return redirect("/login")

    conversation_id = create_conversation(
        session["user"],
        "New Chat"
    )

    session["conversation_id"] = conversation_id

    return redirect("/")


# ============================================================
# CHAT - STREAMING RESPONSE
# ============================================================

@app.route("/chat", methods=["POST"])
def chat():

    # --------------------------------------------------------
    # Check login
    # --------------------------------------------------------

    if "user" not in session:

        return jsonify({
            "error": "Not logged in"
        }), 401


    # --------------------------------------------------------
    # Get request data
    # --------------------------------------------------------

    data = request.get_json()

    if not data:

        return jsonify({
            "error": "No data received"
        }), 400


    user_message = data.get("message", "").strip()

    if not user_message:

        return jsonify({
            "error": "Empty message"
        }), 400


    # --------------------------------------------------------
    # Get current conversation
    # --------------------------------------------------------

    conversation_id = session.get("conversation_id")


    if not conversation_id:

        conversation_id = create_conversation(
            session["user"],
            "New Chat"
        )

        session["conversation_id"] = conversation_id


    # --------------------------------------------------------
    # Make sure conversation belongs to user
    # --------------------------------------------------------

    chats = get_conversations(session["user"])

    chat_ids = [chat[0] for chat in chats]

    if conversation_id not in chat_ids:

        conversation_id = create_conversation(
            session["user"],
            "New Chat"
        )

        session["conversation_id"] = conversation_id


    # --------------------------------------------------------
    # Save user message
    # --------------------------------------------------------

    save_message(
        conversation_id,
        "user",
        user_message
    )


    # --------------------------------------------------------
    # Automatically rename "New Chat"
    # --------------------------------------------------------

    title = get_conversation_title(
        conversation_id
    )

    if title == "New Chat":

        update_conversation_title(
            conversation_id,
            user_message
        )


    # --------------------------------------------------------
    # Get conversation history
    # --------------------------------------------------------

    history = get_messages(
        conversation_id
    )


    messages = []

    for role, content in history:

        messages.append({
            "role": role,
            "content": content
        })


    # --------------------------------------------------------
    # Stream Ollama response
    # --------------------------------------------------------

    def generate():

        full_reply = ""

        try:

            print("Connecting to Ollama...")

            stream = ollama.chat(
                model="llama3.2",
                messages=messages,
                stream=True
            )

            print("Ollama connected.")

            for chunk in stream:

                text = chunk["message"]["content"]

                if text:

                    full_reply += text

                    yield text


            # ------------------------------------------------
            # Save complete AI response
            # ------------------------------------------------

            if full_reply:

                save_message(
                    conversation_id,
                    "assistant",
                    full_reply
                )

                print("AI response saved.")


        except Exception as e:

            print()
            print("==============================")
            print("OLLAMA ERROR")
            print("==============================")
            print(repr(e))
            print("==============================")
            print()

            yield "\n[Error connecting to Ollama]"


    return Response(
        stream_with_context(generate()),
        mimetype="text/plain"
    )


# ============================================================
# OPEN CONVERSATION
# ============================================================

@app.route("/conversation/<int:id>")
def conversation(id):

    if "user" not in session:
        return redirect("/login")


    # Get only this user's conversations
    chats = get_conversations(
        session["user"]
    )


    # Check ownership
    chat_ids = [chat[0] for chat in chats]

    if id not in chat_ids:

        return redirect("/")


    # Load messages
    messages = get_messages(id)


    # Set active conversation
    session["conversation_id"] = id


    return render_template(
        "index.html",
        chats=chats,
        messages=messages
    )


# ============================================================
# DELETE CHAT
# ============================================================

@app.route("/delete_chat/<int:id>")
def delete_chat(id):

    if "user" not in session:
        return redirect("/login")


    # --------------------------------------------------------
    # Get user's conversations
    # --------------------------------------------------------

    chats = get_conversations(
        session["user"]
    )


    # --------------------------------------------------------
    # Check that chat belongs to logged-in user
    # --------------------------------------------------------

    chat_ids = [chat[0] for chat in chats]


    if id in chat_ids:

        delete_conversation(id)


    # --------------------------------------------------------
    # If deleted chat was active
    # --------------------------------------------------------

    if session.get("conversation_id") == id:

        remaining_chats = get_conversations(
            session["user"]
        )


        if remaining_chats:

            # Open latest remaining chat
            session["conversation_id"] = remaining_chats[0][0]

        else:

            # Create a new empty chat
            session["conversation_id"] = create_conversation(
                session["user"],
                "New Chat"
            )


    return redirect("/")


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        threaded=True
    )