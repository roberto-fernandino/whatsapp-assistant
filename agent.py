import asyncio
from mcp_agent.core.fastagent import FastAgent
from websockets.asyncio.client import connect

# Create the application
fast = FastAgent("FastAgent Example")

async def hello():
    async with connect("ws://localhost:8080/ws") as ws:
        while True:  # Keep running indefinitely
            try:
                message = await ws.recv()
                print(message)
            except Exception as e:
                print(f"Error: {e}")
                break  # Exit the loop if there's an error

# Define the agent

if __name__ == "__main__":
    asyncio.run(hello())
