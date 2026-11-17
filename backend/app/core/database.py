
from typing import Optional

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import settings


_client: Optional[AsyncMongoClient] = None
_database: Optional[AsyncDatabase] = None


async def connect_to_mongo() -> None:
    """Create the MongoDB client and verify database connectivity."""
    global _client, _database

    if _client is not None:
        return

    client = AsyncMongoClient(
        settings.mongodb_uri.get_secret_value(),
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        appname="HCM Lite",
    )

    try:
        await client.admin.command("ping")
    except Exception:
        await client.close()
        raise

    _client = client
    _database = client[settings.mongodb_database]


async def close_mongo_connection() -> None:
    """Close MongoDB resources during application shutdown."""
    global _client, _database

    if _client is not None:
        await _client.close()

    _client = None
    _database = None


def get_database() -> AsyncDatabase:
    """Return the connected database or fail if not initialized."""
    if _database is None:
        raise RuntimeError(
            "MongoDB is not connected. Check application lifespan."
        )

    return _database


def get_mongo_client() -> AsyncMongoClient:
    """Return the MongoDB client for transactions or admin commands."""
    if _client is None:
        raise RuntimeError(
            "MongoDB client is not initialized."
        )

    return _client
