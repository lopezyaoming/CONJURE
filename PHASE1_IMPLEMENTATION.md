# Phase 1 - VIBE Modeling Implementation

## Overview

This document describes the implementation of Phase 1 VIBE Modeling for CONJURE, which integrates FLUX.1-dev, FLUX.1-Depth-dev, and PartPacker APIs to enable AI-driven 3D mesh generation from natural language prompts.

## Key Features

### 🎨 AI-Powered Mesh Generation
- **FLUX.1-dev**: Generate initial concept images from text prompts
- **FLUX.1-Depth-dev**: Create depth-controlled images using GestureCamera renders as input
- **PartPacker**: Convert 2D images to production-ready 3D meshes

### 📦 Advanced Mesh Processing
- **Volume-based Culling**: Automatically remove small, unwanted mesh fragments
- **Segment Labeling**: Organize imported meshes as `seg_1`, `seg_2`, etc. by volume
- **Fuse Mesh**: Boolean union all segments into a single cohesive object
- **Segment Selection**: Gesture-based segment picking for focused editing

### 🔌 FastAPI Integration
- Centralized API server for coordinating all external API calls
- Robust error handling and timeout management
- Scalable architecture for future API integrations

## Architecture

```
User Prompt → FLUX.1-Depth (w/ GestureCamera) → PartPacker → Blender Import
     ↓                    ↓                         ↓             ↓
 Text Input         2D Image Generation      3D Model Gen    Mesh Processing
```

## API Endpoints

### Core Generation APIs

1. **`POST /flux/generate`** - FLUX.1-dev image generation
2. **`POST /flux/depth`** - FLUX.1-Depth-dev with control image
3. **`POST /partpacker/generate_3d`** - 3D model generation
4. **`POST /blender/render_gesture_camera`** - Trigger GestureCamera render
5. **`POST /blender/import_mesh`** - Import and process meshes

### Instruction Manager Tools

- **`generate_flux_mesh`** - Complete FLUX1.DEPTH → PartPacker pipeline
- **`fuse_mesh`** - Boolean union all segments
- **`segment_selection`** - Enable gesture-based segment picking
- **`mesh_import`** - Import and process PartPacker results

## File Structure

```
CONJURE/
├── launcher/
│   ├── api_server.py              # FastAPI server with FLUX/PartPacker endpoints
│   ├── instruction_manager.py     # Updated with Phase 1 tools
│   └── main.py                    # FLUX pipeline orchestration
├── scripts/addons/conjure/
│   ├── ops_phase1.py              # New Phase 1 Blender operators
│   ├── operator_main.py           # Updated with Phase 1 command handling
│   ├── panel_ui.py                # Updated UI with Phase 1 controls
│   └── __init__.py                # Updated registration
├── requirements.txt               # Added gradio_client dependency
└── test_phase1_implementation.py  # Comprehensive test suite
```

## Setup Instructions

### 1. Install Dependencies

```bash
pip install gradio_client
```

### 2. Set Environment Variables

```bash
export HUGGINGFACE_HUB_ACCESS_TOKEN="your_token_here"
export OPENAI_API_KEY="your_openai_key"  # For existing agent functionality
export ELEVENLABS_API_KEY="your_elevenlabs_key"  # For existing agent functionality
```

### 3. Start the System

1. Start the main CONJURE application:
```bash
python launcher/main.py
```

2. The FastAPI server will start automatically on `http://127.0.0.1:8000`

### 4. Test the Implementation

Run the test script to verify everything works:
```bash
python test_phase1_implementation.py
```

## Usage Guide

### In Blender UI

The CONJURE panel now includes a **"Phase 1 - VIBE Modeling"** section with:

#### FLUX Mesh Generation
- **Render Camera**: Capture GestureCamera view for FLUX.1-Depth input
- **Test FLUX Pipeline**: Run complete pipeline with sample prompt

#### Mesh Processing  
- **Fuse Segments**: Boolean union all imported segments
- **Select Segment**: Enable gesture-based segment selection

### Programmatic Usage

#### Generate Mesh from Prompt

```python
# Via instruction manager
instruction = {
    "tool_name": "generate_flux_mesh",
    "parameters": {
        "prompt": "A futuristic robotic sculpture with metallic surfaces",
        "seed": 42,
        "min_volume_threshold": 0.001
    }
}

# Execute via API
import httpx
response = httpx.post("http://127.0.0.1:8000/execute_instruction", 
                     json={"instruction": instruction})
```

#### Direct API Calls

