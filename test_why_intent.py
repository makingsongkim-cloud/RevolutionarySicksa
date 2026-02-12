from bot_server import analyze_intent_fallback

def test_intent(utterance):
    print(f"Testing: '{utterance}'")
    result = analyze_intent_fallback(utterance)
    print(f"Result: {result.get('intent')}")
    print("-" * 20)

test_intent("왜")
test_intent("왜?")
test_intent("이유가 뭐야")
test_intent("도움말")
