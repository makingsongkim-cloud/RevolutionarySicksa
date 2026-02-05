
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
print(f"Key loaded: {bool(api_key)}")

genai.configure(api_key=api_key)

try:
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content("Hello, can you hear me?")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
