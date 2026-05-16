import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
from langchain_google_genai import ChatGoogleGenerativeAI

async def test():
    model = ChatGoogleGenerativeAI(model="gemini-2.5-pro")
    try:
        res = await model.ainvoke("Hello")
        print("Success:", res.content)
    except Exception as e:
        print("Error:", repr(e))

asyncio.run(test())
