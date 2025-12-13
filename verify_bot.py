from fastapi.testclient import TestClient
from bot_server import app

client = TestClient(app)

def test_lunch_recommendation():
    # Mock payload for Kakao Skill
    payload = {
        "userRequest": {
            "utterance": "점심 추천해줘"
        },
        "action": {
            "params": {
                "weather": "맑음", 
                "mood": "행복"
            }
        }
    }
    
    response = client.post("/api/lunch", json=payload)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.json()}")
    
    assert response.status_code == 200
    data = response.json()
    assert data['version'] == "2.0"
    assert "template" in data
    assert len(data['template']['outputs']) > 0
    text = data['template']['outputs'][0]['simpleText']['text']
    print(f"Recommendation Text: {text}")

if __name__ == "__main__":
    try:
        test_lunch_recommendation()
        print("Test Passed!")
    except ImportError:
        print("httpx not installed, skipping TestClient test.")
    except Exception as e:
        print(f"Test Failed: {e}")
