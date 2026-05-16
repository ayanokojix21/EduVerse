import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import json

async def main():
    client = AsyncIOMotorClient("mongodb+srv://nishchandel21_db_user:NISHchan%4021@eduverse.rhsgyxs.mongodb.net/?appName=EduVerse")
    db = client["eduverse"]
    course_id = "824524319272"
    user_id = "vinayakgoel012@gmail.com"
    docs = await db["parent_chunks"].find({"user_id": user_id, "course_id": course_id}).to_list(length=3)
    print(json.dumps([d.get("metadata") for d in docs], indent=2))

asyncio.run(main())
