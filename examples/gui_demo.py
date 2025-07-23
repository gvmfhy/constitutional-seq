#!/usr/bin/env python3
"""Demo script for the GenBank Tool GUI."""

import sys
import time
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

from genbank_tool.gui.main_window import GenBankToolGUI


def demo_gui():
    """Run a demonstration of the GUI features."""
    app = QApplication(sys.argv)
    app.setApplicationName("GenBank Tool Demo")
    
    # Create main window
    window = GenBankToolGUI()
    window.show()
    
    # Add some sample genes
    sample_genes = """BRCA1
TP53
EGFR
KRAS
MYC
VEGFA
PTEN
RB1
"""
    
    # Simulate user interaction
    QTimer.singleShot(1000, lambda: window.input_text.setPlainText(sample_genes))
    QTimer.singleShot(2000, lambda: window.status_bar.showMessage("Demo: Added sample genes"))
    
    # Show different tabs
    QTimer.singleShot(3000, lambda: window.results_tabs.setCurrentIndex(1))  # Sequence viewer
    QTimer.singleShot(4000, lambda: window.results_tabs.setCurrentIndex(2))  # Error log
    QTimer.singleShot(5000, lambda: window.results_tabs.setCurrentIndex(0))  # Back to results
    
    # Update status
    QTimer.singleShot(6000, lambda: window.status_bar.showMessage(
        "Demo complete - try processing these genes!"
    ))
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    print("Starting GenBank Tool GUI Demo...")
    print("The GUI will open and demonstrate various features.")
    print("Close the window when done.")
    demo_gui()