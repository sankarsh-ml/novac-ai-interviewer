from datetime import datetime, timezone
import os
from pathlib import Path

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError


ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(ROOT_DIR / ".env")

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "novac_3")
COLLECTION_NAME = "resume_applications"

client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
database = client[MONGODB_DB]
resume_applications = database[COLLECTION_NAME]


class MongoConnectionError(Exception):
    pass


def save_resume_application(data: dict) -> str:
    now = datetime.now(timezone.utc)
    document = {
        **data,
        "ats_status": data.get("ats_status", "pending"),
        "created_at": data.get("created_at", now),
        "updated_at": data.get("updated_at", now),
    }

    try:
        _check_mongo_connection()
        result = resume_applications.insert_one(document)
        return str(result.inserted_id)
    except (ServerSelectionTimeoutError, PyMongoError) as exc:
        raise MongoConnectionError from exc


def get_resume_application(application_id: str) -> dict | None:
    if not ObjectId.is_valid(application_id):
        return None

    try:
        _check_mongo_connection()
        document = resume_applications.find_one({"_id": ObjectId(application_id)})
    except (ServerSelectionTimeoutError, PyMongoError) as exc:
        raise MongoConnectionError from exc

    if not document:
        return None

    return _convert_object_id(document)


def update_ats_status(application_id: str, status: str) -> bool:
    if not ObjectId.is_valid(application_id):
        return False

    try:
        _check_mongo_connection()
        result = resume_applications.update_one(
            {"_id": ObjectId(application_id)},
            {
                "$set": {
                    "ats_status": status,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
    except (ServerSelectionTimeoutError, PyMongoError) as exc:
        raise MongoConnectionError from exc

    return result.matched_count == 1


def update_kyc_verification(application_id: str, aadhaar_verification: dict) -> bool:
    if not ObjectId.is_valid(application_id):
        return False

    try:
        _check_mongo_connection()
        result = resume_applications.update_one(
            {"_id": ObjectId(application_id)},
            {
                "$set": {
                    "aadhaar_verification": aadhaar_verification,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
    except (ServerSelectionTimeoutError, PyMongoError) as exc:
        raise MongoConnectionError from exc

    return result.matched_count == 1


def _check_mongo_connection():
    client.admin.command("ping")


def _convert_object_id(document: dict) -> dict:
    converted_document = dict(document)
    converted_document["_id"] = str(converted_document["_id"])
    return converted_document
