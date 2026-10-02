from browser_use import Agent
from langchain_ollama import ChatOllama

# Use your local 2B model via Ollama
llm = ChatOllama(model="gemma4:e2b")

agent = Agent(
    task="Go to quotes.toscrape.com and extract first 5 quotes",
    llm=llm
)

result = agent.run()