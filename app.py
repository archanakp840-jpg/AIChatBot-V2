from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    jsonify,
    Response,
    stream_with_context,
)

import os
import re
import secrets
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
    delete_memory,
)

from chatbot.auth import register_user, login_user
from chatbot.intents import detect_intent, generate_response


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)
# Set FLASK_SECRET_KEY in your environment for a stable key across restarts.
# The generated fallback is convenient for local testing only.
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)

create_tables()


# ============================================================
# OLLAMA SETTINGS
# ============================================================

MODEL_NAME = "llama3.2"
MAX_HISTORY_MESSAGES = 12
MAX_RESPONSE_TOKENS = 300
CONTEXT_SIZE = 4096
OLLAMA_KEEP_ALIVE = "10m"


# ============================================================
# MEMORY SETTINGS
# ============================================================

MAX_MEMORIES = 30
MAX_MEMORY_LENGTH = 300
MAX_MEMORIES_PER_MESSAGE = 5


# ============================================================
# MEMORY VALIDATION
# ============================================================

def is_memory_supported(memory, user_message):
    """Heuristically check that a candidate memory is supported by the user's message."""
    message = user_message.strip().lower().replace("’", "'")
    candidate = memory.strip().lower().replace("’", "'")
    message = re.sub(r"\s+", " ", message)
    candidate = re.sub(r"\s+", " ", candidate)

    # Do not turn questions into personal facts.
    if "?" in message:
        return False

    request_starts = (
        "can you ", "could you ", "would you ", "will you ", "please ",
        "teach me ", "tell me ", "help me ", "show me ", "i want to know ",
        "what is ", "what are ", "what jobs ", "how do i ", "how can i ",
        "should i ", "maybe i should ", "is it ", "are there ", "do you ",
        "does anyone ",
    )
    if message.startswith(request_starts):
        return False

    # Specific patterns must precede the generic "I am" patterns.
    patterns = [
        (r"\bi am learning (.+)", r"the user is learning \1"),
        (r"\bi'm learning (.+)", r"the user is learning \1"),
        (r"\bi am studying (.+)", r"the user is studying \1"),
        (r"\bi'm studying (.+)", r"the user is studying \1"),
        (r"\bi live in (.+)", r"the user lives in \1"),
        (r"\bi like (.+)", r"the user likes \1"),
        (r"\bi love (.+)", r"the user loves \1"),
        (r"\bi enjoy (.+)", r"the user enjoys \1"),
        (r"\bi prefer (.+)", r"the user prefers \1"),
        (r"\bi have (.+)", r"the user has \1"),
        (r"\bi use (.+)", r"the user uses \1"),
        (r"\bi work as (.+)", r"the user works as \1"),
        (r"\bi work at (.+)", r"the user works at \1"),
        (r"\bi study (.+)", r"the user studies \1"),
        (r"\bi am interested in (.+)", r"the user is interested in \1"),
        (r"\bi'm interested in (.+)", r"the user is interested in \1"),
        (r"\bi want to become (.+)", r"the user wants to become \1"),
        (r"\bi want to be (.+)", r"the user wants to be \1"),
        (r"\bi want to learn (.+)", r"the user wants to learn \1"),
        (r"\bmy name is (.+)", r"the user's name is \1"),
        (r"\bmy goal is to (.+)", r"the user's goal is to \1"),
        (r"\bmy goal is (.+)", r"the user's goal is \1"),
        (r"\bmy favorite (.+) is (.+)", r"the user's favorite \1 is \2"),
        (r"\bmy favourite (.+) is (.+)", r"the user's favourite \1 is \2"),
        (r"\bi am (.+)", r"the user is \1"),
        (r"\bi'm (.+)", r"the user is \1"),
    ]

    candidate = candidate.strip(" \t\r\n.!,")
    for pattern, replacement in patterns:
        if re.search(pattern, message):
            supported_memory = re.sub(
                pattern, replacement, message, count=1
            ).strip(" \t\r\n.!,")
            if candidate == supported_memory:
                return True
    return False


# ============================================================
# MEMORY-AWARE ANSWERS
# ============================================================

