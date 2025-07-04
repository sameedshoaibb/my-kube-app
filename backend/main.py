# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from motor.motor_asyncio import AsyncIOMotorClient
# from bson import ObjectId
# import redis.asyncio as redis
# import pika
# import os

# app = FastAPI()

# # CORS config
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"]
# )

# # Environment Variables
# MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongodb:27017")
# REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
# RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

# # MongoDB setup
# client = AsyncIOMotorClient(MONGO_URL)
# db = client["testdb"]
# collection = db["users"]

# # Redis setup (async)
# @app.on_event("startup")
# async def connect_redis():
#     app.state.redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)


# @app.on_event("shutdown")
# async def close_redis():
#     await app.state.redis.close()

# # Pydantic models
# class User(BaseModel):
#     name: str
#     email: str

# class CacheEntry(BaseModel):
#     value: str

# class QueueMessage(BaseModel):
#     message: str

# # User APIs
# @app.post("/users/")
# async def create_user(user: User):
#     result = await collection.insert_one(user.dict())
#     return {"id": str(result.inserted_id), **user.dict()}

# @app.get("/users/{user_id}")
# async def get_user(user_id: str):
#     try:
#         user = await collection.find_one({"_id": ObjectId(user_id)})
#     except Exception:
#         raise HTTPException(status_code=400, detail="Invalid ID format")
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#     user["id"] = str(user["_id"])
#     del user["_id"]
#     return user

# @app.delete("/users/{user_id}")
# async def delete_user(user_id: str):
#     try:
#         result = await collection.delete_one({"_id": ObjectId(user_id)})
#     except Exception:
#         raise HTTPException(status_code=400, detail="Invalid ID format")
#     if result.deleted_count == 0:
#         raise HTTPException(status_code=404, detail="User not found")
#     return {"message": "User deleted successfully"}

# # Redis APIs
# @app.post("/cache/{key}")
# async def set_cache(key: str, data: CacheEntry):
#     await app.state.redis.set(key, data.value, ex=300)
#     return {"message": f"{key} cached for 5 minutes"}

# @app.get("/cache/{key}")
# async def get_cache(key: str):
#     value = await app.state.redis.get(key)
#     if value is None:
#         raise HTTPException(status_code=404, detail="Key not found in cache")
#     return {"key": key, "value": value}

# # RabbitMQ Publisher
# @app.post("/queue/")
# async def publish_to_queue(payload: QueueMessage):
#     try:
#         connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
#         channel = connection.channel()
#         channel.queue_declare(queue="default")
#         channel.basic_publish(exchange="", routing_key="default", body=payload.message)
#         connection.close()
#         return {"message": "Message published to RabbitMQ"}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"RabbitMQ error: {str(e)}")

# @app.get("/ping-redis")
# async def ping_redis():
#     try:
#         pong = await app.state.redis.ping()
#         return {"redis": "✅ working"} if pong else {"redis": "❌ not responding"}
#     except Exception as e:
#         return {"error": str(e)}
    
# @app.get("/ping-rabbitmq")
# def ping_rabbitmq():
#     try:
#         conn = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
#         conn.close()
#         return {"rabbitmq": "✅ connection successful"}
#     except Exception as e:
#         return {"error": str(e)}


from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import redis.asyncio as redis
import pika
import os
import logging
from datetime import datetime

# ---------------- Logging Setup ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ---------------- App Init ----------------
app = FastAPI()

# CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Environment Variables
MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongodb:27017")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

# MongoDB setup
client = AsyncIOMotorClient(MONGO_URL)
db = client["testdb"]
collection = db["users"]

# Redis setup
@app.on_event("startup")
async def connect_redis():
    app.state.redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    logger.info("🔌 Redis connection established")

@app.on_event("shutdown")
async def close_redis():
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

# MongoDB - Create
@app.post("/users/")
async def create_user(user: User):
    logger.info("📥 Received request to create user")
    result = await collection.insert_one(user.dict())
    user_id = str(result.inserted_id)
    logger.info(f"✅ User inserted to MongoDB with id: {user_id}")

    timestamp_key = f"user:{user_id}:created_at"
    timestamp = datetime.utcnow().isoformat()
    await app.state.redis.set(timestamp_key, timestamp)
    logger.info(f"🕒 Timestamp cached in Redis: {timestamp_key} = {timestamp}")

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

    return {"id": user_id, **user.dict()}

# MongoDB - Read
@app.get("/users/{user_id}")
async def get_user(user_id: str):
    logger.info(f"🔍 Fetching user from MongoDB with id: {user_id}")
    try:
        user = await collection.find_one({"_id": ObjectId(user_id)})
    except Exception:
        logger.warning("⚠️ Invalid ObjectId format")
        raise HTTPException(status_code=400, detail="Invalid ID format")

    if not user:
        logger.warning("❌ User not found")
        raise HTTPException(status_code=404, detail="User not found")

    user["id"] = str(user["_id"])
    del user["_id"]
    return user

# MongoDB - Delete
@app.delete("/users/{user_id}")
async def delete_user(user_id: str):
    logger.info(f"🗑️ Deleting user from MongoDB with id: {user_id}")
    try:
        result = await collection.delete_one({"_id": ObjectId(user_id)})
    except Exception:
        logger.warning("⚠️ Invalid ObjectId format")
        raise HTTPException(status_code=400, detail="Invalid ID format")

    if result.deleted_count == 0:
        logger.warning("❌ User not found for deletion")
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User deleted successfully"}

# Redis - Set
@app.post("/cache/{key}")
async def set_cache(key: str, data: CacheEntry):
    logger.info(f"📦 Caching {key} = {data.value}")
    await app.state.redis.set(key, data.value, ex=300)
    return {"message": f"{key} cached for 5 minutes"}

# Redis - Get
@app.get("/cache/{key}")
async def get_cache(key: str):
    logger.info(f"📤 Retrieving cache key: {key}")
    value = await app.state.redis.get(key)
    if value is None:
        logger.warning(f"❌ Cache miss: {key}")
        raise HTTPException(status_code=404, detail="Key not found in cache")
    return {"key": key, "value": value}

# RabbitMQ - Publish
@app.post("/queue/")
async def publish_to_queue(payload: QueueMessage):
    logger.info(f"🚀 Publishing message to RabbitMQ: {payload.message}")
    try:
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()
        channel.queue_declare(queue="default")
        channel.basic_publish(exchange="", routing_key="default", body=payload.message)
        connection.close()
        logger.info("✅ Message published to RabbitMQ")
        return {"message": "Message published to RabbitMQ"}
    except Exception as e:
        logger.error(f"❌ RabbitMQ error: {e}")
        raise HTTPException(status_code=500, detail=f"RabbitMQ error: {str(e)}")

# Redis - Ping
@app.get("/ping-redis")
async def ping_redis():
    logger.info("🔍 Pinging Redis")
    try:
        pong = await app.state.redis.ping()
        return {"redis": "✅ working"} if pong else {"redis": "❌ not responding"}
    except Exception as e:
        logger.error(f"❌ Redis ping failed: {e}")
        return {"error": str(e)}

# RabbitMQ - Ping
@app.get("/ping-rabbitmq")
def ping_rabbitmq():
    logger.info("🔍 Pinging RabbitMQ")
    try:
        conn = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        conn.close()
        return {"rabbitmq": "✅ connection successful"}
    except Exception as e:
        logger.error(f"❌ RabbitMQ ping failed: {e}")
        return {"error": str(e)}
