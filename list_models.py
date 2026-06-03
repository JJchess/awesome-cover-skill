import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

print("Available image models:")
try:
    for model in client.models.list():
        if "image" in model.name.lower() or "imagen" in model.name.lower():
            print("-", model.name)
except Exception as e:
    print("Error listing models:", e)
