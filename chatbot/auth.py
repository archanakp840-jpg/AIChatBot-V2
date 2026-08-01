from werkzeug.security import generate_password_hash, check_password_hash

from chatbot.database import create_user, get_user


def register_user(username, password):
    hashed = generate_password_hash(password)

    try:
        create_user(username, hashed)
        return True
    except:
        return False


def login_user(username, password):
    user = get_user(username)

    if not user:
        return None

    if check_password_hash(user[2], password):
        return user

    return None