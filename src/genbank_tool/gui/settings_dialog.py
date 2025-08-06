"""Settings dialog for GenBank Tool GUI."""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLineEdit, QCheckBox, QSpinBox, QPushButton,
    QTabWidget, QWidget, QGroupBox, QComboBox,
    QDialogButtonBox, QMessageBox
)
from PyQt5.QtCore import QSettings


class SettingsDialog(QDialog):
    """Settings configuration dialog."""
    
    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(500, 400)
        
        self.init_ui()
        self.load_settings()
    
    def init_ui(self):
        """Initialize the settings UI."""
        layout = QVBoxLayout(self)
        
        # Create tab widget
        tabs = QTabWidget()
        
        # API Settings tab
        api_tab = self.create_api_tab()
        tabs.addTab(api_tab, "API Settings")
        
        # Processing tab
        processing_tab = self.create_processing_tab()
        tabs.addTab(processing_tab, "Processing")
        
        # Cache tab
        cache_tab = self.create_cache_tab()
        tabs.addTab(cache_tab, "Cache")
        
        # Network tab
        network_tab = self.create_network_tab()
        tabs.addTab(network_tab, "Network")
        
        layout.addWidget(tabs)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def create_api_tab(self) -> QWidget:
        """Create API settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # NCBI Settings
        ncbi_group = QGroupBox("NCBI Settings")
        ncbi_layout = QFormLayout(ncbi_group)
        
        self.ncbi_api_key = QLineEdit()
        self.ncbi_api_key.setPlaceholderText("Optional - increases rate limit")
        ncbi_layout.addRow("API Key:", self.ncbi_api_key)
        
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("your@email.com")
        ncbi_layout.addRow("Email:", self.email_edit)
        
        layout.addWidget(ncbi_group)
        
        # UniProt Settings
        uniprot_group = QGroupBox("UniProt Settings")
        uniprot_layout = QFormLayout(uniprot_group)
        
        self.uniprot_fallback = QCheckBox("Use UniProt as fallback")
        self.uniprot_fallback.setChecked(True)
        uniprot_layout.addRow(self.uniprot_fallback)
        
        self.confidence_threshold = QSpinBox()
        self.confidence_threshold.setMinimum(50)
        self.confidence_threshold.setMaximum(100)
        self.confidence_threshold.setValue(80)
        self.confidence_threshold.setSuffix("%")
        uniprot_layout.addRow("Confidence Threshold:", self.confidence_threshold)
        
        layout.addWidget(uniprot_group)
        
        layout.addStretch()
        return widget
    
    def create_processing_tab(self) -> QWidget:
        """Create processing settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        form = QFormLayout()
        
        # Canonical selection
        self.canonical_only = QCheckBox("Select canonical transcripts only")
        self.canonical_only.setChecked(True)
        form.addRow(self.canonical_only)
        
        # Validation
        self.enable_validation = QCheckBox("Validate sequences")
        form.addRow(self.enable_validation)
        
        self.strict_validation = QCheckBox("Strict validation mode")
        self.strict_validation.setEnabled(False)
        self.enable_validation.toggled.connect(self.strict_validation.setEnabled)
        form.addRow(self.strict_validation)
        
        # Parallel processing
        self.max_workers = QSpinBox()
        self.max_workers.setMinimum(1)
        self.max_workers.setMaximum(20)
        self.max_workers.setValue(5)
        form.addRow("Max parallel workers:", self.max_workers)
        
        # Output format
        self.default_format = QComboBox()
        self.default_format.addItems(['TSV', 'CSV', 'Excel', 'JSON'])
        form.addRow("Default output format:", self.default_format)
        
        layout.addLayout(form)
        layout.addStretch()
        return widget
    
    def create_cache_tab(self) -> QWidget:
        """Create cache settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        form = QFormLayout()
        
        # Cache enable
        self.enable_cache = QCheckBox("Enable caching")
        self.enable_cache.setChecked(True)
        form.addRow(self.enable_cache)
        
        # Cache directory
        self.cache_dir = QLineEdit()
        self.cache_dir.setText(".genbank_cache")
        form.addRow("Cache directory:", self.cache_dir)
        
        # Cache size
        self.cache_size = QSpinBox()
        self.cache_size.setMinimum(10)
        self.cache_size.setMaximum(5000)
        self.cache_size.setValue(500)
        self.cache_size.setSuffix(" MB")
        form.addRow("Max cache size:", self.cache_size)
        
        # Cache expiration
        self.cache_ttl = QSpinBox()
        self.cache_ttl.setMinimum(1)
        self.cache_ttl.setMaximum(30)
        self.cache_ttl.setValue(7)
        self.cache_ttl.setSuffix(" days")
        form.addRow("Cache expiration:", self.cache_ttl)
        
        layout.addLayout(form)
        
        # Clear cache button
        clear_button = QPushButton("Clear Cache Now")
        clear_button.clicked.connect(self.clear_cache)
        layout.addWidget(clear_button)
        
        layout.addStretch()
        return widget
    
    def create_network_tab(self) -> QWidget:
        """Create network settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        form = QFormLayout()
        
        # Timeout
        self.timeout = QSpinBox()
        self.timeout.setMinimum(10)
        self.timeout.setMaximum(300)
        self.timeout.setValue(60)
        self.timeout.setSuffix(" seconds")
        form.addRow("Request timeout:", self.timeout)
        
        # Retries
        self.max_retries = QSpinBox()
        self.max_retries.setMinimum(0)
        self.max_retries.setMaximum(10)
        self.max_retries.setValue(3)
        form.addRow("Max retries:", self.max_retries)
        
        # Rate limiting
        rate_group = QGroupBox("Rate Limiting")
        rate_layout = QFormLayout(rate_group)
        
        self.ncbi_rate = QSpinBox()
        self.ncbi_rate.setMinimum(1)
        self.ncbi_rate.setMaximum(10)
        self.ncbi_rate.setValue(3)
        self.ncbi_rate.setSuffix(" req/sec")
        rate_layout.addRow("NCBI rate limit:", self.ncbi_rate)
        
        self.uniprot_rate = QSpinBox()
        self.uniprot_rate.setMinimum(1)
        self.uniprot_rate.setMaximum(20)
        self.uniprot_rate.setValue(10)
        self.uniprot_rate.setSuffix(" req/sec")
        rate_layout.addRow("UniProt rate limit:", self.uniprot_rate)
        
        layout.addLayout(form)
        layout.addWidget(rate_group)
        layout.addStretch()
        return widget
    
    def load_settings(self):
        """Load current settings."""
        # API settings
        self.ncbi_api_key.setText(self.settings.value('ncbi_api_key', ''))
        self.email_edit.setText(self.settings.value('email', ''))
        self.uniprot_fallback.setChecked(
            self.settings.value('uniprot_fallback', True, type=bool)
        )
        self.confidence_threshold.setValue(
            self.settings.value('confidence_threshold', 80, type=int)
        )
        
        # Processing settings
        self.canonical_only.setChecked(
            self.settings.value('canonical_only', True, type=bool)
        )
        self.enable_validation.setChecked(
            self.settings.value('enable_validation', False, type=bool)
        )
        self.strict_validation.setChecked(
            self.settings.value('strict_validation', False, type=bool)
        )
        self.max_workers.setValue(
            self.settings.value('max_workers', 5, type=int)
        )
        self.default_format.setCurrentText(
            self.settings.value('default_format', 'TSV')
        )
        
        # Cache settings
        self.enable_cache.setChecked(
            self.settings.value('enable_cache', True, type=bool)
        )
        self.cache_dir.setText(
            self.settings.value('cache_dir', '.genbank_cache')
        )
        self.cache_size.setValue(
            self.settings.value('cache_size', 500, type=int)
        )
        self.cache_ttl.setValue(
            self.settings.value('cache_ttl', 7, type=int)
        )
        
        # Network settings
        self.timeout.setValue(
            self.settings.value('timeout', 60, type=int)
        )
        self.max_retries.setValue(
            self.settings.value('max_retries', 3, type=int)
        )
        self.ncbi_rate.setValue(
            self.settings.value('ncbi_rate', 3, type=int)
        )
        self.uniprot_rate.setValue(
            self.settings.value('uniprot_rate', 10, type=int)
        )
    
    def save_settings(self):
        """Save settings and close dialog."""
        # API settings
        self.settings.setValue('ncbi_api_key', self.ncbi_api_key.text())
        self.settings.setValue('email', self.email_edit.text())
        self.settings.setValue('uniprot_fallback', self.uniprot_fallback.isChecked())
        self.settings.setValue('confidence_threshold', self.confidence_threshold.value())
        
        # Processing settings
        self.settings.setValue('canonical_only', self.canonical_only.isChecked())
        self.settings.setValue('enable_validation', self.enable_validation.isChecked())
        self.settings.setValue('strict_validation', self.strict_validation.isChecked())
        self.settings.setValue('max_workers', self.max_workers.value())
        self.settings.setValue('default_format', self.default_format.currentText())
        
        # Cache settings
        self.settings.setValue('enable_cache', self.enable_cache.isChecked())
        self.settings.setValue('cache_dir', self.cache_dir.text())
        self.settings.setValue('cache_size', self.cache_size.value())
        self.settings.setValue('cache_ttl', self.cache_ttl.value())
        
        # Network settings
        self.settings.setValue('timeout', self.timeout.value())
        self.settings.setValue('max_retries', self.max_retries.value())
        self.settings.setValue('ncbi_rate', self.ncbi_rate.value())
        self.settings.setValue('uniprot_rate', self.uniprot_rate.value())
        
        self.accept()
    
    def clear_cache(self):
        """Clear the cache."""
        from ..cache_manager import CacheManager
        
        reply = QMessageBox.question(
            self,
            "Clear Cache",
            "Are you sure you want to clear all cached data?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                cache_mgr = CacheManager(cache_dir=self.cache_dir.text())
                cleared = cache_mgr.clear()
                QMessageBox.information(
                    self,
                    "Cache Cleared",
                    f"Cleared {cleared} cache entries."
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to clear cache: {e}"
                )