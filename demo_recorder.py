#!/usr/bin/env python3
"""
Constitutional.seq Demo Video Recorder for macOS

Automated demo with built-in screen recording using macOS APIs.
"""

import subprocess
import time
import sys
import os
import signal
from datetime import datetime

def check_dependencies():
    """Check and install required dependencies."""
    deps = ['pyautogui', 'Pillow', 'opencv-python', 'numpy']
    for dep in deps:
        try:
            __import__(dep.replace('-', '_'))
        except ImportError:
            print(f"Installing {dep}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])

check_dependencies()

import pyautogui
import cv2
import numpy as np
from PIL import ImageGrab
import threading

class DemoRecorder:
    def __init__(self, output_file="constitutional_seq_demo.mp4"):
        self.output_file = output_file
        self.recording = False
        self.frames = []
        self.fps = 30
        
        # Configure pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.3
        
    def record_screen(self):
        """Record screen using PIL and OpenCV."""
        # Get screen dimensions
        screen = ImageGrab.grab()
        width, height = screen.size
        
        # Setup video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(self.output_file, fourcc, self.fps, (width, height))
        
        print(f"Recording to {self.output_file}...")
        self.recording = True
        
        while self.recording:
            # Capture screen
            img = ImageGrab.grab()
            frame = np.array(img)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # Write frame
            out.write(frame)
            
            # Control frame rate
            time.sleep(1/self.fps)
        
        out.release()
        print("Recording saved!")
    
    def run_demo_sequence(self):
        """Execute the demo interaction sequence."""
        
        print("Launching Constitutional.seq...")
        gui_process = subprocess.Popen([
            sys.executable, '-m', 'genbank_tool.gui.main_window'
        ])
        
        # Wait for GUI to fully load
        time.sleep(5)
        
        # Demo script with narration
        demo_script = [
            # Introduction
            (2, "hover", (640, 50), "Constitutional.seq - AI-safety inspired sequence selection"),
            
            # Input genes
            (1, "click", (300, 300), "Click in gene input area"),
            (2, "type", "TP53", "Enter tumor suppressor gene TP53"),
            (0.5, "key", "Return", None),
            (2, "type", "BRCA1", "Add breast cancer gene BRCA1"),
            (0.5, "key", "Return", None),
            (2, "type", "VEGFA", "Add VEGFA - complex case with CTG start"),
            (0.5, "key", "Return", None),
            (2, "type", "KRAS", "Add oncogene KRAS"),
            (0.5, "key", "Return", None),
            (2, "type", "EGFR", "Add EGFR receptor"),
            
            # Process
            (2, "move", (150, 700), "Move to Process button"),
            (1, "click", (150, 700), "Click Process Genes"),
            (8, "wait", None, "Processing genes through HGNC → MANE → GenBank pipeline"),
            
            # Show results
            (2, "click", (400, 400), "Select TP53 to view sequence"),
            (3, "wait", None, "Viewing MANE Select transcript with confidence 1.0"),
            
            # Demonstrate tabs
            (2, "click", (720, 85), "Switch to Sequence Viewer"),
            (2, "scroll", -5, "View full CDS sequence"),
            (2, "click", (870, 85), "Open Help documentation"),
            (2, "scroll", -3, "Scroll through documentation"),
            
            # Show AI Safety link
            (2, "move", (600, 790), "AI Safety Book link - promoting safe AI development"),
            
            # Return to results
            (2, "click", (600, 85), "Return to Results Table"),
            
            # Export
            (2, "move", (513, 735), "Export results option"),
            (1, "wait", None, "Demo complete"),
        ]
        
        print("\nExecuting demo sequence...")
        for duration, action, target, narration in demo_script:
            if narration:
                print(f"  → {narration}")
            
            if action == "click" and target:
                pyautogui.click(target[0], target[1])
            elif action == "move" and target:
                pyautogui.moveTo(target[0], target[1], duration=1)
            elif action == "hover" and target:
                pyautogui.moveTo(target[0], target[1], duration=0.5)
            elif action == "type" and target:
                pyautogui.typewrite(target, interval=0.15)
            elif action == "key" and target:
                pyautogui.press(target)
            elif action == "scroll" and target:
                for _ in range(abs(target)):
                    pyautogui.scroll(1 if target > 0 else -1)
                    time.sleep(0.2)
            elif action == "wait":
                pass
            
            time.sleep(duration)
        
        # Clean up
        time.sleep(2)
        gui_process.terminate()
        
    def create_video_with_titles(self):
        """Add title cards and transitions to the video."""
        print("Adding title cards and transitions...")
        
        # This would use moviepy or ffmpeg to add:
        # - Opening title card
        # - Text overlays explaining each step
        # - Closing credits with attribution
        
        cmd = [
            'ffmpeg',
            '-i', self.output_file,
            '-vf', 'fade=in:0:30,fade=out:870:30',
            '-c:v', 'libx264',
            '-crf', '23',
            '-preset', 'medium',
            f'final_{self.output_file}'
        ]
        
        try:
            subprocess.run(cmd, check=True)
            print(f"Final video created: final_{self.output_file}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("ffmpeg not found - skipping post-processing")
    
    def run(self):
        """Main execution flow."""
        print("=" * 60)
        print("Constitutional.seq Automated Demo Recorder")
        print("=" * 60)
        
        print("\nThis will create a video demo showing:")
        print("• Gene name resolution (any format → official)")
        print("• MANE Select identification")
        print("• Confidence scoring system")
        print("• Dark mode interface")
        print("• AI Safety awareness")
        
        input("\nPress Enter to start recording...")
        
        # Start recording in background thread
        record_thread = threading.Thread(target=self.record_screen)
        record_thread.start()
        
        # Give recording a moment to start
        time.sleep(2)
        
        # Run demo
        try:
            self.run_demo_sequence()
        finally:
            # Stop recording
            self.recording = False
            record_thread.join()
        
        # Post-process video
        self.create_video_with_titles()
        
        print("\n" + "=" * 60)
        print("✅ Demo video created successfully!")
        print(f"📹 Output: {self.output_file}")
        print("=" * 60)

if __name__ == "__main__":
    recorder = DemoRecorder()
    recorder.run()