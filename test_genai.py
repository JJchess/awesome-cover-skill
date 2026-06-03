import google.generativeai as genai
print("ImageGenerationModel:", hasattr(genai, "ImageGenerationModel"))
if hasattr(genai, "ImageGenerationModel"):
    print("Methods:", dir(genai.ImageGenerationModel))
