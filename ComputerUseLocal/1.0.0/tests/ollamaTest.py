from ollama import chat

response = chat(
    model='gemma4:e4b',
    messages=[{'role': 'user', 'content': 'Hello!'}],
)
print(response.message.content)