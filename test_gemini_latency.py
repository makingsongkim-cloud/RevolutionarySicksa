
import os
import time
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

start_time = time.time()
try:
    model = genai.GenerativeModel('gemini-2.0-flash')
    response = model.generate_content("Hello, simple response.")
    end_time = time.time()
    print(f"Response: {response.text}")
    print(f"Time taken: {end_time - start_time:.2f} seconds")
except Exception as e:
    print(f"Error: {e}")
