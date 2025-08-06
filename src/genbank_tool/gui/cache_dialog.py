"""Cache management dialog for GenBank Tool GUI."""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QGroupBox,
    QProgressBar, QMessageBox
)
from PyQt5.QtCore import Qt

from ..cache_manager import CacheManager


class CacheDialog(QDialog):
    """Dialog for managing cache."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cache Management")
        self.setModal(True)
        self.resize(700, 500)
        
        # Get cache manager
        cache_dir = parent.settings.value('cache_dir', '.genbank_cache')
        self.cache_manager = CacheManager(cache_dir=cache_dir)
        
        self.init_ui()
        self.refresh_stats()
    
    def init_ui(self):
        """Initialize the cache UI."""
        layout = QVBoxLayout(self)
        
        # Cache statistics
        stats_group = QGroupBox("Cache Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        # Stats labels
        self.stats_labels = {}
        stats_items = [
            ('total_entries', 'Total Entries:'),
            ('total_size', 'Total Size:'),
            ('hit_rate', 'Hit Rate:'),
            ('hits', 'Cache Hits:'),
            ('misses', 'Cache Misses:'),
            ('expired', 'Expired Entries:'),
            ('evicted', 'Evicted Entries:')
        ]
        
        for key, label in stats_items:
            h_layout = QHBoxLayout()
            h_layout.addWidget(QLabel(label))
            value_label = QLabel("0")
            value_label.setAlignment(Qt.AlignRight)
            self.stats_labels[key] = value_label
            h_layout.addWidget(value_label)
            stats_layout.addLayout(h_layout)
        
        # Usage bar
        self.usage_bar = QProgressBar()
        self.usage_bar.setFormat("%p% of maximum size")
        stats_layout.addWidget(QLabel("Cache Usage:"))
        stats_layout.addWidget(self.usage_bar)
        
        layout.addWidget(stats_group)
        
        # Namespace breakdown
        namespace_group = QGroupBox("Cache by Type")
        namespace_layout = QVBoxLayout(namespace_group)
        
        self.namespace_table = QTableWidget()
        self.namespace_table.setColumnCount(3)
        self.namespace_table.setHorizontalHeaderLabels(['Type', 'Entries', 'Size (MB)'])
        self.namespace_table.horizontalHeader().setStretchLastSection(True)
        namespace_layout.addWidget(self.namespace_table)
        
        layout.addWidget(namespace_group)
        
        # Actions
        actions_layout = QHBoxLayout()
        
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_stats)
        actions_layout.addWidget(refresh_button)
        
        cleanup_button = QPushButton("Clean Expired")
        cleanup_button.clicked.connect(self.cleanup_expired)
        actions_layout.addWidget(cleanup_button)
        
        clear_button = QPushButton("Clear All")
        clear_button.clicked.connect(self.clear_all)
        actions_layout.addWidget(clear_button)
        
        actions_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        actions_layout.addWidget(close_button)
        
        layout.addLayout(actions_layout)
    
    def refresh_stats(self):
        """Refresh cache statistics."""
        # Get stats
        stats = self.cache_manager.get_stats()
        size_info = self.cache_manager.get_size_info()
        
        # Update labels
        self.stats_labels['total_entries'].setText(str(stats.total_entries))
        self.stats_labels['total_size'].setText(f"{size_info['total_size_mb']:.2f} MB")
        self.stats_labels['hit_rate'].setText(f"{stats.hit_rate:.1%}")
        self.stats_labels['hits'].setText(str(stats.hit_count))
        self.stats_labels['misses'].setText(str(stats.miss_count))
        self.stats_labels['expired'].setText(str(stats.expired_count))
        self.stats_labels['evicted'].setText(str(stats.evicted_count))
        
        # Update usage bar
        usage_percent = int(size_info['usage_percent'])
        self.usage_bar.setValue(usage_percent)
        
        # Update namespace table
        self.namespace_table.setRowCount(0)
        for namespace, info in size_info['namespaces'].items():
            row = self.namespace_table.rowCount()
            self.namespace_table.insertRow(row)
            self.namespace_table.setItem(row, 0, QTableWidgetItem(namespace))
            self.namespace_table.setItem(row, 1, QTableWidgetItem(str(info['count'])))
            self.namespace_table.setItem(row, 2, QTableWidgetItem(f"{info['size_mb']:.2f}"))
    
    def cleanup_expired(self):
        """Clean up expired cache entries."""
        try:
            removed = self.cache_manager.cleanup_expired()
            QMessageBox.information(
                self,
                "Cleanup Complete",
                f"Removed {removed} expired cache entries."
            )
            self.refresh_stats()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to cleanup cache: {e}"
            )
    
    def clear_all(self):
        """Clear all cache entries."""
        reply = QMessageBox.question(
            self,
            "Clear Cache",
            "Are you sure you want to clear all cached data?\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                cleared = self.cache_manager.clear()
                QMessageBox.information(
                    self,
                    "Cache Cleared",
                    f"Cleared {cleared} cache entries."
                )
                self.refresh_stats()
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to clear cache: {e}"
                )