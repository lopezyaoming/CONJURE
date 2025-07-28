# 🔄 CONJURE Auto-Refresh Guide

## 📸 Automatic Backend Agent Context Updates

The CONJURE Blender addon now includes **automatic refresh functionality** that continuously updates the `render.png` file every 3 seconds. This ensures your backend agent always has the most current visual context of your 3D scene for intelligent decision-making.

---

## ✨ Features

### 🎯 **Automatic Context Updates**
- **3-second intervals**: GestureCamera renders automatically every 3 seconds
- **Background operation**: Runs silently while you work
- **Backend agent integration**: Provides real-time visual context for AI decisions
- **Smart resource management**: Uses efficient timers and proper cleanup

### 🎛️ **Manual Controls**
- **Auto-start**: Begins automatically when you start CONJURE
- **Manual toggle**: Start/stop via the CONJURE UI panel
- **Status display**: Visual indicators show when auto-refresh is active

---

## 🚀 How to Use

### **Automatic Mode (Recommended)**
1. Start CONJURE in Blender: `3D Viewport > CONJURE > Initiate CONJURE`
2. Auto-refresh starts automatically ✅
3. Watch for console messages: `✅ Backend agent auto-refresh started (every 3 seconds)`

### **Manual Control**
1. In the CONJURE panel, find the **"Backend Agent Context"** section
2. Click **"Start Auto-Refresh"** to begin
3. Click **"Stop Auto-Refresh"** to pause
4. Status shows: `📸 Rendering every 3s` when active

---

## 🔧 Technical Details

### **File Output**
- **Location**: `data/generated_images/gestureCamera/render.png`
- **Format**: PNG, 1024x1024 resolution
- **Camera**: Uses the `GestureCamera` object in your scene
- **Update frequency**: Every 3 seconds

### **Backend Agent Integration**
- **Visual analysis**: Backend agent receives actual images, not text descriptions
- **Real-time context**: AI sees your current 3D model and modifications
- **Instruction generation**: Visual context influences AI decision-making
- **FLUX prompt creation**: AI generates prompts based on what it sees

### **Performance Impact**
- **Minimal overhead**: Uses Blender's efficient timer system
- **Background rendering**: Doesn't interrupt your workflow
- **Smart cleanup**: Automatically stops when CONJURE stops

---

## 🛠️ Implementation Details

### **New Blender Operators**
- `CONJURE_OT_auto_refresh_render`: Start auto-refresh functionality
- `CONJURE_OT_stop_auto_refresh`: Stop auto-refresh functionality

### **Timer System**
```python
# Registers a persistent timer that runs every 3 seconds
bpy.app.timers.register(auto_render_timer, first_interval=2.0, persistent=True)
```

### **Render Logic**
```python
# Uses same render settings as manual renders
context.scene.camera = gesture_camera
context.scene.render.resolution_x = 1024
context.scene.render.resolution_y = 1024
bpy.ops.render.render(write_still=True)
```

---

## 🧪 Testing

### **Test Script**
Run `python test_auto_refresh.py` to verify functionality:
```bash
python test_auto_refresh.py
```

### **Expected Output**
```console
✅ Update #1: Mon Jan 27 19:31:57 2025 (after 3.1s)
✅ Update #2: Mon Jan 27 19:32:00 2025 (after 3.0s)
✅ Update #3: Mon Jan 27 19:32:03 2025 (after 3.2s)
```

### **Manual Verification**
1. Check file timestamps: `data/generated_images/gestureCamera/render.png`
2. Watch Blender console for: `📸 Auto-refresh: GestureCamera rendered`
3. Verify backend agent receives updates in your conversation logs

---

## 🎯 Benefits for Your Workflow

### **Enhanced AI Context**
- **Real-time awareness**: Backend agent sees your current model state
- **Accurate instructions**: AI generates contextually appropriate commands
- **Visual understanding**: Agent can reference specific shapes and features

### **Improved Conversation Flow**
- **Reduced confusion**: Agent always has current visual context
- **Better suggestions**: AI recommendations based on what it actually sees
- **Seamless integration**: No manual render steps required

### **Automatic Operation**
- **Set and forget**: Auto-starts when you begin CONJURE
- **Background operation**: Doesn't interrupt your creative flow
- **Smart cleanup**: Properly stops when session ends

---

## 🔍 Console Messages

### **Startup Messages**
```console
🎬 Auto-starting backend agent context refresh...
✅ Backend agent auto-refresh started (every 3 seconds)
```

### **Render Messages**
```console
📸 Auto-refresh: GestureCamera rendered -> /path/to/render.png
```

### **Shutdown Messages**
```console
🛑 Auto-refresh timer stopped
🛑 Auto-stopped backend agent context refresh
```

---

## 🚨 Troubleshooting

### **Auto-refresh not working**
1. **Check CONJURE is running**: Main operator must be active
2. **Verify GestureCamera exists**: Required camera object in scene
3. **Check console messages**: Look for error or status messages
4. **Manual start**: Use the UI panel to start manually

### **Slow performance**
1. **Check render complexity**: Reduce scene complexity if needed
2. **Verify timer interval**: Should be exactly 3 seconds
3. **Monitor system resources**: Rendering uses GPU/CPU

### **File not updating**
1. **Check file permissions**: Ensure write access to data folder
2. **Verify file path**: `data/generated_images/gestureCamera/render.png`
3. **Check disk space**: Ensure sufficient storage available

---

## 📝 Configuration

### **Timing Adjustment**
To change the 3-second interval, modify the timer return value:
```python
# In auto_render_timer() method
return 3.0  # Change to desired seconds
```

### **Resolution Settings**
Auto-refresh uses 1024x1024 for optimal backend agent processing:
```python
context.scene.render.resolution_x = 1024
context.scene.render.resolution_y = 1024
```

---

## 🎉 Success Indicators

✅ **Auto-refresh is working when you see:**
- Console message: `✅ Backend agent auto-refresh started`
- UI shows: `📸 Rendering every 3s`
- File timestamps update every ~3 seconds
- Backend agent receives visual context in conversations

🎯 **Your backend agent now has real-time visual awareness of your 3D creations!** 