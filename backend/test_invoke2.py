import asyncio
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import get_settings
from langchain_core.messages import HumanMessage
import base64

def run_in_thread():
    settings = get_settings()
    llm = ChatGoogleGenerativeAI(model="gemma-4-31b-it", google_api_key=settings.google_api_key)
    try:
        # 1x1 white pixel
        b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
        mm_msg = HumanMessage(content=[
            {"type": "text", "text": "What is this?"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
        ])
        res = llm.invoke([mm_msg])
        print("Success:", res.content)
    except Exception as e:
        import traceback
        traceback.print_exc()

async def main():
    import anyio
    await anyio.to_thread.run_sync(run_in_thread)

asyncio.run(main())
