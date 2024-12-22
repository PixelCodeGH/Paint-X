# Paint X

A modern, high-performance drawing application built with Python and PySide6. This version represents a complete rewrite of the original Tkinter-based Paint X, offering significant improvements in performance, memory management, and user experience.

## What's New in This Version

### Major Changes
- 🔄 Complete rewrite using PySide6 (Qt) instead of Tkinter
- 🚀 Optimized memory management with tile-based canvas system
- 🎯 Improved drawing performance and responsiveness
- 🖼️ Infinite canvas with dynamic expansion
- 🔍 Enhanced zoom functionality with smoother scaling

### Technical Improvements
- Tile-based canvas system for efficient memory usage
- Dynamic tile management based on zoom level
- Optimized rendering for large canvases
- Improved memory cleanup for unused tiles
- Better handling of large images

### UI Enhancements
- 🎨 Modernized toolbar with intuitive icons
- 📏 Non-linear brush size scaling for better control
- 🎚️ Improved opacity control
- 🌈 Enhanced color selection with quick-access palette
- 🌙 Refined dark mode implementation

## Features

- Drawing Tools:
  - ✏️ Pen Tool
  - 🖌️ Brush Tool
  - ⬜ Rectangle Tool
  - ⭕ Circle Tool
  - 📏 Line Tool
  - 🧽 Eraser Tool

- Canvas Features:
  - 🔄 Infinite canvas with dynamic expansion
  - 🔍 Smooth zooming (Ctrl + Mouse Wheel)
  - 🖱️ Canvas panning (Middle Mouse Button)
  - 💾 Save/Load functionality
  - 🎨 Adjustable brush size and opacity

## Requirements

- Python 3.x
- PySide6
- Pillow

## Installation

### Option 1: Executable Version
Download and run the executable file directly - no installation required!
- Simply download `Paint-X.exe`
- Double-click to run the application
- No Python installation needed

### Option 2: From Source
1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python paint_x.py
```

## Controls

- Left Click: Draw
- Middle Click + Drag: Pan canvas
- Ctrl + Mouse Wheel: Zoom in/out
- Top Toolbar: Access all tools and settings

## Performance Notes

- The new tile-based system optimizes memory usage for large canvases
- Automatic cleanup of unused tiles during extreme zoom levels
- Dynamic tile limit adjustment based on zoom level
- Optimized rendering for better performance

## Comparison with Previous Version

### Advantages
- Better performance with large canvases
- More efficient memory management
- Smoother zooming and panning
- Modern Qt-based interface
- Better tool organization
- Enhanced brush size control

### Changes
- Removed fill tool (to be added in future updates)
- Changed from Tkinter to PySide6
- New tile-based architecture
- Modernized UI layout

## Future Plans

- Additional tools (Fill, Text, etc.)
- Layer support
- More export options
- Brush presets
- Custom tool settings

## License

MIT License 