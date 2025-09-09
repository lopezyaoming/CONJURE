# CONJURE
### MS Architectural Technologies Thesis Project

> CONJURE is an AI-powered, gesture-based platform that transforms ideas into production-ready 3D models through natural voice input and intuitive hand movements. It creates a continuous refinement loop where users speak their ideas and shape them with gestures, while AI automatically generates and refines 3D models in real-time.

## Key Features
- **Voice-Driven Prompting:** Speak naturally to update and refine your 3D model description
- **Intuitive Gesture Control:** Shape and manipulate 3D models with natural hand movements
- **Continuous AI Refinement:** Automatic 30-second cycles of AI-powered mesh generation
- **Real-Time Visual Feedback:** See your changes reflected instantly in the Blender viewport
- **Streamlined Interface:** Clean UI showing current prompt and active brush information

---

## Core Philosophy

CONJURE eliminates the complexity of traditional 3D modeling by creating a **continuous creative flow**. Instead of managing complex workflows or conversing with AI agents, users simply:

1. **Speak their ideas** - Voice input continuously updates the model description
2. **Shape with gestures** - Natural hand movements refine the physical form
3. **Let AI iterate** - Automatic generation cycles create refined versions every 30 seconds

This creates an **instinctive, visual workflow** where the creative process feels natural and uninterrupted.

---

## Core Components

### 1. Voice Input System
- **Whisper Integration**: Continuous speech-to-text conversion
- **Prompt Refinement**: ChatGPT processes voice input into structured FLUX prompts
- **Real-Time Updates**: User prompt updates immediately as you speak

### 2. Gesture Control System (`scripts/addons/conjure/`)
The central 3D modeling environment where all geometry is created and deformed using natural hand movements.

**Right-Hand Gestures (Primary Actions):**
- **Thumb + Index Finger**: Use active brush (deform, draw, or create primitives)
- **Thumb + Middle Finger**: Orbit camera around the model
- **Thumb + Ring Finger**: Cycle between brushes (DRAW, CREATE, GRAB, SMOOTH, INFLATE, FLATTEN)
- **Thumb + Pinky Finger**: Rewind/undo changes

**Left-Hand Gestures (Utility Actions):**
- **Thumb + Index Finger**: Boolean UNION (add drawn/created objects to mesh)
- **Thumb + Middle Finger**: Cycle brush size OR cycle primitives (in CREATE mode)
- **Thumb + Ring Finger**: Confirm primitive placement (CREATE mode only)
- **Thumb + Pinky Finger**: Boolean DIFFERENCE (subtract drawn/created objects from mesh)

### 3. Brush System
CONJURE features six specialized brushes for different modeling approaches:

#### **DRAW Brush**
Create organic curves and ribbons by drawing in 3D space:
1. **Right Thumb + Index**: Start drawing - move fingers to create 3D Bezier curves
2. **Release fingers**: Finish the stroke and apply DRAWbrush GeometryNode for thick ribbons
3. **Left Thumb + Index**: Boolean UNION to add ribbons to mesh
4. **Left Thumb + Pinky**: Boolean DIFFERENCE to subtract ribbons from mesh
5. **Right Pinky**: Rewind to remove last drawn stroke

#### **CREATE Brush**
Place and manipulate geometric primitives with precise control:
1. **Left Thumb + Middle**: Cycle through primitives (CUBE, SPHERE, CYLINDER, CONE, TORUS)
2. **Right Thumb + Index**: Start primitive preview - move fingers to adjust size and rotation
3. **Release fingers**: Preview stays active for further adjustment
4. **Right Thumb + Index again**: Continue adjusting size and rotation as needed
5. **Left Thumb + Ring**: Confirm primitive placement (converts to solid object)
6. **Left Thumb + Index**: Boolean UNION to add primitives to mesh
7. **Left Thumb + Pinky**: Boolean DIFFERENCE to subtract primitives from mesh
8. **Right Pinky**: Rewind to cancel preview or remove last confirmed primitive

#### **Traditional Sculpting Brushes**
- **GRAB**: Move and pull mesh vertices
- **SMOOTH**: Smooth surface irregularities
- **INFLATE**: Push vertices outward along surface normals
- **FLATTEN**: Flatten surface areas

### 4. Continuous AI Generation Loop
- **30-Second Cycles**: Automatic mesh generation every 30 seconds
- **FLUX.1-Depth Pipeline**: Uses current prompt + gesture camera render
- **Seamless Import**: New meshes automatically replace the current model
- **Uninterrupted Flow**: Users continue working while AI processes in background

### 5. Streamlined UI (`Agent/conjure_ui.py`)
**Minimal, Essential Information Only:**
- **Prompt Display**: Current model description with real-time updates
- **Brush Status**: Active tool and size indicator
- **Generation Status**: Visual feedback during AI processing cycles

---

## Workflow: Continuous Creative Refinement

