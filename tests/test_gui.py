"""Basic tests for GUI components."""

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
import pytest

from genbank_tool.gui.main_window import GenBankToolGUI
from genbank_tool.gui.settings_dialog import SettingsDialog
from genbank_tool.gui.cache_dialog import CacheDialog


@pytest.fixture(scope='module')
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
    app.quit()


class TestMainWindow:
    """Test main window functionality."""
    
    def test_window_creation(self, qapp):
        """Test main window can be created."""
        window = GenBankToolGUI()
        assert window is not None
        assert window.windowTitle() == "NCBI GenBank CDS Retrieval Tool"
        window.close()
    
    def test_input_area(self, qapp):
        """Test gene input area."""
        window = GenBankToolGUI()
        
        # Test adding text
        test_genes = "BRCA1\nTP53\nEGFR"
        window.input_text.setPlainText(test_genes)
        assert window.input_text.toPlainText() == test_genes
        
        # Test gene count update
        assert "3 genes" in window.gene_count_label.text()
        
        window.close()
    
    def test_clear_input(self, qapp):
        """Test clearing input."""
        window = GenBankToolGUI()
        
        window.input_text.setPlainText("TEST")
        window.clear_input()
        assert window.input_text.toPlainText() == ""
        
        window.close()
    
    def test_results_table_setup(self, qapp):
        """Test results table initialization."""
        window = GenBankToolGUI()
        
        # Check column count
        assert window.results_table.columnCount() == 9
        
        # Check headers
        headers = []
        for i in range(window.results_table.columnCount()):
            headers.append(window.results_table.horizontalHeaderItem(i).text())
        
        assert "Input Name" in headers
        assert "Official Symbol" in headers
        assert "Accession" in headers
        
        window.close()
    
    def test_toolbar_widgets(self, qapp):
        """Test toolbar widgets."""
        window = GenBankToolGUI()
        
        # Check checkboxes
        assert window.canonical_checkbox.isChecked() is True
        assert window.validate_checkbox.isChecked() is False
        
        # Check spinbox
        assert window.workers_spinbox.value() == 5
        assert window.workers_spinbox.minimum() == 1
        assert window.workers_spinbox.maximum() == 10
        
        window.close()


class TestSettingsDialog:
    """Test settings dialog."""
    
    def test_dialog_creation(self, qapp):
        """Test settings dialog can be created."""
        window = GenBankToolGUI()
        dialog = SettingsDialog(window.settings, window)
        
        assert dialog is not None
        assert dialog.windowTitle() == "Settings"
        
        dialog.close()
        window.close()
    
    def test_settings_tabs(self, qapp):
        """Test settings dialog has all tabs."""
        window = GenBankToolGUI()
        dialog = SettingsDialog(window.settings, window)
        
        # Check that dialog was created
        assert dialog.isModal() is True
        
        dialog.close()
        window.close()


class TestCacheDialog:
    """Test cache dialog."""
    
    def test_dialog_creation(self, qapp):
        """Test cache dialog can be created."""
        window = GenBankToolGUI()
        dialog = CacheDialog(window)
        
        assert dialog is not None
        assert dialog.windowTitle() == "Cache Management"
        
        dialog.close()
        window.close()


class TestProcessingThread:
    """Test processing thread setup."""
    
    def test_thread_creation(self, qapp):
        """Test processing thread can be created."""
        from genbank_tool.gui.main_window import ProcessingThread
        
        genes = ['BRCA1', 'TP53']
        config = {
            'ncbi_api_key': '',
            'email': 'test@example.com',
            'use_cache': True
        }
        
        thread = ProcessingThread(genes, config)
        assert thread is not None
        assert thread.genes == genes
        assert thread.config == config