import asyncio
import time
from bot_server import handle_recommendation_logic, SkillPayload
import json

async def test():
    user_id = "test_user"
    utterance = "화난다"

    # Define mock classes matching Pydantic model structure
    class User:
        def __init__(self, id):
            self.id = id

    class UserRequest:
        def __init__(self, utterance, user):
            self.utterance = utterance
            self.user = user

    class MockPayload:
        def __init__(self, user_id, utterance):
            self.userRequest = UserRequest(
                utterance=utterance,
                user=User(id=user_id)
            )
            self.bot = {"id": "bot_id", "name": "bot_name"}
            self.action = {"name": "action_name", "clientExtra": {}, "params": {}, "id": "action_id", "detailParams": {}}

    payload = MockPayload(user_id, utterance)
    
    print(f"Testing utterance: {utterance}")
    try:
        response = await handle_recommendation_logic(user_id, utterance, payload, time.time())
        print("Response received successfully")
        print(json.dumps(response, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"CRASH DETECTED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
