# Force Import Last Mesh - Usage Guide

## 🎯 **What It Does**
The "Force Import Last Mesh" button manually imports the most recently generated mesh file and triggers the segment selection workflow. This is useful for:
- Re-importing meshes when automatic detection fails
- Testing the import/segmentation workflow
- Working with previously generated meshes

## 📍 **Location**
- **Blender UI**: 3D Viewport → Sidebar (N key) → CONJURE tab
- **Section**: "Mesh Import" 
- **Button**: "Force Import Last Mesh" 🗂️

## ⚙️ **Requirements**

### 1. CONJURE API Server Must Be Running
The button requires the CONJURE API server to be active on `127.0.0.1:8000`.

**To start the API server:**
```bash
cd C:\Coding\CONJURE
python launcher/main.py
```

**Choose any generation mode (1-5) to start the full system with API server.**

### 2. Mesh Files Must Exist
The button looks for mesh files in:
```
C:\Coding\CONJURE\data\generated_models\partpacker_results\
```

**Priority order:**
1. `partpacker_result_0.glb` (primary target)
2. Most recent `.glb` file (fallback)

## 🚀 **How to Use**

### Step 1: Start CONJURE System
```bash
cd C:\Coding\CONJURE
python launcher/main.py
```
- Choose any generation mode (1-5)
- Wait for "CONJURE is now running" message

### Step 2: Open Blender with CONJURE Addon
- Load your Blender project with CONJURE addon enabled
- Press `N` to open the sidebar
- Navigate to the **CONJURE** tab

### Step 3: Click Force Import
- Find the "Mesh Import" section
- Click **"Force Import Last Mesh"**
- Wait for success/error message

### Step 4: Expected Result
If successful:
1. ✅ Mesh imports into Blender scene
2. 🔄 Mesh gets segmented automatically  
3. 🎯 System enters segment selection mode
4. 📝 Success message appears in Blender

## ❌ **Troubleshooting**

### Error: "API server not running"
**Cause:** CONJURE launcher not started or API server failed
**Solution:** 
1. Run `python launcher/main.py`
2. Wait for "CONJURE is now running" message
3. Try Force Import again

### Error: "No mesh files found"
**Cause:** No generated meshes available
**Solution:**
1. Generate a mesh first using any mode:
   - LOCAL mode with ComfyUI
   - SERVERLESS mode with runComfy
   - HUGGINGFACE mode
2. Or check `data/generated_models/partpacker_results/` for existing files

### Error: "Import failed: [error message]"
**Cause:** Mesh file corrupted or import process failed
**Solutions:**
1. Try generating a new mesh
2. Check Blender console for detailed error messages
3. Verify mesh file isn't corrupted (check file size > 0)

## 🔍 **Behind the Scenes**

When you click "Force Import Last Mesh":

1. **File Detection**: Searches for `partpacker_result_0.glb` or latest `.glb`
2. **API Call**: Posts to `http://127.0.0.1:8000/blender/import_mesh`
3. **Import Trigger**: API server tells Blender to import the mesh
4. **Segmentation**: Mesh gets automatically segmented
5. **Selection Mode**: System enters segment selection workflow

## 📋 **Available Mesh Files**
Current files in your system:
- ✅ `partpacker_result_0.glb` (3.2MB) - **Will be used first**
- ✅ `partpacker_result_1337.glb` (21.9MB) - Fallback option
- ✅ `partpacker_result_42.glb` (29.1MB) - Fallback option

## 💡 **Tips**
- Always start the CONJURE launcher before using Force Import
- The button works independently of generation mode
- Use this for testing when automatic import fails
- Check the Blender console for detailed status messages
