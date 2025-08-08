# CONJURE Mode Selection

This document describes the new mode selection feature that allows choosing between **LOCAL** and **CLOUD** generation backends.

## Overview

CONJURE now supports two generation modes:

- **LOCAL** - Uses HuggingFace models (existing implementation)
- **CLOUD** - Uses runComfy cloud services (faster, more expensive)

## Mode Selection

When starting CONJURE, you'll be prompted to select your generation mode:

```
🚀 CONJURE - Generation Mode Selection
============================================================
Please choose your generation mode:

1. LOCAL  - Use HuggingFace models (current implementation)
   • FLUX.1-dev and FLUX.1-Depth-dev
   • PartPacker for 3D generation
   • Requires: HUGGINGFACE_HUB_ACCESS_TOKEN

2. CLOUD  - Use runComfy cloud services (faster, more expensive)
   • Cloud-based ComfyUI workflows
   • Faster generation with high-end GPUs
   • Requires: runComfy account and credits

============================================================
Enter your choice (1 for LOCAL, 2 for CLOUD):
```

## Local Mode (Default)

**Requirements:**
- `HUGGINGFACE_HUB_ACCESS_TOKEN` environment variable

**Services Used:**
- FLUX.1-dev (`black-forest-labs/FLUX.1-dev`) - Text-to-image generation
- FLUX.1-Depth-dev (`black-forest-labs/FLUX.1-Depth-dev`) - Depth-controlled images
- PartPacker (`nvidia/PartPacker`) - 2D to 3D model conversion

**Characteristics:**
- Uses HuggingFace's free/paid API quotas
- Moderate generation speed (depends on HF queue)
- No additional costs beyond HF API usage

## Cloud Mode (Coming Soon)

**Requirements:**
- runComfy account and credits
- `RUNCOMFY_API_KEY` environment variable (when implemented)

**Services:**
- Cloud-based ComfyUI workflows
- High-end GPU instances for faster generation
- Custom workflow orchestration

**Characteristics:**
- Faster generation with dedicated GPUs
- Pay-per-use model (more expensive)
- Scalable and reliable

## API Changes

### New Endpoints

#### `GET /mode`
Get current generation mode and service availability:

```json
{
  "generation_mode": "local",
  "available_modes": ["local", "cloud"],
  "local_available": true,
  "cloud_available": false,
  "services": {
    "local": {
      "name": "HuggingFace Models",
      "description": "FLUX.1-dev, FLUX.1-Depth-dev, PartPacker",
      "available": true,
      "requirements": "HUGGINGFACE_HUB_ACCESS_TOKEN"
    },
    "cloud": {
      "name": "runComfy Cloud",
      "description": "Cloud-based ComfyUI workflows",
      "available": false,
      "requirements": "runComfy account and credits"
    }
  }
}
```

### Updated Endpoints

All generation endpoints now:
- Automatically use the selected mode
- Include `generation_mode` in response data
- Work seamlessly with both LOCAL and CLOUD backends

Example response:
```json
{
  "success": true,
  "message": "FLUX image generated successfully using LOCAL mode",
  "data": {
    "image_path": "data/generated_images/flux_results/flux_result_1337.png",
    "seed_used": 1337,
    "generation_mode": "local"
  }
}
```

## Architecture

### Generation Services Interface

The new `GenerationService` abstract base class provides a unified interface:

```python
from launcher.generation_services import get_generation_service

# Get service for current mode
service = get_generation_service("local")  # or "cloud"

# Generate content
result = service.generate_flux_image(prompt="A futuristic sculpture", seed=42)
```

### Mode Configuration

Mode is set in `launcher/config.py`:

```python
GENERATION_MODE = "local"  # or "cloud"
```

## File Structure

New files added:
```
launcher/
├── generation_services.py     # Abstract service interface
├── config.py                 # Updated with GENERATION_MODE
├── main.py                   # Updated with mode selection
└── api_server.py             # Updated to use services

test_mode_selection.py         # Test script for mode functionality
MODE_SELECTION_README.md       # This documentation
```

## Testing

Run the test script to verify mode selection functionality:

```bash
python test_mode_selection.py
```

This tests:
- Config mode setting
- Generation service instantiation
- API endpoint functionality (if server is running)

## Usage Examples

### Starting with Mode Selection
```bash
python launcher/main.py
# Follow the interactive prompts to select LOCAL or CLOUD mode
```

### Checking Current Mode via API
```bash
curl http://127.0.0.1:8000/mode
```

### Generating Content (Same API, Different Backend)
```python
import httpx

# This will use whatever mode was selected at startup
response = httpx.post("http://127.0.0.1:8000/flux/generate", json={
    "prompt": "A beautiful sculpture",
    "seed": 1337
})

print(f"Generated using: {response.json()['data']['generation_mode']}")
```

## Implementation Status

- ✅ Mode selection interface
- ✅ LOCAL mode (HuggingFace) - Fully implemented
- ✅ Service architecture and abstraction
- ✅ API integration with mode awareness
- ⏳ CLOUD mode (runComfy) - Structure ready, implementation pending

## Next Steps

1. **runComfy Integration** - Implement CloudGenerationService
2. **Workflow Optimization** - Optimize cloud workflows for speed
3. **Cost Management** - Add usage tracking and cost estimation
4. **Fallback Logic** - Auto-fallback between modes if one fails
