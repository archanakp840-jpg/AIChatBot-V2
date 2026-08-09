import sqlite3

DATABASE = "chatbot.db"


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_connection():
    conn = sqlite3.connect(
        DATABASE,
        timeout=10,
        check_same_thread=False
    )

    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 10000")

    return conn


# ==========================================
# CREATE TABLES
# ==========================================

def create_tables():

    conn = get_connection()
    cursor = conn.cursor()

    # Users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Conversations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT DEFAULT 'New Chat',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
        )
    """)

    # Messages
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(conversation_id)
            REFERENCES conversations(id)
            ON DELETE CASCADE
        )
    """)

    # Memories
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            memory TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


# ==========================================
# USER FUNCTIONS
# ==========================================

def create_user(username, password):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            INSERT INTO users (username, password)
            VALUES (?, ?)
            """,
            (username, password)
        )

        conn.commit()

        return True

    except sqlite3.IntegrityError:

        conn.rollback()

        return False

    finally:

        conn.close()


def get_user(username):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM users
        WHERE username = ?
        """,
        (username,)
    )

    user = cursor.fetchone()

    conn.close()

    return user


# ==========================================
# CONVERSATION FUNCTIONS
# ==========================================

def create_conversation(user_id, title="New Chat"):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            INSERT INTO conversations (
                user_id,
                title
            )
            VALUES (?, ?)
            """,
            (user_id, title)
        )

        conversation_id = cursor.lastrowid

        conn.commit()

        return conversation_id

    finally:

        conn.close()


def get_conversations(user_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, title
        FROM conversations
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (user_id,)
    )

    chats = cursor.fetchall()

    conn.close()

    return chats


def get_conversation_title(conversation_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT title
        FROM conversations
        WHERE id = ?
        """,
        (conversation_id,)
    )

    row = cursor.fetchone()

    conn.close()

    if row:
        return row[0]

    return None


def update_conversation_title(
    conversation_id,
    title
):

    conn = get_connection()
    cursor = conn.cursor()

    title = title.strip()[:40]

    cursor.execute(
        """
        UPDATE conversations
        SET title = ?
        WHERE id = ?
        """,
        (title, conversation_id)
    )

    conn.commit()
    conn.close()


# ==========================================
# MESSAGE FUNCTIONS
# ==========================================

def save_message(
    conversation_id,
    role,
    content
):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            INSERT INTO messages (
                conversation_id,
                role,
                content
            )
            VALUES (?, ?, ?)
            """,
            (
                conversation_id,
                role,
                content
            )
        )

        conn.commit()

    finally:

        conn.close()


def get_messages(conversation_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT role, content
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id
        """,
        (conversation_id,)
    )

    messages = cursor.fetchall()

    conn.close()

    return messages


# ==========================================
# DELETE CONVERSATION
# ==========================================

def delete_conversation(conversation_id):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        # Delete messages
        cursor.execute(
            """
            DELETE FROM messages
            WHERE conversation_id = ?
            """,
            (conversation_id,)
        )

        # Delete conversation
        cursor.execute(
            """
            DELETE FROM conversations
            WHERE id = ?
            """,
            (conversation_id,)
        )

        conn.commit()

    finally:

        conn.close()


# ==========================================
# MEMORY FUNCTIONS
# ==========================================

def save_memory(user_id, memory):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            INSERT INTO memories (
                user_id,
                memory
            )
            VALUES (?, ?)
            """,
            (user_id, memory)
        )

        conn.commit()

    finally:

        conn.close()


def get_memories(user_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, memory
        FROM memories
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (user_id,)
    )

    memories = cursor.fetchall()

    conn.close()

    return memories


def delete_memory(
    memory_id,
    user_id
):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            DELETE FROM memories
            WHERE id = ?
            AND user_id = ?
            """,
            (
                memory_id,
                user_id
            )
        )

        conn.commit()

    finally:

        conn.close()