```python
import httpx

# 1. Generate FLUX.1-Depth image
flux_response = httpx.post("http://127.0.0.1:8000/flux/depth", json={
    "control_image_path": "data/generated_images/gestureCamera/render.png",
    "prompt": "A mechanical sculpture with intricate details",
    "seed": 42
})

# 2. Generate 3D model
partpacker_response = httpx.post("http://127.0.0.1:8000/partpacker/generate_3d", json={
    "image_path": flux_response.json()["data"]["image_path"],
    "seed": 42
})

# 3. Import to Blender
import_response = httpx.post("http://127.0.0.1:8000/blender/import_mesh", json={
    "mesh_path": partpacker_response.json()["data"]["model_path"],
    "min_volume_threshold": 0.001
})
```

## Workflow Examples

### Complete FLUX Pipeline

1. **Start with Primitive** (optional):
   ```python
   {"tool_name": "spawn_primitive", "parameters": {"primitive_type": "Sphere"}}
   ```

2. **Generate FLUX Mesh**:
   ```python
   {"tool_name": "generate_flux_mesh", "parameters": {"prompt": "futuristic robot"}}
   ```

3. **Choose Processing Path**:
   - **Fuse all segments**: `{"tool_name": "fuse_mesh", "parameters": {}}`
   - **Select segment**: `{"tool_name": "segment_selection", "parameters": {}}`

### Manual Step-by-Step

1. Render GestureCamera view
2. Call FLUX.1-Depth API with prompt
3. Call PartPacker API with generated image
4. Import and process resulting mesh
5. Apply volume culling and segment labeling

## Configuration Options

### Volume Culling
- **`min_volume_threshold`**: Default `0.001` - Meshes smaller than this are removed
- Adjustable per-generation for different mesh complexities

### Generation Quality
- **FLUX.1-dev**: `guidance_scale=3.5`, `num_inference_steps=28`
- **FLUX.1-Depth**: `guidance_scale=10`, `num_inference_steps=28`  
- **PartPacker**: `num_steps=50`, `cfg_scale=7`, `grid_res=384`

### Mesh Processing
- **Segment Naming**: Automatic labeling as `seg_1`, `seg_2`, etc. by volume
- **Boolean Operations**: Union all segments from largest to smallest
- **Centering**: All imported meshes centered at origin

## Error Handling

The implementation includes comprehensive error handling:

- **API Timeouts**: 5min for FLUX, 10min for PartPacker, 1min for import
- **File Validation**: Verify existence of images and models before processing
- **Graceful Fallbacks**: Continue operation even if individual steps fail
- **Detailed Logging**: Full error traces for debugging

## Performance Considerations

### Generation Times
- **FLUX.1-dev**: ~30-60 seconds (1024x1024)
- **FLUX.1-Depth**: ~30-90 seconds (1024x1024)
- **PartPacker**: ~2-10 minutes (depends on complexity)

### Optimization Tips
- Use lower `grid_res` (256) for faster PartPacker generation during testing
- Reduce `num_inference_steps` for quicker FLUX generation
- Adjust `target_num_faces` based on desired mesh detail

## Future Enhancements

### Planned Features
- **Batch Processing**: Generate multiple variants simultaneously
- **Style Transfer**: Apply artistic styles to generated meshes
- **Interactive Refinement**: Real-time parameter adjustment
- **Quality Presets**: Fast/Standard/High quality generation modes

### API Extensions
- **Additional 2D→3D Models**: Integration with other generative 3D APIs
- **Texture Generation**: Automatic material and texture application
- **Animation**: Rigging and animation generation from poses

## Troubleshooting

### Common Issues

1. **"Control image not found"**
   - Run "Render Camera" button in Blender first
   - Check `data/generated_images/gestureCamera/render.png` exists

2. **"API server not healthy"**
   - Ensure `python launcher/main.py` is running
   - Check port 8000 is not in use by other applications

3. **"PartPacker generation failed"**
   - Verify HUGGINGFACE_HUB_ACCESS_TOKEN is set correctly
   - Check image quality - PartPacker works best with clear, well-lit objects

4. **"No meshes remain after culling"**
   - Lower `min_volume_threshold` parameter
   - Check input image has clear, substantial objects

### Debug Mode

Enable detailed logging by setting:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Integration with Existing CONJURE

Phase 1 seamlessly integrates with existing CONJURE functionality:

- **Gesture Controls**: All existing hand gestures continue to work
- **Conversational Agent**: Agents can trigger Phase 1 tools via instruction manager
- **Generative Pipeline**: Original ComfyUI workflows remain available
- **State Management**: Uses existing `state.json` coordination system

The implementation preserves all existing features while adding powerful new AI-driven mesh generation capabilities.

---

**Status**: ✅ **Complete and Ready for Testing**

This implementation provides a solid foundation for AI-powered 3D modeling in CONJURE, with robust error handling, comprehensive testing, and clear documentation for future development. 