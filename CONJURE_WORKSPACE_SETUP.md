# CONJURE Blender Workspace Setup

## 🎯 **What It Does:**

When you start CONJURE (via `launcher/main.py`), the Blender addon now automatically:

### 1. **Creates a New Window**
- Opens a separate "CONJURE Workspace" window  
- Keeps your original Blender window untouched
- New window is dedicated to CONJURE operations

### 2. **Sets Render Viewport Shading**
- Automatically switches to **RENDERED** viewport shading
- Shows real-time rendered view of your 3D models
- No need to manually change viewport settings

### 3. **Disables Overlays**
- Turns off all viewport overlays for clean view
- Removes axis indicators, cursor, object origins
- Hides gizmos and toolbar for minimal interface
- Keeps only the floor grid for reference

### 4. **Optimizes Viewport**
- Sets up EEVEE render engine for fast real-time rendering
- Enables bloom, screen space reflections, ambient occlusion
- Configures clean world lighting
- Removes default cube automatically

## 📁 **Files Modified:**

- `scripts/addons/conjure/conjure_workspace.py` - New workspace setup module
- `scripts/addons/conjure/__init__.py` - Updated to include workspace setup
- `launcher/main.py` - Already configured to use CONJURE addon

## 🚀 **How to Use:**

1. **Start CONJURE normally:**
   ```bash
   python launcher/main.py
   ```

2. **Select generation mode** (LOCAL or CLOUD)

3. **Watch for the new window:**
   - A new Blender window will open automatically
   - Window title: "CONJURE Workspace"
   - Viewport will be in RENDERED mode with overlays off

4. **Start creating:**
   - The new window is ready for CONJURE operations
   - Clean, minimal interface focused on 3D modeling
   - Real-time rendered viewport for immediate feedback

## ⚙️ **What You'll See:**

```
Original Blender Window:
├── Default Blender interface
├── All your normal tools and panels
└── Unchanged workflow

CONJURE Workspace Window:
├── 🎨 RENDERED viewport shading (automatic)
├── 🚫 No overlays (clean view)
├── 🚫 No gizmos or toolbar clutter  
├── ✅ CONJURE panel on the right
├── ✅ Clean 3D viewport focused on your models
└── ✅ Real-time rendering for immediate feedback
```

## 🛠️ **Technical Details:**

The workspace setup happens automatically via:
- `bpy.app.timers.register()` - Delayed execution after addon loads
- `bpy.ops.wm.window_new()` - Creates new Blender window
- `space_3d.shading.type = 'RENDERED'` - Sets viewport shading
- `space_3d.overlay.show_overlays = False` - Disables overlays
- `scene.render.engine = 'EEVEE'` - Fast rendering engine

## 🎉 **Result:**

When you start CONJURE, you'll automatically get:
- ✅ A dedicated, clean workspace for 3D modeling
- ✅ Real-time rendered viewport (no manual setup needed)
- ✅ Minimal, distraction-free interface
- ✅ Optimized for CONJURE voice/gesture workflow

**The setup is now as bare and optimized as possible for CONJURE operations!** 🎊
