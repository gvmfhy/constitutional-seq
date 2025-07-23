"""Main window for GenBank Tool GUI."""

import sys
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QTextEdit,
    QLabel, QProgressBar, QFileDialog, QMessageBox,
    QSplitter, QGroupBox, QTabWidget, QToolBar,
    QAction, QMenuBar, QMenu, QStatusBar, QHeaderView,
    QCheckBox, QSpinBox, QComboBox, QLineEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings
from PyQt5.QtGui import QIcon, QFont, QDragEnterEvent, QDropEvent

from ..gene_resolver import GeneResolver
from ..sequence_retriever import SequenceRetriever
from ..transcript_selector import TranscriptSelector
from ..data_validator import DataValidator
from ..output_formatter import OutputFormatter
from ..error_handler import get_error_handler, ErrorType
from ..logging_config import setup_logging


class ProcessingThread(QThread):
    """Thread for processing genes without blocking the GUI."""
    
    # Signals
    progress = pyqtSignal(int, int)  # current, total
    status_update = pyqtSignal(str)  # status message
    gene_processed = pyqtSignal(dict)  # result dict
    error_occurred = pyqtSignal(str, str)  # gene, error message
    finished_all = pyqtSignal()
    
    def __init__(self, genes: List[str], config: Dict[str, Any]):
        super().__init__()
        self.genes = genes
        self.config = config
        self._is_cancelled = False
        
        # Initialize components
        self.resolver = GeneResolver(
            api_key=config.get('ncbi_api_key'),
            cache_enabled=config.get('use_cache', True)
        )
        self.retriever = SequenceRetriever(
            api_key=config.get('ncbi_api_key'),
            email=config.get('email', 'user@example.com'),
            cache_enabled=config.get('use_cache', True)
        )
        self.selector = TranscriptSelector()
        self.validator = DataValidator() if config.get('validate', False) else None
        self.error_handler = get_error_handler()
    
    def cancel(self):
        """Cancel processing."""
        self._is_cancelled = True
    
    def run(self):
        """Process genes in thread."""
        total = len(self.genes)
        
        for i, gene_name in enumerate(self.genes):
            if self._is_cancelled:
                break
            
            self.progress.emit(i + 1, total)
            self.status_update.emit(f"Processing {gene_name}...")
            
            try:
                # Resolve gene
                resolved = self.resolver.resolve(gene_name)
                if not resolved:
                    raise ValueError(f"Gene not found: {gene_name}")
                
                # Get sequences
                selection = self.retriever.get_canonical_transcript(
                    resolved.official_symbol,
                    resolved.gene_id,
                    user_preference=self.config.get('prefer_transcript')
                )
                
                if not selection:
                    raise ValueError(f"No sequences found for {gene_name}")
                
                # Validate if requested
                validation = None
                if self.validator:
                    validation = self.validator.validate_sequence(
                        selection.transcript,
                        resolved.official_symbol
                    )
                
                # Emit result
                result = {
                    'input_name': gene_name,
                    'official_symbol': resolved.official_symbol,
                    'gene_id': resolved.gene_id,
                    'accession': selection.transcript.accession,
                    'version': selection.transcript.version,
                    'length': len(selection.transcript.cds_sequence),
                    'sequence': selection.transcript.cds_sequence,
                    'url': selection.transcript.genbank_url,
                    'selection_method': selection.method.value,
                    'confidence': selection.confidence,
                    'validation': validation,
                    'warnings': selection.warnings
                }
                
                self.gene_processed.emit(result)
                
            except Exception as e:
                self.error_handler.handle_error(
                    e,
                    operation="process_gene",
                    item_id=gene_name
                )
                self.error_occurred.emit(gene_name, str(e))
        
        if not self._is_cancelled:
            self.finished_all.emit()