def answer_from_memories(user_id, user_message):
    """Answer language-learning questions from saved memories."""
    memories = get_memories(user_id)
    if not memories:
        return None

    question = re.sub(r"\s+", " ", user_message.lower().strip()).rstrip("?!. ")
    language_questions = {
        "what programming language am i learning",
        "which programming language am i learning",
        "what programming languages am i learning",
        "which programming languages am i learning",
        "what languages am i learning",
        "which languages am i learning",
        "what language am i learning",
        "which language am i learning",
    }
    if question not in language_questions:
        return None

    languages = []
    for memory in memories:
        text = str(memory[1]).strip()
        match = re.fullmatch(
            r"the user is learning\s+(.+?)[.!]?", text, re.IGNORECASE
        )
        if not match:
            continue
        language = match.group(1).strip(" \t\r\n.,!?")
        if not language or len(language) > 40:
            continue
        if language.casefold() not in {item.casefold() for item in languages}:
            languages.append(language)

    if languages:
        return "According to my saved memories, you are learning " + " and ".join(languages) + "."
    return "I don't have a saved memory confirming which programming languages you are learning."


def format_memory(memory):
    """Convert stored third-person memory wording into natural wording."""
    text = str(memory).strip()
    replacements = [
        ("The user's name is ", "Your name is "),
        ("The user's goal is ", "Your goal is "),
        ("The user's favourite ", "Your favourite "),
        ("The user's favorite ", "Your favorite "),
        ("The user is learning ", "You are learning "),
        ("The user is studying ", "You are studying "),
        ("The user is interested in ", "You are interested in "),
        ("The user lives in ", "You live in "),
        ("The user likes ", "You like "),
        ("The user loves ", "You love "),
        ("The user enjoys ", "You enjoy "),
        ("The user prefers ", "You prefer "),
        ("The user has ", "You have "),
        ("The user uses ", "You use "),
        ("The user works as ", "You work as "),
        ("The user works at ", "You work at "),
        ("The user studies ", "You study "),
        ("The user wants to become ", "You want to become "),
        ("The user wants to be ", "You want to be "),
        ("The user wants to learn ", "You want to learn "),
    ]
    for old, new in replacements:
        if text.lower().startswith(old.lower()):
            return new + text[len(old):]
    return text


# ============================================================
# MEMORY EXTRACTION
# ============================================================

def extract_memories(user_id, user_message):
    """Ask Ollama for candidate facts, then validate before saving."""
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": """
Extract possible long-term personal facts from one user message.
Return only stable facts explicitly stated by the user about themselves.
Never guess or infer. Questions, requests, hypothetical statements,
suggestions, and facts about other people are not memories.
Do not extract passwords, credentials, secrets, or temporary situations.
Do not invent names, interests, preferences, skills, or goals.

Examples:
User: I am learning Python.
Output: The user is learning Python.
User: Can you teach me Python?
Output: NONE
User: I live in Kochi.
Output: The user lives in Kochi.
User: Is Kochi a good place to live?
Output: NONE
User: My favorite language is Python.
Output: The user's favorite language is Python.
User: Maybe I should learn Python.
Output: NONE

