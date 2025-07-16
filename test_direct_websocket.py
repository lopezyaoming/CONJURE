"""
Direct WebSocket connection to ElevenLabs Conversational AI
This bypasses the SDK to get direct access to all WebSocket messages
"""
import asyncio
import websockets
import json
import os
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
AGENT_ID = "agent_01k02wep6vev8rzsz6pww831s3"

async def test_direct_websocket():
    """Test direct WebSocket connection to ElevenLabs."""
    uri = f"wss://api.elevenlabs.io/v1/convai/conversation?agent_id={AGENT_ID}&xi_api_key={ELEVENLABS_API_KEY}"
    
    print(f"Connecting to: {uri[:50]}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to ElevenLabs WebSocket!")
            
            # Send initialization message
            init_message = {
                "type": "conversation_initiation_client_data",
                "conversation_config_override": {
                    "agent": {
                        "language": "en"
                    }
                }
            }
            await websocket.send(json.dumps(init_message))
            print("📤 Sent initialization message")
            
            # Listen for messages
            message_count = 0
            async for message in websocket:
                try:
                    data = json.loads(message)
                    message_type = data.get('type', 'unknown')
                    message_count += 1
                    
                    print(f"\n--- MESSAGE #{message_count}: {message_type} ---")
                    
                    if message_type == 'conversation_initiation_metadata':
                        conv_id = data.get('conversation_initiation_metadata_event', {}).get('conversation_id')
                        print(f"🎯 Conversation started: {conv_id}")
                        
                    elif message_type == 'user_transcript':
                        user_text = data.get('user_transcription_event', {}).get('user_transcript', '')
                        print(f"🎤 USER: {user_text}")
                        
                    elif message_type == 'agent_response':
                        agent_text = data.get('agent_response_event', {}).get('agent_response', '')
                        print(f"🤖 AGENT: {agent_text}")
                        
                    elif message_type == 'audio':
                        audio_data = data.get('audio_event', {}).get('audio_base_64', '')
                        print(f"🔊 Audio data received ({len(audio_data)} chars)")
                        
                    elif message_type == 'ping':
                        ping_ms = data.get('ping_event', {}).get('ping_ms', 'N/A')
                        print(f"📡 Ping: {ping_ms}ms")
                        
                        # Send pong response
                        pong_message = {
                            "type": "pong",
                            "event_id": data.get('ping_event', {}).get('event_id', 0)
                        }
                        await websocket.send(json.dumps(pong_message))
                        
                    else:
                        print(f"❓ Unknown message type: {message_type}")
                        print(f"Content preview: {str(data)[:200]}...")
                        
                        # Look for any text content
                        message_str = str(data)
                        if any(word in message_str.lower() for word in ['hello', 'hi', 'can', 'help', 'response']):
                            print(f"🔍 POTENTIAL AGENT TEXT FOUND:")
                            print(f"Full message: {data}")
                    
                    # Stop after getting a reasonable number of messages
                    if message_count > 50:
                        print("Stopping after 50 messages...")
                        break
                        
                except json.JSONDecodeError:
                    print(f"❌ Invalid JSON: {message}")
                except Exception as e:
                    print(f"❌ Error processing message: {e}")
                    
    except Exception as e:
        print(f"❌ WebSocket connection error: {e}")

if __name__ == "__main__":
    print("Testing direct WebSocket connection to ElevenLabs...")
    print("This will show ALL messages received from the WebSocket")
    print("Speak to the agent to see if we get agent_response events")
    print("Press Ctrl+C to stop\n")
    
    asyncio.run(test_direct_websocket()) 