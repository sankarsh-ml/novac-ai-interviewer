import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
CREDENTIAL_FILE = BASE_DIR / "storage" / "admin_credentials.json"


def authenticate(username: str, password: str):
    with open(CREDENTIAL_FILE, "r") as f:
        data = json.load(f)

    for admin in data.get("admins", []):
        if (
            admin["username"] == username
            and admin["password"] == password
        ):
            return True

    return False