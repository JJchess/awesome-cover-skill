import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("No API key")
    exit(1)
genai.configure(api_key=api_key)

try:
    print("Testing gemini-2.5-flash-image")
    model = genai.GenerativeModel("gemini-2.5-flash-image")
    response = model.generate_content("A simple logo")
    print("Success!", response)
except Exception as e:
    print("Error 1:", e)

try:
    print("Testing imagen-3.0-generate-001")
    model = genai.ImageGenerationModel("imagen-3.0-generate-001")
    response = model.generate_images("A simple logo")
    print("Success!", response)
except Exception as e:
    print("Error 2:", e)
