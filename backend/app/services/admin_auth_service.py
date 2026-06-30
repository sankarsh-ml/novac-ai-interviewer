from app.services.auth_service import authenticate_admin


def authenticate(username: str, password: str):
    return authenticate_admin(username, password)