Return one fact per line. If there are no suitable facts, return exactly NONE.
Do not explain your answer.
""",
                },
                {"role": "user", "content": user_message},
            ],
            stream=False,
            keep_alive=OLLAMA_KEEP_ALIVE,
            options={"num_predict": 150, "num_ctx": 2048, "temperature": 0},
        )
        result = response.get("message", {}).get("content", "").strip()
        if not result or result.upper() == "NONE":
            return

        invalid_phrases = {
            "none", "blue", "programming skills:", "user's name:", "name:",
            "work-life balance preferences", "flexible work schedule",
            "learning programming languages", "blue colour preference",
            "blue color preference",
        }
        existing_texts = {
            str(memory[1]).strip().lower() for memory in get_memories(user_id)
        }
        saved_count = 0

        for line in result.splitlines():
            memory = line.strip().lstrip("-•* \t")
            memory = re.sub(r"^\d+[.)]\s*", "", memory).strip()
            if not memory or len(memory) > MAX_MEMORY_LENGTH:
                continue
            if memory.lower() in invalid_phrases:
                continue
            if memory.upper() == "NONE" or memory.endswith(":"):
                continue

            lower_memory = memory.lower()
            if not lower_memory.startswith(("the user ", "the user's ")):
                print("MEMORY REJECTED (invalid format):", memory)
                continue
            if not is_memory_supported(memory, user_message):
                print("MEMORY REJECTED (not directly supported):", memory)
                continue
            if lower_memory in existing_texts:
                continue

            current_memories = get_memories(user_id)
            if len(current_memories) >= MAX_MEMORIES:
                oldest = current_memories[-1]  # assumes newest-first ordering
                delete_memory(oldest[0], user_id)

            save_memory(user_id, memory)
            existing_texts.add(lower_memory)
            saved_count += 1
            print("MEMORY SAVED:", memory)
            if saved_count >= MAX_MEMORIES_PER_MESSAGE:
                break
    except Exception as e:
        print("MEMORY EXTRACTION ERROR:", repr(e))


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
        chat_ids = {chat[0] for chat in chats}
        if conversation_id in chat_ids:
            messages = get_messages(conversation_id)
        else:
            conversation_id = None
            session.pop("conversation_id", None)

    if not conversation_id:
        if chats:
            conversation_id = chats[0][0]
            session["conversation_id"] = conversation_id
            messages = get_messages(conversation_id)
        else:
            conversation_id = create_conversation(user_id, "New Chat")
            session["conversation_id"] = conversation_id
            chats = get_conversations(user_id)

    return render_template("index.html", chats=chats, messages=messages)


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = login_user(username, password)
        if user:
            session.clear()
            session["user"] = user[0]
            session["username"] = user[1]
            chats = get_conversations(user[0])
            if chats:
                session["conversation_id"] = chats[0][0]
            else:
                session["conversation_id"] = create_conversation(user[0], "New Chat")
            return redirect("/")
        return "Invalid username or password"
    return render_template("login.html")


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            return "Username and password are required"
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
    conversation_id = create_conversation(session["user"], "New Chat")
    session["conversation_id"] = conversation_id
    return redirect("/")


# ============================================================
# CHAT
# ============================================================

@app.route("/chat", methods=["POST"])
def chat():
    if "user" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data received"}), 400

    user_message = data.get("message", "")
    if not isinstance(user_message, str):
        return jsonify({"error": "Message must be text"}), 400
    user_message = user_message.strip()
    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    user_id = session["user"]
    conversation_id = session.get("conversation_id")
    if not conversation_id:
        conversation_id = create_conversation(user_id, "New Chat")
        session["conversation_id"] = conversation_id

    chats = get_conversations(user_id)
    chat_ids = {chat_item[0] for chat_item in chats}
    if conversation_id not in chat_ids:
        conversation_id = create_conversation(user_id, "New Chat")
        session["conversation_id"] = conversation_id

    save_message(conversation_id, "user", user_message)

    intent = detect_intent(user_message)
    print("Detected intent:", intent)

    memory_answer = answer_from_memories(user_id, user_message)
    if memory_answer:
        save_message(conversation_id, "assistant", memory_answer)
        return Response(memory_answer, mimetype="text/plain")

    if intent == "memory_question":
        memories = get_memories(user_id)
        if memories:
            memory_lines = [f"- {format_memory(memory[1])}" for memory in memories]
            response_text = (
                "Here is what you have explicitly told me and what I currently remember:\n\n"
                + "\n".join(memory_lines)
            )
        else:
            response_text = (
                "I don't have any saved memories about you yet. "
                "I won't guess personal information that you haven't explicitly shared."
            )
        save_message(conversation_id, "assistant", response_text)
        return Response(response_text, mimetype="text/plain")

    if intent != "fallback":
        response_text = generate_response(intent)
        if response_text:
            save_message(conversation_id, "assistant", response_text)
            return Response(response_text, mimetype="text/plain")

    extract_memories(user_id, user_message)

    title = get_conversation_title(conversation_id)
    if title == "New Chat":
        update_conversation_title(conversation_id, user_message[:40])

    history = get_messages(conversation_id)[-MAX_HISTORY_MESSAGES:]
    memories = get_memories(user_id)

    system_prompt = """
You are a helpful AI assistant.

You have access to the current conversation and long-term user memories.
Memories are intended to contain facts explicitly stated by the user,
but may contain errors. Do not blindly trust them if the current chat
contradicts them.

STRICT USER KNOWLEDGE RULES:
1. Only state information supported by the provided memory or current chat.
2. Never guess personal details or infer facts from questions.
3. Do not infer personality, interests, job, education, location, age,
   relationships, hobbies, preferences, goals, or abilities.