### The Simplified Process

1. **Start Creating**: Begin with voice description or primitive shape
2. **Speak & Shape**: 
   - Voice input continuously refines the model description
   - Hand gestures shape the physical form
   - UI shows current prompt and active brush
3. **AI Iterates**: Every 30 seconds, AI generates a new mesh based on:
   - Current voice prompt (userPrompt.txt)
   - Current visual state (gestureRender.png)
   - Accumulated context from session
4. **Continue Refining**: Keep speaking and shaping as AI provides new iterations
5. **Natural Flow**: No interruptions, no complex decisions - just continuous creation

### Technical Flow

```
Voice Input → Whisper → ChatGPT → Structured Prompt → userPrompt.txt
     ↓
Gesture Camera Render → gestureRender.png
     ↓
[Every 30 seconds] → FLUX.1-Depth → PartPacker → New Mesh → Blender Import
     ↓
Continue Loop...
```

---

## FLUX Prompt Structure

The system generates structured prompts optimized for 3D mesh generation:

```json
{
  "subject": {
    "name": "string",                 // e.g., "stackable chair", "wireless headset"
    "form_keywords": ["string"],      // shape descriptors: "curved shell", "mono-block", "faceted"
    "material_keywords": ["string"],  // CMF: "brushed aluminum", "matte ABS", "polished steel"
    "color_keywords": ["string"]      // palette: "graphite gray", "satin sand", "electric blue"
  }
}
```

This structured data is automatically formatted into professional product photography prompts:

*"[Subject] shown in a three-quarter view and centered in frame, set against a clean studio background in neutral mid-gray. The [subject] sits under soft studio lighting with a large key softbox at 45 degrees, gentle fill, and a subtle rim to control reflections. Shot on a 35mm lens at f/5.6, ISO 100—product-catalog clarity, no clutter or props, no text or people, avoid pure white backgrounds."*

---

## How to Run

### Prerequisites
- Python 3.7+
- Blender 3.0+
- Required API keys:
  - `HUGGINGFACE_HUB_ACCESS_TOKEN`
  - `OPENAI_API_KEY`

### Quick Start

1. **Launch CONJURE:**
    ```bash
    python launcher/main.py
    ```

2. **Select Generation Mode:**
   - Choose LOCAL (HuggingFace) or CLOUD (RunComfy) when prompted

3. **Start Creating:**
   - Blender opens with CONJURE workspace
   - Click "Initiate CONJURE" in the 3D viewport panel
   - Begin speaking your ideas and shaping with gestures
   - AI automatically generates new iterations every 30 seconds

### What You'll See

- **Clean Blender Workspace**: Rendered viewport with minimal UI
- **CONJURE Overlay**: Shows current prompt and brush status
- **Continuous Updates**: Prompt text updates as you speak
- **Automatic Iterations**: New meshes appear every 30 seconds
- **Gesture Feedback**: Visual indicators for active brush and size

---

## Technical Architecture

### Simplified Component Structure

```
Voice Input → Whisper → ChatGPT → Prompt Updates
Hand Tracking → MediaPipe → Gesture Processing → Mesh Deformation
Timer Loop (30s) → FLUX Generation → Mesh Import → Continue
```

### Key Files

- **`launcher/main.py`**: Main orchestrator with simplified 30-second loop
- **`launcher/backend_agent.py`**: Streamlined prompt processing (no conversation)
- **`scripts/addons/conjure/operator_main.py`**: Gesture control and mesh deformation
- **`Agent/conjure_ui.py`**: Minimal UI showing prompt and brush status
- **`data/generated_text/userPrompt.txt`**: Current model description
- **`data/generated_images/gestureCamera/render.png`**: Current visual state

---

## Design Philosophy: Instinctive Creation

### What Changed
- **Removed**: Conversational AI agent, complex workflow phases, user decision points
- **Added**: Continuous voice input, automatic generation cycles, streamlined UI
- **Focused**: Natural creative flow without interruption or complexity

### Why This Works
- **No AI Sales Call Feel**: Direct creative input without synthetic personality
- **Visual Feedback**: See exactly what prompt is being used
- **Continuous Flow**: No stopping to make decisions or answer questions
- **Instinctive Interface**: Gesture controls feel natural and immediate
- **Automatic Refinement**: AI works in background while user stays creative

### User Experience
Users experience CONJURE as a **natural extension of their creativity** rather than a complex software tool. The interface disappears, leaving only the creative process of speaking ideas and shaping them with hands while AI continuously refines the results.

---

## Future Enhancements

- **Enhanced Mesh Import**: Advanced processing of generated models
- **Material Integration**: Automatic material application based on prompts
- **Export Options**: Direct export to various 3D formats
- **Performance Optimization**: Faster generation cycles and smoother interaction

---

*CONJURE: Where voice meets gesture, and AI amplifies human creativity through continuous, instinctive 3D modeling.*