import asyncio
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import get_settings

def run_in_thread():
    settings = get_settings()
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=settings.google_api_key)
    try:
        res = llm.invoke("Hello")
        print("Success:", res.content)
    except Exception as e:
        print("Error:", type(e), str(e))

async def main():
    import anyio
    await anyio.to_thread.run_sync(run_in_thread)

asyncio.run(main())