4. Asking "What jobs would suit me?" does not mean the user wants to
   become a software developer.
5. "Can you teach me Python?" does not mean the user knows Python.
6. Asking about travelling to Kochi does not mean the user lives there.
7. Learning one programming language does not mean the user stopped learning another.
8. Keep compatible memories together. If notes say Java and Python, report both.
9. Do not replace an older fact because a newer message mentions another
   compatible fact. Update a fact only when the user clearly corrects it.
10. If asked what you know about the user, list only supported facts.
11. If you do not know something, say so.
12. Never claim to remember something unless it is in the context.

Use memories only when relevant. Do not infer additional facts from them.
Be honest, helpful, natural, and conversational.
Do not mention the internal memory system unless asked.
"""

    if memories:
        memory_text = "\n".join(f"- {memory[1]}" for memory in memories)
        system_prompt += (
            "\n\nLONG-TERM USER MEMORY\n"
            "Compatible notes can both be true. Do not treat one as replacing "
            "another unless the user clearly corrects it:\n"
            + memory_text
        )

    ollama_messages = [{"role": "system", "content": system_prompt}]
    for role, content in history:
        ollama_messages.append({"role": role, "content": content})

    def generate():
        full_reply = ""
        try:
            print("\n===================================")
            print("OLLAMA REQUEST")
            print("Model:", MODEL_NAME)
            print("Conversation:", conversation_id)
            print("History:", len(history))
            print("Long-term memories:", len(memories))
            print("===================================")

            stream = ollama.chat(
                model=MODEL_NAME,
                messages=ollama_messages,
                stream=True,
                keep_alive=OLLAMA_KEEP_ALIVE,
                options={
                    "num_predict": MAX_RESPONSE_TOKENS,
                    "num_ctx": CONTEXT_SIZE,
                    "temperature": 0.7,
                },
            )
            for chunk in stream:
                text = chunk.get("message", {}).get("content", "")
                if text:
                    full_reply += text
                    yield text

            if full_reply:
                save_message(conversation_id, "assistant", full_reply)
                print("AI response saved.")
            print("Generation finished.")

        except Exception as e:
            print("OLLAMA ERROR:", repr(e))
            yield "\n[Error connecting to Ollama. Check that Ollama is running and the model is installed.]"

    return Response(
        stream_with_context(generate()),
        mimetype="text/plain",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ============================================================
# OPEN CONVERSATION
# ============================================================

@app.route("/conversation/<int:id>")
def conversation(id):
    if "user" not in session:
        return redirect("/login")
    user_id = session["user"]
    chats = get_conversations(user_id)
    chat_ids = {chat_item[0] for chat_item in chats}
    if id not in chat_ids:
        return redirect("/")
    messages = get_messages(id)
    session["conversation_id"] = id
    return render_template("index.html", chats=chats, messages=messages)


# ============================================================
# DELETE CHAT
# ============================================================

@app.route("/delete_chat/<int:id>")
def delete_chat(id):
    if "user" not in session:
        return redirect("/login")
    user_id = session["user"]
    chats = get_conversations(user_id)
    chat_ids = {chat_item[0] for chat_item in chats}
    if id in chat_ids:
        delete_conversation(id)

    if session.get("conversation_id") == id:
        remaining_chats = get_conversations(user_id)
        if remaining_chats:
            session["conversation_id"] = remaining_chats[0][0]
        else:
            session["conversation_id"] = create_conversation(user_id, "New Chat")
    return redirect("/")


# ============================================================
# MEMORY API
# ============================================================

@app.route("/memories")
def memories():
    if "user" not in session:
        return jsonify({"error": "Not logged in"}), 401
    user_memories = get_memories(session["user"])
    return jsonify([
        {"id": memory[0], "memory": memory[1]}
        for memory in user_memories
    ])


# ============================================================
# DELETE MEMORY
# ============================================================

@app.route("/delete_memory/<int:id>", methods=["POST", "DELETE"])
def remove_memory(id):
    if "user" not in session:
        return jsonify({"error": "Not logged in"}), 401
    delete_memory(id, session["user"])
    return jsonify({"success": True})


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
    app.run(debug=True, threaded=True, host="127.0.0.1", port=5000)
