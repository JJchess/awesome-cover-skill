import os
from dotenv import load_dotenv
from google import genai
import json

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

try:
    print("Sending request...")
    response = client.models.generate_content(
        model="gemini-3.1-flash-image-preview",
        contents=["A simple red dot"],
    )
    
    print("\n--- 完整 Response 类型 ---")
    print(type(response))
    
    print("\n--- Response 包含的属性 ---")
    print(dir(response))
    
    print("\n--- Response candidates 结构 ---")
    if hasattr(response, "candidates") and response.candidates:
        for i, candidate in enumerate(response.candidates):
            print(f"Candidate {i}:")
            if hasattr(candidate, "content") and candidate.content:
                print(f"  Content parts count: {len(candidate.content.parts)}")
                for j, part in enumerate(candidate.content.parts):
                    print(f"    Part {j}: text={'yes' if part.text else 'no'}, inline_data={'yes' if part.inline_data else 'no'}")
                    if part.inline_data:
                        print(f"      Mime Type: {part.inline_data.mime_type}")
                        # 打印前 50 个字节看看
                        if hasattr(part.inline_data, "data"):
                            data = part.inline_data.data
                            print(f"      Data length: {len(data)} bytes")
                            print(f"      Data preview: {data[:50]}")
    else:
        print("No candidates.")

    print("\n--- Response 转 dict (如果支持) ---")
    try:
        # 新版 genai 通常基于 Pydantic 或者提供了 model_dump()
        if hasattr(response, "model_dump"):
            dumped = response.model_dump()
            # 移除可能会很长的二进制数据
            if "candidates" in dumped:
                for c in dumped["candidates"]:
                    if "content" in c and "parts" in c["content"]:
                        for p in c["content"]["parts"]:
                            if "inline_data" in p and "data" in p["inline_data"]:
                                p["inline_data"]["data"] = f"<binary data, length: {len(p['inline_data']['data'])}>"
            print(json.dumps(dumped, indent=2))
    except Exception as inner_e:
        print(f"Could not dump to JSON: {inner_e}")

except Exception as e:
    print(f"Error: {e}")
