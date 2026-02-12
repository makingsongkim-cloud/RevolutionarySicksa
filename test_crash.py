import asyncio
import time
from bot_server import handle_recommendation_logic, SkillPayload
import json

async def test():
    user_id = "test_user"
    utterance = "화난다"
    
    # Mock payload
    payload_dict = {
        "userRequest": {
            "user": {"id": user_id},
            "utterance": utterance
        },
        "bot": {"id": "bot_id", "name": "bot_name"},
        "action": {"name": "action_name", "clientExtra": {}, "params": {}, "id": "action_id", "detailParams": {}}
    }
    
    class MockPayload:
        def __init__(self, d):
            self.userRequest = type('obj', (object,), {
                "user": type('obj', (object,), {"id": d["userRequest"]["user"]["id"]}),
                "utterance": d["userRequest"]["utterance"]
            })
            self.bot = d["bot"]
            self.action = d["action"]

    payload = MockPayload(payload_dict)
    
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
