#!/usr/bin/env python3
"""
Constitutional.seq Demo Video Creator

This script automates the GUI to create a demo video showing all features.
Requires: pyautogui, Pillow
On macOS: Also requires screen recording permission
"""

import subprocess
import time
import sys
import os
from pathlib import Path

try:
    import pyautogui
except ImportError:
    print("Installing pyautogui...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyautogui", "Pillow"])
    import pyautogui

# Configure pyautogui
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5

def start_screen_recording(output_file="constitutional_seq_demo.mov"):
    """Start screen recording using macOS built-in screencapture."""
    print("Starting screen recording...")
    # Use screencapture command (macOS)
    # Note: This will record the entire screen
    cmd = [
        'screencapture',
        '-v',  # Video mode
        '-x',  # No sound  
        output_file
    ]
    process = subprocess.Popen(cmd)
    return process

def start_quicktime_recording():
    """Alternative: Use AppleScript to control QuickTime."""
    script = '''
    tell application "QuickTime Player"
        activate
        new screen recording
        tell front document
            start
        end tell
    end tell
    '''
    subprocess.run(['osascript', '-e', script])

def run_demo():
    """Run the automated demo sequence."""
    
    print("Launching Constitutional.seq...")
    # Launch the GUI
    gui_process = subprocess.Popen([
        sys.executable, '-m', 'genbank_tool.gui.main_window'
    ])
    
    # Wait for GUI to load
    time.sleep(5)
    
    print("Starting demo sequence...")
    
    # Get screen size
    screen_width, screen_height = pyautogui.size()
    
    # Demo sequence
    demo_steps = [
        ("Moving to input area...", lambda: pyautogui.moveTo(300, 300, duration=1)),
        ("Typing test genes...", lambda: type_with_style("TP53\nBRCA1\nVEGFA\nKRAS\nEGFR")),
        ("Moving to Process button...", lambda: pyautogui.moveTo(150, 700, duration=1)),
        ("Clicking Process Genes...", lambda: pyautogui.click()),
        ("Waiting for processing...", lambda: time.sleep(8)),
        ("Selecting first result...", lambda: pyautogui.click(400, 400)),
        ("Waiting to show sequence...", lambda: time.sleep(3)),
        ("Switching to Help tab...", lambda: pyautogui.click(870, 85)),
        ("Scrolling help content...", lambda: smooth_scroll(5)),
        ("Returning to results...", lambda: pyautogui.click(600, 85)),
        ("Opening export menu...", lambda: pyautogui.click(500, 735)),
    ]
    
    for description, action in demo_steps:
        print(f"  {description}")
        action()
        time.sleep(1)
    
    print("Demo sequence complete!")
    
    # Keep GUI open for a moment
    time.sleep(3)
    
    # Close GUI
    gui_process.terminate()
    
def type_with_style(text, interval=0.1):
    """Type text with realistic typing speed."""
    pyautogui.typewrite(text, interval=interval)

def smooth_scroll(times=3):
    """Smooth scrolling animation."""
    for _ in range(times):
        pyautogui.scroll(-3)
        time.sleep(0.5)

def create_title_card():
    """Create a title card image for the video."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Create image
        img = Image.new('RGB', (1920, 1080), color='#1e1e1e')
        draw = ImageDraw.Draw(img)
        
        # Try to use a nice font, fallback to default
        try:
            title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 80)
            subtitle_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
        except:
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
        
        # Add text
        draw.text((960, 400), "Constitutional.seq", 
                  font=title_font, fill='#4fc3f7', anchor='mm')
        draw.text((960, 500), "Principle-based Canonical Sequence Selection", 
                  font=subtitle_font, fill='#e0e0e0', anchor='mm')
        draw.text((960, 600), "Developed with Claude Opus 4", 
                  font=subtitle_font, fill='#b0b0b0', anchor='mm')
        
        # Save
        img.save('title_card.png')
        print("Created title card: title_card.png")
        
    except ImportError:
        print("Pillow not installed, skipping title card")

def main():
    """Main demo creation workflow."""
    
    print("=" * 50)
    print("Constitutional.seq Demo Creator")
    print("=" * 50)
    
    # Create title card
    create_title_card()
    
    print("\nThis script will:")
    print("1. Launch Constitutional.seq")
    print("2. Automatically interact with the GUI")
    print("3. Demonstrate key features")
    print("\nMAKE SURE TO:")
    print("- Start screen recording manually (QuickTime or OBS)")
    print("- Position the window properly")
    print("- Stop recording when 'Demo complete' appears")
    
    input("\nPress Enter when ready to start...")
    
    # Run the demo
    run_demo()
    
    print("\n" + "=" * 50)
    print("Demo complete!")
    print("Remember to stop your screen recording")
    print("=" * 50)
    
    # Optional: Convert video format
    print("\nTo convert video (if needed):")
    print("ffmpeg -i recording.mov -c:v libx264 -crf 23 -preset medium demo.mp4")

if __name__ == "__main__":
    main()