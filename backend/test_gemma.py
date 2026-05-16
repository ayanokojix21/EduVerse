import asyncio
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import get_settings

async def test():
    settings = get_settings()
    llm = ChatGoogleGenerativeAI(
        model=settings.gemma_routing_model,
        google_api_key=settings.google_api_key,
        temperature=0.1
    )
    try:
        res = await llm.ainvoke("Say hello")
        print(f"Success! Response: {res.content}")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test())
