Never assume missing context. Ask questions if uncertain.
Never hallucinate libraries or functions – only use known, verified Python packages. If you are not sure, ask the user to provide you with the information you require.
Always confirm file paths and module names exist before referencing them in code or tests.
Never delete or overwrite existing code unless explicitly instructed to.
Do not modify Gesture-modelling logic by any reason.
Use already implemented code and functions as much as possible.

## FEATURE:

Build a platform that Enables seamless collaboration between a conversational interface (from now on, agent A) (voice-driven, real-time) and a backend controller (Agent B)(logic and modeling actions), to transform user input into production-ready 3D models.
The expectation is that these two agents work hand in hand, one as the low-latency, friendly front-facing agent and the other as the silent operator.
The conversational agent is managed by ElevenLabs conversational agent API service, and the backend agent is managed by chatgpt custom gpt API service.
The conversational agent speeaks with the user and guides him through the design process, while the backend agent listens and returns a JSON.
The conversational agent input and output (User speech and conversational agent response)  must be delievered to the backend agent, which will in turn react to the conversation being held with a JSON.
This JSON must be parsed into  "vision", "instruction", "tool_name", "parameters", "param1", "param2", "user_prompt".
- `vision` → A visual summary of the current screen. This gets written to `screen_description.txt`. If there is no image embedded in the response, simply use "null"
- `instruction` → Triggers a backend tool. If no action is needed, return `null`.
- `user_prompt` → A long-form visual prompt (between 60–75 words) for generating images/models.
If no backend action is required, the instruction becomes `null`.
The backend tools list and functions can be found in agentToolset.txt
You must: Build the platforms for both agents and help the backend agent to properly act on the actions. 
Everytime the conversational agent finishes a cycle of inquiry from the user and response from the agent, both this text must go to the backend agent, and blender must refresh it's gestureCamera.png by rendering. this rendering must be sent back to the backend agent to give context in "vision"
this are the system prompt for the agents: Agent\context_prompting\documentation\system_prompt_agents.md

## DOCUMENTATION:


Agent\context_prompting\documentation\elevenlabs_api_doc.md
Agent\context_prompting\documentation\openai_doc.md
Agent\context_prompting\documentation\elevenlabs_conversational_ai_overview_doc.md
Agent\context_prompting\documentation\API Reference - OpenAI API.html

these are the links for the agents

ElevenLabs: agent_01k02wep6vev8rzsz6pww831s3
OpenAI: https://chatgpt.com/g/g-68742df47c3881918fc61172bf53d4b4-vibe-backend

## OTHER CONSIDERATIONS:

Please read first through masterPrompt.txt
Be surgical in your implementations. don't modify or comment out stuff that you are not using. they most likely serve another purpose in the software.

