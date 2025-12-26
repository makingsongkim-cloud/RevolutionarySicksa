import google.generativeai as genai
import os
from dotenv import load_dotenv
import time

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
print(f"API Key found: {'Yes' if API_KEY else 'No'}")
if API_KEY:
    print(f"Key preview: {API_KEY[:5]}...{API_KEY[-3:]}")

genai.configure(api_key=API_KEY)

model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
print(f"\nTarget Model: {model_name}")

try:
    print("Sending request...")
    start = time.time()
    model = genai.GenerativeModel(model_name)
    response = model.generate_content("Hello! Are you working?")
    print(f"Response: {response.text}")
    print(f"Duration: {time.time() - start:.2f}s")
    print("\n✅ API Success!")
except Exception as e:
    print(f"\n❌ API Failed: {e}")
