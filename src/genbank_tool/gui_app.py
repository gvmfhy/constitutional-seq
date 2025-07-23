#!/usr/bin/env python3
"""GUI application entry point for GenBank Tool."""

import sys
from PyQt5.QtWidgets import QApplication
from genbank_tool.gui.main_window import GenBankToolGUI


def main():
    """Main entry point for GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("GenBank Tool")
    app.setOrganizationName("GenBankTool")
    
    # Set application style (optional)
    app.setStyle('Fusion')  # Modern look
    
    # Create and show main window
    window = GenBankToolGUI()
    window.show()
    
    # Run application
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()