class GenBankToolGUI(QMainWindow):
    """Main GUI window for GenBank Tool."""
    
    def __init__(self):
        super().__init__()
        self.settings = QSettings('GenBankTool', 'GUI')
        self.processing_thread = None
        self.results = []
        
        # Setup logging
        setup_logging(log_level="INFO", log_dir=".genbank_gui_logs")
        
        self.init_ui()
        self.load_settings()
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("NCBI GenBank CDS Retrieval Tool")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create toolbar
        self.create_toolbar()
        
        # Create main content area
        content_splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Input
        left_panel = self.create_input_panel()
        content_splitter.addWidget(left_panel)
        
        # Right panel - Results
        right_panel = self.create_results_panel()
        content_splitter.addWidget(right_panel)
        
        content_splitter.setSizes([400, 800])
        main_layout.addWidget(content_splitter)
        
        # Bottom panel - Status and progress
        bottom_panel = self.create_status_panel()
        main_layout.addWidget(bottom_panel)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def create_menu_bar(self):
        """Create application menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        open_action = QAction('Open Gene List...', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        save_action = QAction('Save Results...', self)
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self.save_results)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu('Edit')
        
        clear_input_action = QAction('Clear Input', self)
        clear_input_action.triggered.connect(self.clear_input)
        edit_menu.addAction(clear_input_action)
        
        clear_results_action = QAction('Clear Results', self)
        clear_results_action.triggered.connect(self.clear_results)
        edit_menu.addAction(clear_results_action)
        
        # Tools menu
        tools_menu = menubar.addMenu('Tools')
        
        settings_action = QAction('Settings...', self)
        settings_action.triggered.connect(self.show_settings)
        tools_menu.addAction(settings_action)
        
        cache_action = QAction('Manage Cache...', self)
        cache_action.triggered.connect(self.manage_cache)
        tools_menu.addAction(cache_action)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        
        about_action = QAction('About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_toolbar(self):
        """Create application toolbar."""
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        # Process button
        self.process_action = QAction('Process Genes', self)
        self.process_action.triggered.connect(self.process_genes)
        toolbar.addAction(self.process_action)
        
        # Stop button
        self.stop_action = QAction('Stop', self)
        self.stop_action.triggered.connect(self.stop_processing)
        self.stop_action.setEnabled(False)
        toolbar.addAction(self.stop_action)
        
        toolbar.addSeparator()
        
        # Quick settings
        self.canonical_checkbox = QCheckBox('Canonical Only')
        self.canonical_checkbox.setChecked(True)
        toolbar.addWidget(self.canonical_checkbox)
        
        self.validate_checkbox = QCheckBox('Validate')
        toolbar.addWidget(self.validate_checkbox)
        
        toolbar.addSeparator()
        
        # Workers spinbox
        toolbar.addWidget(QLabel('Workers:'))
        self.workers_spinbox = QSpinBox()
        self.workers_spinbox.setMinimum(1)
        self.workers_spinbox.setMaximum(10)
        self.workers_spinbox.setValue(5)
        toolbar.addWidget(self.workers_spinbox)
    
    def create_input_panel(self) -> QWidget:
        """Create the input panel."""
        panel = QGroupBox("Input Genes")
        layout = QVBoxLayout(panel)
        
        # Instructions
        instructions = QLabel("Enter gene names (one per line) or drag & drop a file:")
        layout.addWidget(instructions)
        
        # Text input area
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("BRCA1\nTP53\nEGFR\n...")
        self.input_text.setAcceptDrops(True)
        layout.addWidget(self.input_text)
        
        # File controls
        file_layout = QHBoxLayout()
        
        self.file_button = QPushButton("Load from File")
        self.file_button.clicked.connect(self.open_file)
        file_layout.addWidget(self.file_button)
        
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_input)
        file_layout.addWidget(self.clear_button)
        
        layout.addLayout(file_layout)
        
        # Gene count
        self.gene_count_label = QLabel("0 genes")
        layout.addWidget(self.gene_count_label)
        
        # Connect text change signal
        self.input_text.textChanged.connect(self.update_gene_count)
        
        return panel
    
    def create_results_panel(self) -> QWidget:
        """Create the results panel."""
        panel = QGroupBox("Results")
        layout = QVBoxLayout(panel)
        
        # Results tabs
        self.results_tabs = QTabWidget()
        
        # Results table
        self.results_table = QTableWidget()
        self.setup_results_table()
        self.results_tabs.addTab(self.results_table, "Results Table")
        
        # Sequence viewer
        self.sequence_viewer = QTextEdit()
        self.sequence_viewer.setReadOnly(True)
        self.sequence_viewer.setFont(QFont("Courier", 10))
        self.results_tabs.addTab(self.sequence_viewer, "Sequence Viewer")
        
        # Error log
        self.error_log = QTextEdit()
        self.error_log.setReadOnly(True)
        self.results_tabs.addTab(self.error_log, "Errors")
        
        layout.addWidget(self.results_tabs)
        
        # Export controls
        export_layout = QHBoxLayout()
        
        export_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(['TSV', 'CSV', 'Excel', 'JSON'])
        export_layout.addWidget(self.format_combo)
        
        self.export_button = QPushButton("Export Results")
        self.export_button.clicked.connect(self.save_results)
        self.export_button.setEnabled(False)
        export_layout.addWidget(self.export_button)
        
        export_layout.addStretch()
        
        layout.addLayout(export_layout)
        
        return panel
    
    def setup_results_table(self):
        """Setup the results table columns."""
        headers = [
            'Input Name', 'Official Symbol', 'Gene ID', 
            'Accession', 'Version', 'Length', 
            'Selection Method', 'Confidence', 'Status'
        ]
        
        self.results_table.setColumnCount(len(headers))
        self.results_table.setHorizontalHeaderLabels(headers)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.itemSelectionChanged.connect(self.on_result_selected)
    
    def create_status_panel(self) -> QWidget:
        """Create the status panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("Ready to process genes")
        layout.addWidget(self.status_label)
        
        return panel
    
    def update_gene_count(self):
        """Update the gene count label."""
        text = self.input_text.toPlainText().strip()
        if text:
            genes = [g.strip() for g in text.split('\n') if g.strip()]
            self.gene_count_label.setText(f"{len(genes)} genes")
        else:
            self.gene_count_label.setText("0 genes")
    
    def open_file(self):
        """Open a file dialog to load gene list."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open Gene List",
            "",
            "Text Files (*.txt);;CSV Files (*.csv);;All Files (*.*)"
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    content = f.read()
                self.input_text.setPlainText(content)
                self.status_bar.showMessage(f"Loaded {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {e}")
    
    def clear_input(self):
        """Clear the input text area."""
        self.input_text.clear()
    
    def clear_results(self):
        """Clear all results."""
        self.results_table.setRowCount(0)
        self.sequence_viewer.clear()
        self.error_log.clear()
        self.results = []
        self.export_button.setEnabled(False)
    
    def process_genes(self):
        """Start processing genes."""
        # Get gene list
        text = self.input_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Warning", "Please enter gene names to process.")
            return
        
        genes = [g.strip() for g in text.split('\n') if g.strip()]
        
        # Clear previous results
        self.clear_results()
        
        # Prepare configuration
        config = {
            'ncbi_api_key': self.settings.value('ncbi_api_key', ''),
            'email': self.settings.value('email', 'user@example.com'),
            'use_cache': self.settings.value('use_cache', True),
            'canonical_only': self.canonical_checkbox.isChecked(),
            'validate': self.validate_checkbox.isChecked(),
            'workers': self.workers_spinbox.value()
        }
        
        # Create and start processing thread
        self.processing_thread = ProcessingThread(genes, config)
        self.processing_thread.progress.connect(self.update_progress)
        self.processing_thread.status_update.connect(self.update_status)
        self.processing_thread.gene_processed.connect(self.add_result)
        self.processing_thread.error_occurred.connect(self.add_error)
        self.processing_thread.finished_all.connect(self.processing_finished)
        
        # Update UI state
        self.process_action.setEnabled(False)
        self.stop_action.setEnabled(True)
        self.progress_bar.setMaximum(len(genes))
        self.progress_bar.setValue(0)
        
        # Start processing
        self.processing_thread.start()
    
    def stop_processing(self):
        """Stop the processing thread."""
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.cancel()
            self.status_label.setText("Stopping...")
    
    def update_progress(self, current: int, total: int):
        """Update progress bar."""
        self.progress_bar.setValue(current)
    
    def update_status(self, message: str):
        """Update status label."""
        self.status_label.setText(message)
    
    def add_result(self, result: dict):
        """Add a result to the table."""
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)
        
        # Populate columns
        self.results_table.setItem(row, 0, QTableWidgetItem(result['input_name']))
        self.results_table.setItem(row, 1, QTableWidgetItem(result['official_symbol']))
        self.results_table.setItem(row, 2, QTableWidgetItem(result['gene_id']))
        self.results_table.setItem(row, 3, QTableWidgetItem(result['accession']))
        self.results_table.setItem(row, 4, QTableWidgetItem(str(result['version'])))
        self.results_table.setItem(row, 5, QTableWidgetItem(str(result['length'])))
        self.results_table.setItem(row, 6, QTableWidgetItem(result['selection_method']))
        self.results_table.setItem(row, 7, QTableWidgetItem(f"{result['confidence']:.2f}"))
        self.results_table.setItem(row, 8, QTableWidgetItem("✓ Success"))
        
        # Color code success
        for col in range(self.results_table.columnCount()):
            self.results_table.item(row, col).setBackground(Qt.lightGray)
        
        # Store full result
        self.results.append(result)
        self.export_button.setEnabled(True)
    
    def add_error(self, gene_name: str, error_message: str):
        """Add an error to the table and log."""
        # Add to table
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)
        
        self.results_table.setItem(row, 0, QTableWidgetItem(gene_name))
        self.results_table.setItem(row, 8, QTableWidgetItem(f"✗ {error_message}"))
        
        # Color code error
        for col in range(self.results_table.columnCount()):
            item = self.results_table.item(row, col)
            if item:
                item.setBackground(Qt.red)
        
        # Add to error log
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.error_log.append(f"[{timestamp}] {gene_name}: {error_message}\n")
    
    def processing_finished(self):
        """Handle processing completion."""
        self.process_action.setEnabled(True)
        self.stop_action.setEnabled(False)
        self.status_label.setText(f"Processing complete. {len(self.results)} successful results.")
        
        # Show summary
        total = self.results_table.rowCount()
        successful = len(self.results)
        failed = total - successful
        
        QMessageBox.information(
            self,
            "Processing Complete",
            f"Total genes: {total}\n"
            f"Successful: {successful}\n"
            f"Failed: {failed}"
        )
    
    def on_result_selected(self):
        """Handle result selection in table."""
        selected = self.results_table.selectedItems()
        if not selected:
            return
        
        row = selected[0].row()
        if row < len(self.results):
            result = self.results[row]
            
            # Display sequence
            sequence = result['sequence']
            formatted = '\n'.join([sequence[i:i+60] for i in range(0, len(sequence), 60)])
            
            info = f">{result['accession']}.{result['version']} {result['official_symbol']}\n"
            info += f"Length: {len(sequence)} bp\n"
            info += f"Selection: {result['selection_method']} (confidence: {result['confidence']:.2f})\n"
            if result.get('warnings'):
                info += f"Warnings: {', '.join(result['warnings'])}\n"
            info += f"\n{formatted}"
            
            self.sequence_viewer.setText(info)
    
    def save_results(self):
        """Save results to file."""
        if not self.results:
            QMessageBox.warning(self, "Warning", "No results to save.")
            return
        
        format_map = {
            'TSV': ('Tab-separated values (*.tsv)', 'tsv'),
            'CSV': ('Comma-separated values (*.csv)', 'csv'),
            'Excel': ('Excel files (*.xlsx)', 'excel'),
            'JSON': ('JSON files (*.json)', 'json')
        }
        
        format_name = self.format_combo.currentText()
        file_filter, format_type = format_map[format_name]
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Results",
            f"genbank_results.{format_type.split('.')[-1]}",
            file_filter
        )
        
        if filename:
            try:
                formatter = OutputFormatter()
                
                # Convert results to formatter format
                formatted_results = []
                for r in self.results:
                    formatted = {
                        'Input Name': r['input_name'],
                        'Official Symbol': r['official_symbol'],
                        'Gene ID': r['gene_id'],
                        'RefSeq Accession': f"{r['accession']}.{r['version']}",
                        'GenBank URL': r['url'],
                        'CDS Length': r['length'],
                        'CDS Sequence': r['sequence'],
                        'Selection Method': r['selection_method'],
                        'Confidence Score': f"{r['confidence']:.2f}",
                        'Warnings': '; '.join(r.get('warnings', []))
                    }
                    formatted_results.append(formatted)
                
                formatter.format_results(
                    formatted_results,
                    filename,
                    format=format_type
                )
                
                self.status_bar.showMessage(f"Results saved to {filename}")
                QMessageBox.information(self, "Success", f"Results saved to {filename}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save results: {e}")
    
    def show_settings(self):
        """Show settings dialog."""
        from .settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec_():
            # Settings were updated
            pass
    
    def manage_cache(self):
        """Show cache management dialog."""
        from .cache_dialog import CacheDialog
        dialog = CacheDialog(self)
        dialog.exec_()
    
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About GenBank Tool",
            "NCBI GenBank CDS Retrieval Tool\n\n"
            "Version 1.0.0\n\n"
            "A tool for automated retrieval of coding sequences\n"
            "from NCBI GenBank for mRNA therapeutic development.\n\n"
            "© 2024 - Created with PyQt5"
        )
    
    def load_settings(self):
        """Load saved settings."""
        # Window geometry
        geometry = self.settings.value('geometry')
        if geometry:
            self.restoreGeometry(geometry)
        
        # Other settings
        self.canonical_checkbox.setChecked(
            self.settings.value('canonical_only', True, type=bool)
        )
        self.validate_checkbox.setChecked(
            self.settings.value('validate', False, type=bool)
        )
        self.workers_spinbox.setValue(
            self.settings.value('workers', 5, type=int)
        )
    
    def closeEvent(self, event):
        """Save settings on close."""
        # Stop any running threads
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.cancel()
            self.processing_thread.wait()
        
        # Save settings
        self.settings.setValue('geometry', self.saveGeometry())
        self.settings.setValue('canonical_only', self.canonical_checkbox.isChecked())
        self.settings.setValue('validate', self.validate_checkbox.isChecked())
        self.settings.setValue('workers', self.workers_spinbox.value())
        
        event.accept()


def main():
    """Main entry point for GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("GenBank Tool")
    app.setOrganizationName("GenBankTool")
    
    window = GenBankToolGUI()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    main()