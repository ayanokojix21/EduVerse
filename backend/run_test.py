import asyncio
from app.services.core.chat_service import ChatService

async def main():
    service = ChatService(db=None, sync_client=None)
    messages = []
    
    class FakeBGTasks:
        def add_task(self, *args, **kwargs):
            pass
            
    async for event in service.run(
        user_id="test_user",
        course_id="test_course",
        message="what is the news?",
        background_tasks=FakeBGTasks()
    ):
        if 'event' in event and 'data' in event:
            event_type = event['event']
            if event_type == 'node_start':
                print("NODE_START:", event['data'])
            elif event_type == 'tool_start':
                print("TOOL_START:", event['data'])
            elif event_type == 'token':
                print("TOKEN:", repr(event['data']))

asyncio.run(main())
