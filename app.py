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
    delete_conversation,
    save_memory,
    get_memories,
    delete_memory
)

from chatbot.auth import (
    register_user,
    login_user
)


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

# IMPORTANT:
# Change this to a long random secret before deploying.
app.secret_key = "change_this_to_a_secure_secret_key"

# Create database tables
create_tables()


# ============================================================
# OLLAMA SETTINGS
# ============================================================

MODEL_NAME = "llama3.2"

# Number of recent messages from current conversation
MAX_HISTORY_MESSAGES = 12

# Maximum generated response tokens
MAX_RESPONSE_TOKENS = 300

# Ollama context size
CONTEXT_SIZE = 4096

# Keep model loaded
OLLAMA_KEEP_ALIVE = "10m"


# ============================================================
# MEMORY SETTINGS
# ============================================================

# Maximum long-term memories for one user
MAX_MEMORIES = 30

# Maximum characters allowed for one memory
MAX_MEMORY_LENGTH = 300


# ============================================================
# MEMORY EXTRACTION
# ============================================================

def extract_memories(user_id, user_message):
    """
    Ask Ollama to identify ONLY stable information
    explicitly stated by the user.

    IMPORTANT:
    This function must NEVER infer or guess user facts.
    """

    try:

        response = ollama.chat(

            model=MODEL_NAME,

            messages=[
                {
                    "role": "system",

                    "content": """
You are a strict long-term memory extraction system.

Your job is ONLY to extract facts that the user explicitly
states about themselves.

IMPORTANT RULES:

1. NEVER infer or guess anything.

2. NEVER create a fact from context.

3. NEVER assume something is true because it seems likely.

4. NEVER save information about the user that they did not
   explicitly state.

5. Save only stable information that the user directly stated.

6. Do not save information about other people unless the user
   explicitly says it is about themselves.

7. Do not save temporary questions or hypothetical statements.

8. Do not save passwords, API keys, private credentials,
   authentication codes, or secrets.

9. Do not save temporary emotions or temporary situations.

10. If you are unsure whether something is explicitly stated,
    DO NOT save it.

11. A question is NOT a fact.

12. A request is NOT a fact.

13. A possibility is NOT a fact.

14. A suggestion is NOT a fact.

15. A hypothetical statement is NOT a fact.

16. Information mentioned by the assistant is NOT a fact about
    the user unless the user explicitly confirms it.

Examples:

User:
"I am learning Python."

Save:
"The user is learning Python."

User:
"Can you teach me Python?"

Save:
NONE

User:
"I like building AI projects."

Save:
"The user likes building AI projects."

User:
"What jobs would suit someone who knows Python?"

Save:
NONE

User:
"I want to become a software developer."

Save:
"The user's goal is to become a software developer."

User:
"Maybe I should become a software developer."

Save:
NONE

User:
"I live in Kochi."

Save:
"The user lives in Kochi."

User:
"Is Kochi a good place for software developers?"

Save:
NONE

User:
"My favorite programming language is Python."

Save:
"The user's favorite programming language is Python."

User:
"What is the best programming language?"

Save:
NONE

User:
"I have a project called AIChatBot."

Save:
"The user has a project called AIChatBot."

User:
"Can you suggest an AI chatbot project?"

Save:
NONE

User:
"I studied computer science."

Save:
"The user studied computer science."

User:
"What can I do with a computer science degree?"

Save:
NONE

Return each valid memory on a separate line.

If there is no explicit, stable user fact, return exactly:

NONE

Do not explain your answer.
"""
                },

                {
                    "role": "user",
                    "content": user_message
                }
            ],

            stream=False,

            keep_alive=OLLAMA_KEEP_ALIVE,

            options={
                "num_predict": 150,
                "num_ctx": 2048,
                "temperature": 0
            }
        )

        # ----------------------------------------------------
        # Get result
        # ----------------------------------------------------

        result = (
            response
            .get("message", {})
            .get("content", "")
            .strip()
        )

        if not result:
            return

        # ----------------------------------------------------
        # No memory
        # ----------------------------------------------------

        if result.upper() == "NONE":
            return

        # ----------------------------------------------------
        # Existing memories
        # ----------------------------------------------------

        existing_memories = get_memories(user_id)

        existing_texts = {
            memory[1].strip().lower()
            for memory in existing_memories
        }

        # ----------------------------------------------------
        # Process extracted memories
        # ----------------------------------------------------

        for memory in result.splitlines():

            memory = memory.strip()

            # Remove bullets
            memory = memory.lstrip("-•* ")

            # Remove simple numbering
            if memory[:2].rstrip(".").isdigit():
                memory = memory[2:].strip()

            if not memory:
                continue

            # ------------------------------------------------
            # Safety check
            # ------------------------------------------------

            upper_memory = memory.upper()

            if upper_memory == "NONE":
                continue

            # ------------------------------------------------
            # Limit length
            # ------------------------------------------------

            memory = memory[:MAX_MEMORY_LENGTH]

            if len(memory) < 3:
                continue

            # ------------------------------------------------
            # Duplicate check
            # ------------------------------------------------

            if memory.lower() in existing_texts:
                continue

            # ------------------------------------------------
            # Memory limit
            # ------------------------------------------------

            current_memories = get_memories(user_id)

            if len(current_memories) >= MAX_MEMORIES:

                # Memories are newest first.
                # Last item = oldest.
                oldest = current_memories[-1]

                delete_memory(
                    oldest[0],
                    user_id
                )

            # ------------------------------------------------
            # Save
            # ------------------------------------------------

            save_memory(
                user_id,
                memory
            )

            existing_texts.add(
                memory.lower()
            )

            print()
            print("===================================")
            print("MEMORY SAVED")
            print(memory)
            print("===================================")
            print()

    except Exception as e:

        # Memory extraction must NEVER
        # break the actual chatbot.

        print()
        print("===================================")
        print("MEMORY EXTRACTION ERROR")
        print("===================================")
        print(repr(e))
        print("===================================")
        print()


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    # --------------------------------------------------------
    # Login check
    # --------------------------------------------------------

    if "user" not in session:
        return redirect("/login")

    user_id = session["user"]

    # --------------------------------------------------------
    # Get user's conversations
    # --------------------------------------------------------

    chats = get_conversations(user_id)

    # --------------------------------------------------------
    # Get active conversation
    # --------------------------------------------------------

    conversation_id = session.get(
        "conversation_id"
    )

    messages = []

    # --------------------------------------------------------
    # Verify active conversation ownership
    # --------------------------------------------------------

    if conversation_id:

        chat_ids = {
            chat[0]
            for chat in chats
        }

        if conversation_id in chat_ids:

            messages = get_messages(
                conversation_id
            )

        else:

            conversation_id = None

            session.pop(
                "conversation_id",
                None
            )

    # --------------------------------------------------------
    # No active conversation
    # --------------------------------------------------------

    if not conversation_id:

        if chats:

            # Open latest conversation
            conversation_id = chats[0][0]

            session["conversation_id"] = (
                conversation_id
            )

            messages = get_messages(
                conversation_id
            )

        else:

            # Create first conversation
            conversation_id = create_conversation(
                user_id,
                "New Chat"
            )

            session["conversation_id"] = (
                conversation_id
            )

            chats = get_conversations(
                user_id
            )

    # --------------------------------------------------------
    # Render
    # --------------------------------------------------------

    return render_template(
        "index.html",
        chats=chats,
        messages=messages
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        # ----------------------------------------------------
        # Login
        # ----------------------------------------------------

        user = login_user(
            username,
            password
        )

        if user:

            # Clear old session
            session.clear()

            session["user"] = user[0]
            session["username"] = user[1]

            # ------------------------------------------------
            # Get previous conversations
            # ------------------------------------------------

            chats = get_conversations(
                user[0]
            )

            if chats:

                # Open latest conversation
                session["conversation_id"] = (
                    chats[0][0]
                )

            else:

                # Create first conversation
                session["conversation_id"] = (
                    create_conversation(
                        user[0],
                        "New Chat"
                    )
                )

            return redirect("/")

        return "Invalid username or password"

    return render_template(
        "login.html"
    )


# ============================================================
# REGISTER
# ============================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if not username or not password:

            return (
                "Username and password are required"
            )

        if register_user(
            username,
            password
        ):

            return redirect("/login")

        return "Username already exists"

    return render_template(
        "register.html"
    )


# ============================================================
# NEW CHAT
# ============================================================

@app.route("/new_chat")
def new_chat():

    if "user" not in session:
        return redirect("/login")

    user_id = session["user"]

    conversation_id = create_conversation(
        user_id,
        "New Chat"
    )

    session["conversation_id"] = (
        conversation_id
    )

    return redirect("/")


# ============================================================
# CHAT
# ============================================================

@app.route(
    "/chat",
    methods=["POST"]
)
def chat():

    # --------------------------------------------------------
    # Login check
    # --------------------------------------------------------

    if "user" not in session:

        return jsonify({
            "error": "Not logged in"
        }), 401

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "error": "No data received"
        }), 400

    # --------------------------------------------------------
    # User message
    # --------------------------------------------------------

    user_message = data.get(
        "message",
        ""
    ).strip()

    if not user_message:

        return jsonify({
            "error": "Empty message"
        }), 400

    # --------------------------------------------------------
    # Current user
    # --------------------------------------------------------

    user_id = session["user"]

    # --------------------------------------------------------
    # Current conversation
    # --------------------------------------------------------

    conversation_id = session.get(
        "conversation_id"
    )

    # --------------------------------------------------------
    # Create conversation if necessary
    # --------------------------------------------------------

    if not conversation_id:

        conversation_id = create_conversation(
            user_id,
            "New Chat"
        )

        session["conversation_id"] = (
            conversation_id
        )

    # --------------------------------------------------------
    # Verify conversation ownership
    # --------------------------------------------------------

    chats = get_conversations(
        user_id
    )

    chat_ids = {
        chat[0]
        for chat in chats
    }

    if conversation_id not in chat_ids:

        conversation_id = create_conversation(
            user_id,
            "New Chat"
        )

        session["conversation_id"] = (
            conversation_id
        )

    # --------------------------------------------------------
    # Save user message
    # --------------------------------------------------------

    save_message(
        conversation_id,
        "user",
        user_message
    )

    # --------------------------------------------------------
    # Extract long-term memories
    #
    # IMPORTANT:
    # The extractor ONLY receives the user's message.
    # It does not receive previous assistant answers.
    #
    # This helps prevent assistant-generated assumptions
    # from becoming memories.
    # --------------------------------------------------------

    extract_memories(
        user_id,
        user_message
    )

    # --------------------------------------------------------
    # Automatically rename new chat
    # --------------------------------------------------------

    title = get_conversation_title(
        conversation_id
    )

    if title == "New Chat":

        new_title = (
            user_message
            .strip()
            [:40]
        )

        update_conversation_title(
            conversation_id,
            new_title
        )

    # --------------------------------------------------------
    # Get current conversation history
    # --------------------------------------------------------

    history = get_messages(
        conversation_id
    )

    # --------------------------------------------------------
    # Keep recent history
    # --------------------------------------------------------

    history = history[
        -MAX_HISTORY_MESSAGES:
    ]

    # --------------------------------------------------------
    # Get long-term memories
    # --------------------------------------------------------

    memories = get_memories(
        user_id
    )

    # ========================================================
    # BUILD OLLAMA MESSAGES
    # ========================================================

    ollama_messages = []

    # --------------------------------------------------------
    # Main system prompt
    # --------------------------------------------------------

    system_prompt = """
You are a helpful AI assistant.

You have access to two types of context:

1. CURRENT CONVERSATION
   This is the conversation the user is currently in.

2. LONG-TERM USER MEMORY
   These are explicit facts that the user previously
   stated about themselves.

==================================================
STRICT USER KNOWLEDGE RULES
==================================================

When answering questions about the user:

1. ONLY state information that is explicitly supported
   by the LONG-TERM USER MEMORY or CURRENT CONVERSATION.

2. NEVER guess information about the user.

3. NEVER infer personality traits from their questions.

4. NEVER infer their interests from the topics they ask about.

5. NEVER infer their job, education, location, age,
   relationships, hobbies, preferences, goals, or abilities.

6. NEVER turn a question into a personal fact.

Examples:

User:
"What jobs would suit me?"

This does NOT mean:
"The user wants to become a software developer."

User:
"Can you teach me Python?"

This does NOT mean:
"The user knows Python."

User:
"Tell me about travelling to Kochi."

This does NOT mean:
"The user lives in Kochi."

User:
"What do you think I am interested in?"

This does NOT mean that any guessed interest is a fact.

7. If the user asks:

   "What do you know about me?"

   Give ONLY facts that are explicitly supported by
   the LONG-TERM USER MEMORY or CURRENT CONVERSATION.

8. If there is not enough information, say:

   "I don't know that yet."

   Do not fill the gap with guesses.

9. Clearly distinguish between:

   - what the user explicitly told you
   - what you do not know

10. Never present assumptions as facts.

11. Never claim that you remember something unless it is
    actually present in the provided context.

12. Never use general knowledge about the user to create
    a personal fact.

==================================================
LONG-TERM MEMORY RULES
==================================================

Long-term memory contains only information that the user
explicitly stated about themselves.

Use long-term memory when it is relevant.

Do not modify or reinterpret a memory.

Do not create new personal facts from the memories.

If a memory says:

"The user likes Python."

You may say:

"You told me that you like Python."

You may NOT conclude:

"Therefore you are a programmer."

unless the user explicitly stated that.

==================================================
CURRENT CONVERSATION RULES
==================================================

Use the current conversation naturally.

The current conversation may contain questions,
possibilities, examples, hypothetical situations,
or statements about other people.

Do not automatically treat those as facts about the user.

Only treat something as a user fact when the user
explicitly states that it applies to themselves.

==================================================
WHEN ASKED WHAT YOU KNOW
==================================================

If the user asks:

"What do you know about me?"

or:

"What do you remember about me?"

or similar questions:

1. List only explicit facts available in memory
   or the current conversation.

2. Do not add guesses.

3. Do not add personality analysis unless the user
   explicitly stated the relevant trait.

4. Do not turn previous questions into facts.

5. If there are no known facts, say so.

6. Never pretend to know more than the available context.

==================================================
HONESTY
==================================================

Accuracy is more important than appearing knowledgeable.

If you don't know something about the user, say that
you don't know.

Be helpful, natural, and conversational.

Do not mention the internal memory system unless the
user explicitly asks about it.
"""

    # --------------------------------------------------------
    # Add long-term memory
    # --------------------------------------------------------

    if memories:

        memory_text = "\n".join(
            f"- {memory[1]}"
            for memory in memories
        )

        system_prompt += (
            "\n\n"
            "==================================================\n"
            "LONG-TERM USER MEMORY\n"
            "==================================================\n"
            + memory_text
        )

    # --------------------------------------------------------
    # Add system message
    # --------------------------------------------------------

    ollama_messages.append({
        "role": "system",
        "content": system_prompt
    })

    # --------------------------------------------------------
    # Add current conversation
    # --------------------------------------------------------

    for role, content in history:

        ollama_messages.append({
            "role": role,
            "content": content
        })

    # ========================================================
    # STREAM GENERATOR
    # ========================================================

    def generate():

        full_reply = ""

        try:

            print()
            print("===================================")
            print("OLLAMA REQUEST")
            print("Model:", MODEL_NAME)
            print(
                "Conversation:",
                conversation_id
            )
            print(
                "History:",
                len(history)
            )
            print(
                "Long-term memories:",
                len(memories)
            )
            print("===================================")

            # ------------------------------------------------
            # Ollama
            # ------------------------------------------------

            stream = ollama.chat(

                model=MODEL_NAME,

                messages=ollama_messages,

                stream=True,

                keep_alive=OLLAMA_KEEP_ALIVE,

                options={

                    "num_predict":
                        MAX_RESPONSE_TOKENS,

                    "num_ctx":
                        CONTEXT_SIZE,

                    "temperature":
                        0.7
                }
            )

            print(
                "Ollama connected."
            )

            print(
                "Generating..."
            )

            # ------------------------------------------------
            # Stream response
            # ------------------------------------------------

            for chunk in stream:

                text = (
                    chunk
                    .get("message", {})
                    .get("content", "")
                )

                if text:

                    full_reply += text

                    # Send immediately
                    yield text

            # ------------------------------------------------
            # Save complete response
            # ------------------------------------------------

            if full_reply:

                save_message(
                    conversation_id,
                    "assistant",
                    full_reply
                )

                print(
                    "AI response saved."
                )

            print(
                "Generation finished."
            )

            print(
                "==================================="
            )

        except Exception as e:

            print()
            print("===================================")
            print("OLLAMA ERROR")
            print("===================================")
            print(repr(e))
            print("===================================")
            print()

            yield (
                "\n[Error connecting to Ollama]"
            )

    # --------------------------------------------------------
    # Streaming HTTP response
    # --------------------------------------------------------

    return Response(

        stream_with_context(
            generate()
        ),

        mimetype="text/plain",

        headers={

            "X-Accel-Buffering":
                "no",

            "Cache-Control":
                "no-cache",

            "Connection":
                "keep-alive"
        }
    )


