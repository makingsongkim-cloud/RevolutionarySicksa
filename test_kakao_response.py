import sys
import os
import asyncio
import json
from unittest.mock import MagicMock

# Add current directory to path
sys.path.append(os.getcwd())

# Mock modules before importing bot_server
import bot_server

# Mock Global Recommender
bot_server.r = MagicMock()
bot_server.r.menus = [{"name": "TestMenu", "area": "TestArea", "tags": ["soup"], "category": "TestCat"}]
# Mock History Manager
bot_server.r.history_mgr = MagicMock()
bot_server.r.history_mgr.save_history = MagicMock()

# Mock Session Manager
bot_server.session_manager.get_last_recommendation = MagicMock(return_value={"name": "TestMenu", "tags": ["soup"], "category": "TestCat", "area": "TestArea"})

def test_fallback():
    print("--- Testing Emergency Fallback with '이유는' ---")
    utterance = "이유는"
    user_id = "test_user"
    
    # 1. Call get_emergency_fallback_response
    response = bot_server.get_emergency_fallback_response(
        reason="timeout",
        utterance=utterance,
        user_id=user_id,
        weather="비"
    )
    
    print("\n[Result Type]:", type(response))
    print("[Result JSON]:")
    print(json.dumps(response, indent=2, ensure_ascii=False))
    
    # Validate structure
    try:
        if not isinstance(response, dict): raise ValueError("Response is not a dict")
        if "template" not in response: raise ValueError("No template")
        if "outputs" not in response["template"]: raise ValueError("No outputs")
        simple_text = response["template"]["outputs"][0].get("simpleText")
        if not simple_text: raise ValueError("No simpleText")
        text = simple_text.get("text")
        if not text: raise ValueError("Empty text")
        print("\n✅ Validation Passed!")
    except Exception as e:
        print(f"\n❌ Validation Failed: {e}")

if __name__ == "__main__":
    test_fallback()
