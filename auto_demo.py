#!/usr/bin/env python3
"""
Automatic Constitutional.seq Demo - No user input needed
Just start your screen recording and run this script!
"""

import subprocess
import time
import sys

try:
    import pyautogui
except ImportError:
    print("pyautogui not installed, skipping import")
    sys.exit(1)

# Settings
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5
TYPING_SPEED = 0.12

def narrate(text):
    """Print narration for the demo."""
    print(f"\n>>> {text}")
    time.sleep(1)

def main():
    print("=" * 60)
    print("CONSTITUTIONAL.SEQ AUTOMATIC DEMO")
    print("=" * 60)
    print("\nStarting in 5 seconds...")
    print("Make sure your screen recording is running!")
    
    # Countdown
    for i in range(5, 0, -1):
        print(f"{i}...")
        time.sleep(1)
    
    print("\nStarting demo!")
    
    # Launch GUI
    narrate("Launching Constitutional.seq...")
    gui = subprocess.Popen([sys.executable, '-m', 'genbank_tool.gui.main_window'])
    time.sleep(5)
    
    # Click in text area (adjust coordinates as needed)
    narrate("Entering gene names - accepts any format...")
    pyautogui.click(300, 300)
    
    # Type genes with explanation
    narrate("TP53 - Tumor suppressor, most studied human gene")
    pyautogui.typewrite("TP53", interval=TYPING_SPEED)
    pyautogui.press('enter')
    time.sleep(0.5)
    
    narrate("BRCA1 - Breast cancer susceptibility gene")
    pyautogui.typewrite("BRCA1", interval=TYPING_SPEED)
    pyautogui.press('enter')
    time.sleep(0.5)
    
    narrate("VEGFA - Complex case with alternative start codons")
    pyautogui.typewrite("VEGFA", interval=TYPING_SPEED)
    pyautogui.press('enter')
    time.sleep(0.5)
    
    narrate("PKM - Pyruvate kinase, metabolic enzyme")
    pyautogui.typewrite("PKM", interval=TYPING_SPEED)
    pyautogui.press('enter')
    time.sleep(0.5)
    
    narrate("CD19 - Immunotherapy target")
    pyautogui.typewrite("CD19", interval=TYPING_SPEED)
    
    time.sleep(2)
    
    # Process genes
    narrate("Processing through HGNC → MANE → GenBank pipeline...")
    pyautogui.moveTo(150, 700, duration=1)
    pyautogui.click()
    
    # Wait for processing
    narrate("Retrieving sequences from NCBI...")
    time.sleep(10)
    
    # Click on first result
    narrate("Selecting TP53 to view sequence details...")
    pyautogui.click(400, 400)
    time.sleep(3)
    
    # Switch to sequence viewer
    narrate("Viewing the full CDS sequence...")
    pyautogui.click(720, 85)
    time.sleep(2)
    
    # Scroll sequence
    pyautogui.scroll(-5)
    time.sleep(2)
    
    # Go to help
    narrate("Comprehensive help documentation...")
    pyautogui.click(870, 85)
    time.sleep(2)
    
    # Scroll help
    pyautogui.scroll(-5)
    time.sleep(2)
    pyautogui.scroll(-5)
    time.sleep(2)
    
    # Back to results
    narrate("Results show confidence scores and selection methods...")
    pyautogui.click(600, 85)
    time.sleep(2)
    
    # Hover over AI safety link
    narrate("Promoting AI safety awareness...")
    pyautogui.moveTo(600, 790, duration=1)
    time.sleep(2)
    
    # Move to export
    narrate("Export results for downstream analysis...")
    pyautogui.moveTo(513, 735, duration=1)
    time.sleep(2)
    
    narrate("Demo complete - Constitutional.seq")
    time.sleep(3)
    
    # Close GUI
    gui.terminate()
    
    print("\n" + "=" * 60)
    print("✅ DEMO COMPLETE!")
    print("⏹️  Stop your screen recording now")
    print("💾 Save your video")
    print("=" * 60)

if __name__ == "__main__":
    main()