# ============================================================
# OPEN CONVERSATION
# ============================================================

@app.route(
    "/conversation/<int:id>"
)
def conversation(id):

    if "user" not in session:
        return redirect("/login")

    user_id = session["user"]

    # --------------------------------------------------------
    # Get user's conversations
    # --------------------------------------------------------

    chats = get_conversations(
        user_id
    )

    chat_ids = {
        chat[0]
        for chat in chats
    }

    # --------------------------------------------------------
    # Security check
    # --------------------------------------------------------

    if id not in chat_ids:
        return redirect("/")

    # --------------------------------------------------------
    # Get messages
    # --------------------------------------------------------

    messages = get_messages(
        id
    )

    # --------------------------------------------------------
    # Set active conversation
    # --------------------------------------------------------

    session["conversation_id"] = id

    return render_template(
        "index.html",
        chats=chats,
        messages=messages
    )


# ============================================================
# DELETE CHAT
# ============================================================

@app.route(
    "/delete_chat/<int:id>"
)
def delete_chat(id):

    if "user" not in session:
        return redirect("/login")

    user_id = session["user"]

    # --------------------------------------------------------
    # Get user's conversations
    # --------------------------------------------------------

    chats = get_conversations(
        user_id
    )

    chat_ids = {
        chat[0]
        for chat in chats
    }

    # --------------------------------------------------------
    # Delete only user's conversation
    # --------------------------------------------------------

    if id in chat_ids:

        delete_conversation(
            id
        )

    # --------------------------------------------------------
    # If active chat was deleted
    # --------------------------------------------------------

    if session.get(
        "conversation_id"
    ) == id:

        remaining_chats = get_conversations(
            user_id
        )

        if remaining_chats:

            session["conversation_id"] = (
                remaining_chats[0][0]
            )

        else:

            session["conversation_id"] = (
                create_conversation(
                    user_id,
                    "New Chat"
                )
            )

    return redirect("/")


# ============================================================
# MEMORY API
# ============================================================

@app.route("/memories")
def memories():

    if "user" not in session:

        return jsonify({
            "error": "Not logged in"
        }), 401

    user_id = session["user"]

    user_memories = get_memories(
        user_id
    )

    return jsonify([
        {
            "id": memory[0],
            "memory": memory[1]
        }

        for memory in user_memories
    ])


# ============================================================
# DELETE MEMORY
# ============================================================

@app.route(
    "/delete_memory/<int:id>",
    methods=["POST", "DELETE"]
)
def remove_memory(id):

    if "user" not in session:

        return jsonify({
            "error": "Not logged in"
        }), 401

    user_id = session["user"]

    delete_memory(
        id,
        user_id
    )

    return jsonify({
        "success": True
    })


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

        threaded=True,

        host="127.0.0.1",

        port=5000
    )