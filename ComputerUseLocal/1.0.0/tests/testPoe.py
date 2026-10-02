import os
import openai

client = openai.OpenAI(
    api_key = os.getenv("POE_API_KEY", ""),  # or os.getenv("POE_API_KEY")
    base_url = "https://api.poe.com/v1",
)

response = client.responses.create(
    model = "GPT-OSS-120B-CS",
    input = "Hello world"
)

print(response.output_text)