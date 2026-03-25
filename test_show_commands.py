#!/usr/bin/env python3
"""
Test script to show what commands are being generated for a job
"""

import sys
sys.path.insert(0, '/Users/takuyaitabashi/cameo-cut/src')

from gpgl.commands import GPGLCommandBuilder, ToolSettings

# Simulate creating a job like the app does
builder = GPGLCommandBuilder()

# Initialize
builder.set_orientation(False)  # FN0
builder.set_origin(0)           # SO0

# Create tool settings for Tool 2 (pen)
tool = ToolSettings(
    toolholder=2,
    force=10,
    speed=30,  # Max speed
    depth=0,
)

print("Tool settings:")
print(f"  toolholder: {tool.toolholder}")
print(f"  force: {tool.force}")
print(f"  speed: {tool.speed}")
print()

# Apply tool settings
builder.apply_tool_settings(tool)

# Add a simple move and draw
builder.move_to(1000, 1000)
builder.draw_to(2000, 2000)

builder.home()

# Build and show commands
commands = builder.build()

print("Generated commands:")
print(f"Total bytes: {len(commands)}")
print()

# Split by ETX and show each command
cmd_list = commands.split(b'\x03')
for i, cmd in enumerate(cmd_list):
    if cmd:
        cmd_str = cmd.decode('ascii', errors='replace')
        print(f"  [{i:2d}] {cmd_str}")
