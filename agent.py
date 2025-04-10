import asyncio
import json
from mcp_agent.core.fastagent import FastAgent
from websockets.asyncio.client import connect
from pathlib import Path
from openai import OpenAI
import os
import subprocess
import tempfile

fast = FastAgent("WhatsApp Assistant")

@fast.agent(
    name="whatsapp_assistant",
    instruction="""Sonia, you are an expert assistant that works for Roberto at analyzing WhatsApp messages and their context. Your function is to:
    1. When receiving a message, respond DIRECTLY with what you want to say to the user. Do not describe your actions.
    2. Keep responses clear and conversational
    4. IMPORTANT: Only respond with the exact message you want to send - do not include meta commentary or descriptions
    
    Example:
    User: "Oi, tudo bem?"
    You: "Olá! Tudo ótimo, obrigado por perguntar! Como posso ajudar você hoje? Meu nome é Sonia, sou assistente de Roberto. Enquanto ele trabalha, eu vou te ajudar com o que precisar. Vou juntar as informações que você me der falar com ele e te mandar uma mensagem com a resposta. Tudo bem?"
    """,
    model="anthropic.claude-3-7-sonnet-latest",
    servers=["whatsapp"],
    use_history=True
)

class AudioHandler:
    def __init__(self):
        self.client = OpenAI()
        self.temp_dir = tempfile.mkdtemp()
        self.speech_file_path = Path(self.temp_dir) / "speech.mp3"
        self.ogg_file_path = Path(self.temp_dir) / "audio.ogg"

    async def text_to_speech(self, text):
        try:
            # Generate MP3 audio
            with self.client.audio.speech.with_streaming_response.create(
                model="tts-1",  # Changed to use the standard TTS model
                voice="shimmer",  # Using a more natural voice
                input=text,
                speed=1.0,
                response_format="mp3"
            ) as response:
                response.stream_to_file(self.speech_file_path)
            
            # Convert MP3 to OGG using ffmpeg with auto-overwrite
            try:
                subprocess.run([
                    'ffmpeg',
                    '-y',  # Add -y flag to automatically overwrite files
                    '-i', str(self.speech_file_path),
                    '-c:a', 'libopus',  # Using Opus codec which WhatsApp supports
                    '-b:a', '128k',     # Bitrate that works well with WhatsApp
                    '-ar', '48000',     # Sample rate required by WhatsApp
                    str(self.ogg_file_path)
                ], check=True, capture_output=True)
                
                return str(self.ogg_file_path)
            except subprocess.CalledProcessError as e:
                print(f"Error converting audio: {e.stderr.decode()}")
                return None
                
        except Exception as e:
            print(f"Error in text_to_speech: {e}")
            return None

async def main():
    # Check for ffmpeg installation
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️ ffmpeg not found! Please install ffmpeg first:")
        print("macOS: brew install ffmpeg")
        print("Ubuntu/Debian: sudo apt-get install ffmpeg")
        print("Windows: choco install ffmpeg")
        exit(1)

    audio_handler = AudioHandler()
    
    async with fast.run() as agent:
        print("WhatsApp Assistant started and ready to process messages...")
        async with connect("ws://localhost:8080/ws") as ws:
            print("Connected to WebSocket server")
            while True:
                try:
                    message = await ws.recv()
                    data = json.loads(message)
                    
                    if data.get("type") == "message" and data.get("is_from_me") == False and not data.get("chat_jid").endswith("@g.us"):
                        content = data.get("content")
                        sender = data.get("sender")
                        print(f"Received message from {sender}: {content}")
                        
                        if content:
                            print("Processing message through assistant chain...")
                            # Get the assistant's response
                            response = await agent.whatsapp_assistant(data)
                            
                            if isinstance(response, str):
                                # Extract just the actual message content (remove any meta commentary)
                                actual_message = response.strip()
                                
                                # First send the text response
                                await agent.whatsapp_assistant({
                                    "type": "command",
                                    "command": "send_message",
                                    "content": actual_message
                                })
                                
                                # Then generate and send voice message
                                ogg_path = await audio_handler.text_to_speech(actual_message)
                                if ogg_path:
                                    await agent.whatsapp_assistant({
                                        "type": "command",
                                        "command": "send_voice_message",
                                        "file_path": ogg_path
                                    })
                                    print("Voice message sent successfully")
                                
                except Exception as e:
                    print(f"Error processing message: {e}")
                    continue

if __name__ == "__main__":
    # Ensure OPENAI_API_KEY is set
    if not os.getenv('OPENAI_API_KEY'):
        print("⚠️ OPENAI_API_KEY not found!")
        print("Please set your API key using:")
        print("export OPENAI_API_KEY='your-key-here'")
        exit(1)
        
    asyncio.run(main())
