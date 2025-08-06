"""Constitutional.seq - Principle-based canonical sequence selection.

This tool was developed through AI-human collaboration using Claude Opus 4.
The implementation demonstrates "vibe coding" - a fluid collaboration between
human domain expertise and AI capabilities.

The name "Constitutional.seq" reflects both Anthropic's Constitutional AI approach
and the biological concept of essential, foundational sequences.
"""

import sys
import json
import re
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QTextEdit, QTextBrowser,
    QLabel, QProgressBar, QFileDialog, QMessageBox,
    QSplitter, QGroupBox, QTabWidget, QToolBar,
    QAction, QMenuBar, QMenu, QStatusBar, QHeaderView,
    QCheckBox, QSpinBox, QComboBox, QLineEdit, QApplication
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
            cache_enabled=config.get('use_cache', True),
            uniprot_first=config.get('uniprot_first', False)
        )
        self.retriever = SequenceRetriever(
            api_key=config.get('ncbi_api_key'),
            email=config.get('email', 'user@example.com'),
            cache_enabled=config.get('use_cache', True)
        )
        self.selector = TranscriptSelector()
        self.validator = DataValidator()  # Always validate by default
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
                    user_preference=self.config.get('prefer_transcript'),
                    resolved_gene=resolved
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
                    'full_gene_name': selection.transcript.full_gene_name or resolved.description,
                    'gene_id': resolved.gene_id,
                    'gene_url': selection.transcript.gene_url,
                    'accession': selection.transcript.accession,
                    'isoform': selection.transcript.isoform,
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
        self.setWindowTitle("Constitutional.seq")
        self.setGeometry(100, 100, 1200, 800)
        
        # Apply dark theme
        self.apply_dark_theme()
        
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
        
        # Removed UniProt First toggle - HGNC now handles all name resolution
    
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
        
        # Add prominent Process Genes button
        self.process_button = QPushButton("🧬 Process Genes")
        self.process_button.setObjectName("processButton")  # For dark theme styling
        self.process_button.clicked.connect(self.process_genes)
        self.process_button.setToolTip("Process the genes listed above to retrieve their CDS sequences")
        layout.addWidget(self.process_button)
        
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
        self.sequence_viewer = QTextBrowser()
        self.sequence_viewer.setReadOnly(True)
        self.sequence_viewer.setFont(QFont("Courier", 10))
        self.sequence_viewer.setOpenExternalLinks(True)
        self.results_tabs.addTab(self.sequence_viewer, "Sequence Viewer")
        
        # Error log
        self.error_log = QTextEdit()
        self.error_log.setReadOnly(True)
        self.results_tabs.addTab(self.error_log, "Errors")
        
        # Help/Instructions tab
        self.help_text = QTextBrowser()
        self.help_text.setReadOnly(True)
        self.help_text.setOpenExternalLinks(True)
        self.setup_help_content()
        self.results_tabs.addTab(self.help_text, "Help")
        
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
            'Input Name', 'Official Symbol', 'Full Gene Name',
            'Gene ID', 'Gene URL', 'Accession', 'Isoform', 'Version', 
            'Length', 'Selection Method', 'Confidence', 'Status'
        ]
        
        self.results_table.setColumnCount(len(headers))
        self.results_table.setHorizontalHeaderLabels(headers)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.itemSelectionChanged.connect(self.on_result_selected)
    
    def setup_help_content(self):
        """Setup help content by loading from markdown file."""
        help_file = Path(__file__).parent / "help_content.md"
        
        try:
            with open(help_file, 'r', encoding='utf-8') as f:
                markdown_content = f.read()
            
            # Convert markdown to HTML
            if MARKDOWN_AVAILABLE:
                html_content = markdown.markdown(
                    markdown_content, 
                    extensions=['tables', 'fenced_code', 'toc']
                )
            else:
                # Simple fallback conversion for basic markdown
                html_content = self._simple_markdown_to_html(markdown_content)
            
            # Add CSS styling for dark mode
            styled_html = f"""
            <html>
            <head>
                <style>
                    body {{ 
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; 
                        margin: 25px 35px; 
                        line-height: 1.75; 
                        color: #e0e0e0;
                        background-color: #1e1e1e;
                        font-size: 14px;
                    }}
                    h1 {{ 
                        color: #4fc3f7; 
                        border-bottom: 3px solid #4fc3f7; 
                        padding-bottom: 12px;
                        margin-top: 35px;
                        margin-bottom: 20px;
                        font-size: 28px;
                        font-weight: 600;
                    }}
                    h2 {{ 
                        color: #4fc3f7; 
                        border-bottom: 2px solid #3c3c3c; 
                        padding-bottom: 8px; 
                        margin-top: 30px;
                        margin-bottom: 15px;
                        font-size: 22px;
                        font-weight: 600;
                    }}
                    h3 {{ 
                        color: #81c784; 
                        margin-top: 25px; 
                        margin-bottom: 12px;
                        font-size: 18px;
                        font-weight: 600;
                    }}
                    h4 {{ 
                        color: #a5d6a7; 
                        margin-top: 20px;
                        margin-bottom: 10px;
                        font-size: 16px;
                        font-weight: 600;
                    }}
                    table {{ 
                        border-collapse: collapse; 
                        width: 100%; 
                        margin: 15px 0;
                        background-color: #2b2b2b;
                    }}
                    th, td {{ 
                        border: 1px solid #3c3c3c; 
                        padding: 8px; 
                        text-align: left; 
                    }}
                    th {{ 
                        background-color: #3c3c3c; 
                        color: #4fc3f7;
                        font-weight: bold;
                    }}
                    td {{
                        color: #e0e0e0;
                    }}
                    blockquote {{
                        margin: 15px 0;
                        padding: 12px;
                        background-color: #2b2b2b;
                        border-left: 4px solid #4fc3f7;
                        font-style: italic;
                        color: #b0b0b0;
                    }}
                    code {{
                        background-color: #2b2b2b;
                        color: #81c784;
                        padding: 2px 4px;
                        border-radius: 3px;
                        border: 1px solid #3c3c3c;
                        font-family: 'Courier New', monospace;
                    }}
                    pre {{
                        background-color: #2b2b2b;
                        color: #4fc3f7;
                        padding: 10px;
                        border: 1px solid #3c3c3c;
                        border-radius: 4px;
                        font-family: 'Courier New', monospace;
                        overflow-x: auto;
                    }}
                    p {{
                        margin-bottom: 15px;
                        text-align: left;
                    }}
                    ul, ol {{ 
                        padding-left: 25px;
                        color: #e0e0e0;
                        margin-bottom: 15px;
                    }}
                    li {{ 
                        margin-bottom: 8px;
                        line-height: 1.6;
                    }}
                    ul li {{
                        list-style-type: disc;
                    }}
                    ol li {{
                        list-style-type: decimal;
                    }}
                    strong {{
                        color: #ffd54f;
                        font-weight: bold;
                    }}
                    em {{
                        color: #ffab91;
                        font-style: italic;
                    }}
                    a {{
                        color: #4fc3f7;
                        text-decoration: none;
                    }}
                    a:hover {{
                        text-decoration: underline;
                    }}
                    hr {{
                        border: 1px solid #3c3c3c;
                        margin: 20px 0;
                    }}
                </style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """
            
            self.help_text.setHtml(styled_html)
            
        except FileNotFoundError:
            # Fallback content if markdown file is missing
            fallback_html = """
            <html><body>
            <h2>Help Content Not Found</h2>
            <p>The help content file (help_content.md) could not be loaded.</p>
            <p>Please ensure the file exists in the GUI directory.</p>
            </body></html>
            """
            self.help_text.setHtml(fallback_html)
            
        except Exception as e:
            # Error handling for other issues
            error_html = f"""
            <html><body>
            <h2>Error Loading Help Content</h2>
            <p>An error occurred while loading the help content:</p>
            <p><code>{str(e)}</code></p>
            </body></html>
            """
            self.help_text.setHtml(error_html)
    
    def _simple_markdown_to_html(self, markdown_text: str) -> str:
        """Simple markdown to HTML conversion for basic formatting."""
        
        html = markdown_text
        
        # Headers
        html = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^#### (.*?)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
        
        # Bold and italic
        html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html, flags=re.MULTILINE)
        
        # Code blocks
        html = re.sub(r'`(.*?)`', r'<code>\1</code>', html)
        
        # Simple table conversion (basic)
        lines = html.split('\n')
        in_table = False
        table_html = []
        
        for line in lines:
            if '|' in line and line.strip().startswith('|'):
                if not in_table:
                    table_html.append('<table>')
                    in_table = True
                
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                if all(cell.strip('-') == '' for cell in cells):
                    # Header separator line
                    continue
                
                if not any('<tr>' in h for h in table_html[-3:]):
                    # First row is header
                    row = '<tr>' + ''.join(f'<th>{cell}</th>' for cell in cells) + '</tr>'
                else:
                    row = '<tr>' + ''.join(f'<td>{cell}</td>' for cell in cells) + '</tr>'
                table_html.append(row)
            else:
                if in_table:
                    table_html.append('</table>')
                    in_table = False
                table_html.append(line)
        
        if in_table:
            table_html.append('</table>')
        
        html = '\n'.join(table_html)
        
        # Convert newlines to paragraphs
        html = re.sub(r'\n\n+', '</p><p>', html)
        html = f'<p>{html}</p>'
        html = html.replace('<p></p>', '')
        
        return html
    
    def create_status_panel(self) -> QWidget:
        """Create the status panel."""
        panel = QWidget()
        panel.setMaximumHeight(60)  # Slightly taller to accommodate link
        layout = QVBoxLayout(panel)  # Vertical layout for progress bar and link
        layout.setContentsMargins(10, 5, 10, 5)  # Reduce margins
        
        # Top row: Status and progress bar
        top_row = QWidget()
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        # Status label
        self.status_label = QLabel("Ready to process genes")
        self.status_label.setMinimumWidth(200)
        top_layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(20)  # Make progress bar thinner
        top_layout.addWidget(self.progress_bar, 1)  # Stretch to fill available space
        
        layout.addWidget(top_row)
        
        # Bottom row: AI Safety link
        link_label = QLabel('<a href="https://www.aisafetybook.com/" style="color: #4fc3f7; text-decoration: none;">📚 Interested in AI safety? Check out The AI Safety Book</a>')
        link_label.setOpenExternalLinks(True)  # Enable clicking to open in browser
        link_label.setStyleSheet("QLabel { font-size: 11px; color: #b0b0b0; }")
        link_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(link_label)
        
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
        
        # Disable process button during processing
        if hasattr(self, 'process_button'):
            self.process_button.setEnabled(False)
            self.process_button.setText("⏳ Processing...")
        
        # Clear previous results
        self.clear_results()
        
        # Prepare configuration
        config = {
            'ncbi_api_key': self.settings.value('ncbi_api_key', ''),
            'email': self.settings.value('email', 'user@example.com'),
            'use_cache': self.settings.value('use_cache', True),
            'canonical_only': True,  # Now always true by default
            'validate': True,  # Now always true by default
            'uniprot_first': False,  # Deprecated - HGNC handles resolution
            'workers': 5  # Fixed value for simplicity
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
        self.results_table.setItem(row, 2, QTableWidgetItem(result.get('full_gene_name', '')))
        self.results_table.setItem(row, 3, QTableWidgetItem(result['gene_id']))
        self.results_table.setItem(row, 4, QTableWidgetItem(result.get('gene_url', '')))
        self.results_table.setItem(row, 5, QTableWidgetItem(result['accession']))
        self.results_table.setItem(row, 6, QTableWidgetItem(result.get('isoform', '')))
        self.results_table.setItem(row, 7, QTableWidgetItem(str(result['version'])))
        self.results_table.setItem(row, 8, QTableWidgetItem(str(result['length'])))
        self.results_table.setItem(row, 9, QTableWidgetItem(result['selection_method']))
        self.results_table.setItem(row, 10, QTableWidgetItem(f"{result['confidence']:.2f}"))
        self.results_table.setItem(row, 11, QTableWidgetItem("✓ Success"))
        
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
        self.results_table.setItem(row, 11, QTableWidgetItem(f"✗ {error_message}"))
        
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
        
        # Re-enable process button
        if hasattr(self, 'process_button'):
            self.process_button.setEnabled(True)
            self.process_button.setText("🧬 Process Genes")
        
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
            
            # Display sequence with enhanced info
            sequence = result['sequence']
            formatted = '\n'.join([sequence[i:i+60] for i in range(0, len(sequence), 60)])
            
            # Build info text without extra spaces that break copy-paste
            info_lines = [
                f">{result['accession']}.{result['version']} {result['official_symbol']}",
                f"Full Name: {result.get('full_gene_name', 'N/A')}",
                f"Gene ID: {result['gene_id']}"
            ]
            
            if result.get('gene_url'):
                info_lines.append(f"Gene URL: {result['gene_url']}")
            if result.get('url'):
                info_lines.append(f"GenBank URL: {result['url']}")
            
            if result.get('isoform'):
                info_lines.append(f"Isoform: {result['isoform']}")
            
            info_lines.extend([
                f"Length: {len(sequence)} bp",
                f"Selection: {result['selection_method']} (confidence: {result['confidence']:.2f})"
            ])
            
            if result.get('warnings'):
                info_lines.append(f"Warnings: {', '.join(result['warnings'])}")
            
            # Combine all info with proper newlines, then add sequence
            full_text = '\n'.join(info_lines) + '\n\n' + formatted
            
            # Use setPlainText for clean copy-paste behavior
            self.sequence_viewer.setPlainText(full_text)
    
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
            "GenBank CDS Retrieval Tool\n\n"
            "Version 1.0.0\n\n"
            "Automated retrieval of validated canonical CDS sequences\n"
            "from NCBI GenBank for mRNA therapeutic development.\n\n"
            "Features:\n"
            "• Automatic canonical transcript selection\n"
            "• Built-in sequence validation\n"
            "• Full gene name and database links\n"
            "• Optional UniProt-first search\n\n"
            "© 2024 - Created with PyQt5"
        )
    
    def load_settings(self):
        """Load saved settings."""
        # Window geometry
        geometry = self.settings.value('geometry')
        if geometry:
            self.restoreGeometry(geometry)
        
        # Other settings
        # UniProt First checkbox removed - HGNC handles all resolution
    
    def apply_dark_theme(self):
        """Apply a sleek dark theme to the application."""
        dark_stylesheet = """
        /* Main Application */
        QMainWindow {
            background-color: #1e1e1e;
        }
        
        QWidget {
            background-color: #2b2b2b;
            color: #e0e0e0;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 13px;
        }
        
        /* Group Boxes */
        QGroupBox {
            background-color: #2b2b2b;
            border: 1px solid #3c3c3c;
            border-radius: 6px;
            margin-top: 8px;
            padding-top: 8px;
            font-weight: bold;
        }
        
        QGroupBox::title {
            color: #4fc3f7;
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        
        /* Text Input Areas */
        QTextEdit, QTextBrowser, QPlainTextEdit {
            background-color: #1e1e1e;
            color: #e0e0e0;
            border: 1px solid #3c3c3c;
            border-radius: 4px;
            padding: 5px;
            selection-background-color: #264f78;
        }
        
        QLineEdit {
            background-color: #1e1e1e;
            color: #e0e0e0;
            border: 1px solid #3c3c3c;
            border-radius: 4px;
            padding: 5px;
            selection-background-color: #264f78;
        }
        
        /* Tables */
        QTableWidget {
            background-color: #1e1e1e;
            color: #e0e0e0;
            border: 1px solid #3c3c3c;
            gridline-color: #3c3c3c;
            selection-background-color: #264f78;
        }
        
        QTableWidget::item {
            padding: 5px;
            border: none;
        }
        
        QTableWidget::item:selected {
            background-color: #264f78;
            color: #ffffff;
        }
        
        QHeaderView::section {
            background-color: #2b2b2b;
            color: #4fc3f7;
            padding: 6px;
            border: 1px solid #3c3c3c;
            font-weight: bold;
        }
        
        /* Buttons */
        QPushButton {
            background-color: #3c3c3c;
            color: #e0e0e0;
            border: 1px solid #4c4c4c;
            border-radius: 4px;
            padding: 6px 12px;
            font-weight: bold;
        }
        
        QPushButton:hover {
            background-color: #4c4c4c;
            border: 1px solid #5c5c5c;
        }
        
        QPushButton:pressed {
            background-color: #2c2c2c;
        }
        
        QPushButton:disabled {
            background-color: #2b2b2b;
            color: #6c6c6c;
            border: 1px solid #3c3c3c;
        }
        
        /* Special Process Button (keep green) */
        QPushButton#processButton {
            background-color: #2E7D32;
            color: white;
            font-size: 16px;
            font-weight: bold;
            padding: 10px;
        }
        
        QPushButton#processButton:hover {
            background-color: #388E3C;
        }
        
        QPushButton#processButton:pressed {
            background-color: #1B5E20;
        }
        
        /* Tabs */
        QTabWidget::pane {
            background-color: #2b2b2b;
            border: 1px solid #3c3c3c;
        }
        
        QTabBar::tab {
            background-color: #2b2b2b;
            color: #e0e0e0;
            padding: 8px 12px;
            margin-right: 2px;
            border: 1px solid #3c3c3c;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        
        QTabBar::tab:selected {
            background-color: #3c3c3c;
            color: #4fc3f7;
        }
        
        QTabBar::tab:hover {
            background-color: #3c3c3c;
        }
        
        /* Progress Bar */
        QProgressBar {
            background-color: #1e1e1e;
            border: 1px solid #3c3c3c;
            border-radius: 4px;
            text-align: center;
            color: #e0e0e0;
        }
        
        QProgressBar::chunk {
            background-color: #4fc3f7;
            border-radius: 3px;
        }
        
        /* Menu Bar */
        QMenuBar {
            background-color: #2b2b2b;
            color: #e0e0e0;
            border-bottom: 1px solid #3c3c3c;
        }
        
        QMenuBar::item:selected {
            background-color: #3c3c3c;
        }
        
        QMenu {
            background-color: #2b2b2b;
            color: #e0e0e0;
            border: 1px solid #3c3c3c;
        }
        
        QMenu::item:selected {
            background-color: #264f78;
        }
        
        /* Tool Bar */
        QToolBar {
            background-color: #2b2b2b;
            border: none;
            spacing: 3px;
            padding: 3px;
        }
        
        QToolButton {
            background-color: transparent;
            color: #e0e0e0;
            border: 1px solid transparent;
            border-radius: 4px;
            padding: 4px;
        }
        
        QToolButton:hover {
            background-color: #3c3c3c;
            border: 1px solid #4c4c4c;
        }
        
        /* Status Bar */
        QStatusBar {
            background-color: #2b2b2b;
            color: #e0e0e0;
            border-top: 1px solid #3c3c3c;
        }
        
        /* Scroll Bars */
        QScrollBar:vertical {
            background-color: #1e1e1e;
            width: 12px;
            border: none;
        }
        
        QScrollBar::handle:vertical {
            background-color: #4c4c4c;
            border-radius: 6px;
            min-height: 20px;
        }
        
        QScrollBar::handle:vertical:hover {
            background-color: #5c5c5c;
        }
        
        QScrollBar:horizontal {
            background-color: #1e1e1e;
            height: 12px;
            border: none;
        }
        
        QScrollBar::handle:horizontal {
            background-color: #4c4c4c;
            border-radius: 6px;
            min-width: 20px;
        }
        
        QScrollBar::handle:horizontal:hover {
            background-color: #5c5c5c;
        }
        
        QScrollBar::add-line, QScrollBar::sub-line {
            border: none;
            background: none;
        }
        
        /* Splitters */
        QSplitter::handle {
            background-color: #3c3c3c;
        }
        
        QSplitter::handle:hover {
            background-color: #4fc3f7;
        }
        
        /* CheckBox */
        QCheckBox {
            color: #e0e0e0;
            spacing: 5px;
        }
        
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border: 1px solid #4c4c4c;
            border-radius: 3px;
            background-color: #1e1e1e;
        }
        
        QCheckBox::indicator:checked {
            background-color: #4fc3f7;
            border: 1px solid #4fc3f7;
        }
        
        /* SpinBox */
        QSpinBox {
            background-color: #1e1e1e;
            color: #e0e0e0;
            border: 1px solid #3c3c3c;
            border-radius: 4px;
            padding: 3px;
        }
        
        QSpinBox::up-button, QSpinBox::down-button {
            background-color: #3c3c3c;
            border: none;
            width: 16px;
        }
        
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {
            background-color: #4c4c4c;
        }
        
        /* Labels */
        QLabel {
            color: #e0e0e0;
        }
        
        /* Tooltips */
        QToolTip {
            background-color: #3c3c3c;
            color: #e0e0e0;
            border: 1px solid #4c4c4c;
            border-radius: 4px;
            padding: 4px;
        }
        """
        
        self.setStyleSheet(dark_stylesheet)
    
    def closeEvent(self, event):
        """Save settings on close."""
        # Stop any running threads
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.cancel()
            self.processing_thread.wait()
        
        # Save settings
        self.settings.setValue('geometry', self.saveGeometry())
        # UniProt First setting removed - HGNC handles all resolution
        
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
    main()