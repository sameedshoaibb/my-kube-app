from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import redis.asyncio as redis
import pika
import os
import logging
import json
from datetime import datetime

# ---------------- Logging Setup ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ---------------- App Initialization ----------------
app = FastAPI()

# Enable CORS for all origins (adjust in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# ---------------- Environment Setup ----------------
MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongodb:27017")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

# MongoDB
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["testdb"]
users_collection = db["users"]

# Redis
@app.on_event("startup")
async def startup_event():
    app.state.redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    logger.info("✅ Connected to Redis")

@app.on_event("shutdown")
async def shutdown_event():
    await app.state.redis.close()
    logger.info("🔌 Redis connection closed")

# ---------------- Models ----------------
class User(BaseModel):
    name: str
    email: str

class CacheEntry(BaseModel):
    value: str

class QueueMessage(BaseModel):
    message: str

# ---------------- API Endpoints ----------------

@app.post("/users/")
async def create_user(user: User):
    logger.info("📥 Creating new user...")
    result = await users_collection.insert_one(user.dict())
    user_id = str(result.inserted_id)

    timestamp = datetime.utcnow().isoformat()
    redis = app.state.redis

    # Cache created_at timestamp
    await redis.set(f"user:{user_id}:created_at", timestamp)
    # Cache full user object
    user_data = {"id": user_id, **user.dict()}
    await redis.set(f"user:{user_id}:data", json.dumps(user_data), ex=300)

    logger.info(f"✅ User {user_id} created and cached")

    # Send message to RabbitMQ
    try:
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()
        channel.queue_declare(queue="default")
        channel.basic_publish(
            exchange="", routing_key="default", body=f"User {user_id} created"
        )
        connection.close()
        logger.info("📤 Message published to RabbitMQ")
    except Exception as e:
        logger.error(f"❌ RabbitMQ error: {e}")

    return user_data

@app.get("/users/{user_id}")
async def get_user(user_id: str):
    redis = app.state.redis
    cache_key = f"user:{user_id}:data"

    # Try Redis first
    cached_data = await redis.get(cache_key)
    if cached_data:
        logger.info(f"⚡ Cache hit for user {user_id}")
        return {"cached": True, **json.loads(cached_data)}

    logger.info(f"🔍 Cache miss. Fetching user {user_id} from MongoDB")
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
    except Exception:
        logger.warning("⚠️ Invalid user ID format")
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    if not user:
        logger.warning("❌ User not found")
        raise HTTPException(status_code=404, detail="User not found")

    user["id"] = str(user["_id"])
    del user["_id"]

    # Cache for future lookups
    await redis.set(cache_key, json.dumps(user), ex=300)
    logger.info(f"🧠 User {user_id} cached in Redis")

    return {"cached": False, **user}

@app.delete("/users/{user_id}")
async def delete_user(user_id: str):
    logger.info(f"🗑️ Deleting user {user_id}")
    try:
        result = await users_collection.delete_one({"_id": ObjectId(user_id)})
    except Exception:
        logger.warning("⚠️ Invalid user ID format")
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    # Delete from Redis
    redis = app.state.redis
    await redis.delete(f"user:{user_id}:data")
    await redis.delete(f"user:{user_id}:created_at")

    logger.info(f"✅ User {user_id} deleted from MongoDB and Redis")
    return {"message": "User deleted successfully"}

@app.post("/cache/{key}")
async def set_cache_entry(key: str, data: CacheEntry):
    await app.state.redis.set(key, data.value, ex=300)
    logger.info(f"🧊 Cached key '{key}' for 5 minutes")
    return {"message": f"Key '{key}' cached for 5 minutes"}

@app.get("/cache/{key}")
async def get_cache_entry(key: str):
    value = await app.state.redis.get(key)
    if value is None:
        logger.warning(f"❌ Cache miss: {key}")
        raise HTTPException(status_code=404, detail="Key not found in cache")
    return {"key": key, "value": value}

@app.post("/queue/")
async def publish_message(payload: QueueMessage):
    logger.info(f"🚀 Sending message to RabbitMQ: {payload.message}")
    try:
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()
        channel.queue_declare(queue="default")
        channel.basic_publish(exchange="", routing_key="default", body=payload.message)
        connection.close()
        logger.info("✅ Message sent successfully")
        return {"message": "Message published to RabbitMQ"}
    except Exception as e:
        logger.error(f"❌ Failed to publish message: {e}")
        raise HTTPException(status_code=500, detail=f"RabbitMQ error: {str(e)}")

@app.get("/ping-redis")
async def ping_redis():
    try:
        pong = await app.state.redis.ping()
        return {"redis": "✅ working"} if pong else {"redis": "❌ not responding"}
    except Exception as e:
        logger.error(f"❌ Redis ping failed: {e}")
        return {"error": str(e)}

@app.get("/ping-rabbitmq")
def ping_rabbitmq():
    try:
        conn = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        conn.close()
        return {"rabbitmq": "✅ connection successful"}
    except Exception as e:
        logger.error(f"❌ RabbitMQ ping failed: {e}")
        return {"error": str(e)}
