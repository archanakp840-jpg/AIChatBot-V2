
import re
from datetime import datetime
from nltk.tokenize import RegexpTokenizer


# ============================================================
# NLTK TEXT PREPROCESSING
# ============================================================

tokenizer = RegexpTokenizer(r"\w+|[^\w\s]")


def preprocess_text(message):
    """
    Normalize and tokenize user input using NLTK.
    Does not require additional NLTK data downloads.
    """
    if not isinstance(message, str):
        return ""

    text = re.sub(r"\s+", " ", message.strip().lower())

    if not text:
        return ""

    tokens = tokenizer.tokenize(text)
    return " ".join(tokens)


# ============================================================
# INTENT PATTERNS
# ============================================================

INTENTS = {
    "greeting": [
        r"\bhi+\b",
        r"\bhello+\b",
        r"\bhey+\b",
        r"\bgood morning\b",
        r"\bgood afternoon\b",
        r"\bgood evening\b",
        r"\bhowdy\b",
        r"\bwhat's up\b",
        r"\bwhats up\b",
    ],

    "goodbye": [
        r"\bbye\b",
        r"\bgoodbye\b",
        r"\bsee you\b",
        r"\btalk to you later\b",
        r"\bcatch you later\b",
        r"\bsee ya\b",
    ],

    "thanks": [
        r"\bthanks\b",
        r"\bthank you\b",
        r"\bthx\b",
        r"\bappreciate it\b",
        r"\bthank you so much\b",
    ],

    "joke": [
        r"\btell me (?:a |another )?jok[ea]\b",
        r"\b(?:make me laugh|say something funny)\b",
        r"\bdo you know any jokes\b",
        r"\bshare (?:a |another )?joke\b",
        r"\b(?:can you )?tell (?:me )?(?:a )?funny joke\b",
    ],

    "bot_identity": [
        r"\bwho are you\b",
        r"\bwhat are you\b",
        r"\bwhat is your name\b",
        r"\bwho created you\b",
        r"\bwhat should i call you\b",
    ],

    "capabilities": [
        r"\bwhat can you do\b",
        r"\byour capabilities\b",
        r"\bwhat are your features\b",
        r"\bhow can you help me\b",
        r"\bwhat can you help me with\b",
    ],

    "how_are_you": [
        r"\bhow are you\b",
        r"\bhow are you doing\b",
        r"\bhow is it going\b",
        r"\bhow's it going\b",
    ],

    "help": [
        r"\bi need help\b",
        r"\bhelp me\b",
        r"\bcan you help\b",
        r"\bi need assistance\b",
        r"\bplease help\b",
    ],

    "time": [
        r"\bwhat time is it\b",
        r"\btell me the time\b",
        r"\bcurrent time\b",
        r"\btime right now\b",
    ],

    "date": [
        r"\bwhat is today's date\b",
        r"\bwhat's today's date\b",
        r"\bwhat is the date today\b",
        r"\btoday's date\b",
        r"\bwhat date is it\b",
    ],

    "learning_help": [
        r"\bcan you teach me\b",
        r"\bteach me\b",
        r"\bi want to learn\b",
        r"\bhelp me learn\b",
        r"\bhow do i learn\b",
        r"\bhow can i learn\b",
        r"\bexplain\b",
        r"\bhow does .+ work\b",
        r"\bwhat is\b",
        r"\bwhat are\b",
        r"\bhow to\b",
        r"\bgive me an example\b",
    ],

    "memory_question": [
        r"\bwhat do you remember about me\b",
        r"\bwhat do you know about me\b",
        r"\bshow my memories\b",
        r"\bmy saved memories\b",
        r"\bwhat have you remembered\b",
    ],
}


# ============================================================
# RESPONSE GENERATION
# ============================================================

def generate_response(intent):
    """
    Generate predefined responses for recognized intents.

    Returns None when the main Flask application should
    use Ollama to generate the answer.
    """

    responses = {
        "greeting": (
            "Hello! 👋 How can I help you today?"
        ),

        "goodbye": (
            "Goodbye! 👋 Feel free to come back whenever you need help."
        ),

        "thanks": (
            "You're welcome! 😊 Happy to help."
        ),

        "joke": (
            "Why do programmers prefer dark mode? "
            "Because light attracts bugs! 😄"
        ),

        "bot_identity": (
            "I'm your AI assistant, powered by a language model. "
            "I can answer questions, help with coding, explain concepts, "
            "and assist with everyday tasks."
        ),

        "capabilities": (
            "I can answer questions, help with programming, explain concepts, "
            "assist with writing, and remember selected information "
            "across conversations."
        ),

        "how_are_you": (
            "I'm doing well and ready to help! How are you?"
        ),

        "help": (
            "Of course! Tell me what you need help with, "
            "and we'll work through it together."
        ),
    }

    if intent == "time":
        current_time = datetime.now().astimezone().strftime("%I:%M %p")
        return f"The current server time is {current_time}."

    if intent == "date":
        current_date = datetime.now().astimezone().strftime("%d %B %Y")
        return f"Today's date is {current_date}."

    # Ollama handles learning questions, general questions,
    # and intents without predefined responses.
    return responses.get(intent)


# ============================================================
# INTENT DETECTION
# ============================================================

def detect_intent(message):
    """
    Detect user intent using NLTK preprocessing and regex patterns.

    Returns a recognized intent name or 'fallback'.
    """

    if not isinstance(message, str):
        return "fallback"

    text = preprocess_text(message)

    if not text:
        return "fallback"

    # Check specific intents before broad learning patterns.
    priority_order = [
        "memory_question",
        "bot_identity",
        "capabilities",
        "goodbye",
        "thanks",
        "joke",
        "how_are_you",
        "time",
        "date",
        "help",
        "greeting",
        "learning_help",
    ]

    for intent in priority_order:
        for pattern in INTENTS.get(intent, []):
            if re.search(pattern, text):
                return intent

    # The main Flask application can pass this input to Ollama.
    return "fallback"

