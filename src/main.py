"""
Main GUI application for Advanced Search
"""
import sys
import os
import re
import json
import string
import subprocess
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTreeWidget, QTreeWidgetItem, QTextEdit, QLineEdit,
    QSplitter, QLabel, QCheckBox, QSpinBox,
    QProgressBar, QStatusBar, QMessageBox, QMenu, QComboBox,
    QDialog, QFormLayout, QDialogButtonBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor, QAction, QIcon
from .search_engine import SearchEngine, SearchMatch


class PreferencesDialog(QDialog):
    """Preferences dialog window"""
    
    def __init__(self, parent, preferences):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setModal(True)
        self.preferences = preferences.copy()
        
        # Create layout
        layout = QVBoxLayout()
        form = QFormLayout()
        
        # Max results
        self.max_results_input = QSpinBox()
        self.max_results_input.setRange(0, 1000000)
        self.max_results_input.setValue(preferences['max_results'])
        self.max_results_input.setSpecialValueText("Unlimited")
        self.max_results_input.setToolTip("Maximum search results to return (0 = unlimited)")
        form.addRow("Max Search Results:", self.max_results_input)
        
        # Max preview file size
        self.max_preview_size_input = QSpinBox()
        self.max_preview_size_input.setRange(1, 1000)
        self.max_preview_size_input.setValue(preferences['max_preview_file_size_mb'])
        self.max_preview_size_input.setSuffix(" MB")
        self.max_preview_size_input.setToolTip("Maximum file size to display in preview")
        form.addRow("Max Preview File Size:", self.max_preview_size_input)
        
        # Max search file size
        self.max_search_size_input = QSpinBox()
        self.max_search_size_input.setRange(1, 1000)
        self.max_search_size_input.setValue(preferences['max_search_file_size_mb'])
        self.max_search_size_input.setSuffix(" MB")
        self.max_search_size_input.setToolTip("Maximum file size to search through")
        form.addRow("Max Search File Size:", self.max_search_size_input)
        
        # Max cache size
        self.max_cache_input = QSpinBox()
        self.max_cache_input.setRange(0, 500)
        self.max_cache_input.setValue(preferences['max_cache_size'])
        self.max_cache_input.setSpecialValueText("Disabled")
        self.max_cache_input.setToolTip("Maximum number of files to cache in memory")
        form.addRow("File Cache Size:", self.max_cache_input)
        
        layout.addLayout(form)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
        self.resize(400, 250)
    
    def get_preferences(self):
        """Get updated preferences from dialog"""
        return {
            'max_results': self.max_results_input.value(),
            'max_preview_file_size_mb': self.max_preview_size_input.value(),
            'max_search_file_size_mb': self.max_search_size_input.value(),
            'max_cache_size': self.max_cache_input.value()
        }


class SearchWorker(QThread):
    """Worker thread for performing searches"""
    finished = Signal(list)  # all results
    
    def __init__(self, search_engine, root_path, pattern):
        super().__init__()
        self.search_engine = search_engine
        self.root_path = root_path
        self.pattern = pattern
        self._is_running = True
    
    def run(self):
        """Run the search in background thread"""
        results = self.search_engine.search(self.root_path, self.pattern)
        if self._is_running:
            self.finished.emit(results)
    
    def stop(self):
        """Stop the search"""
        self._is_running = False


class MainWindow(QMainWindow):
    """Main application window"""
    
    # Class constants for file extensions
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.gif', '.bmp', '.webp'}
    FILE_METADATA_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.pptx', '.mp3', '.flac', '.m4a', '.mp4', '.avi', '.mkv'}
    
    def __init__(self):
        super().__init__()
        self.search_engine = SearchEngine()
        self.search_worker = None
        self.current_results = []
        self.current_directory = os.path.expanduser("~")
        self.current_search_pattern = ""
        self.current_file_matches = []
        self.current_match_index = 0
        self.search_history = []
        self.history_file = os.path.join(os.path.expanduser("~"), ".advanced_search_history.json")
        self.preferences_file = os.path.join(os.path.expanduser("~"), ".advanced_search_preferences.json")
        
        # Default preferences
        self.preferences = {
            'max_results': 0,  # 0 = unlimited
            'max_preview_file_size_mb': 10,
            'max_search_file_size_mb': 50,
            'max_cache_size': 50
        }
        self.load_preferences()
        
        # Performance caches
        self.file_cache = {}  # Cache file contents {path: (size, content_lines)}
        self.max_cache_size = self.preferences['max_cache_size']
        self.max_file_size = self.preferences['max_preview_file_size_mb'] * 1024 * 1024
        self.parsed_extensions = []  # Cached parsed extensions
        
        # Regex pattern options
        self.regex_patterns = {
            'emails': {'pattern': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 'enabled': False, 'label': 'Email addresses'},
            'urls': {'pattern': r'https?://[^\s]+', 'enabled': False, 'label': 'URLs (http/https)'},
            'ipv4': {'pattern': r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', 'enabled': False, 'label': 'IPv4 addresses'},
            'phone': {'pattern': r'\b(?:\+?1[-.]?)?(?:\(?[0-9]{3}\)?[-.]?)?[0-9]{3}[-.]?[0-9]{4}\b', 'enabled': False, 'label': 'Phone numbers'},
            'dates': {'pattern': r'\b\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}\b', 'enabled': False, 'label': 'Dates (various formats)'},
            'numbers': {'pattern': r'\b\d+\b', 'enabled': False, 'label': 'Numbers'},
            'hex': {'pattern': r'\b0x[0-9A-Fa-f]+\b|#[0-9A-Fa-f]{6}\b', 'enabled': False, 'label': 'Hex values'},
            'words': {'pattern': r'\b[A-Za-z_]\w*\b', 'enabled': False, 'label': 'Words/identifiers'},
        }
        self.regex_menu = None  # Track the menu instance
        self.regex_menu_open = False  # Track menu state
        
        # Apply preferences to search engine
        self.search_engine.max_results = self.preferences['max_results']
        self.search_engine.max_search_file_size = self.preferences['max_search_file_size_mb'] * 1024 * 1024
        
        self.load_search_history()
        
        self.init_ui()
        self.create_menu_bar()
        self.setWindowTitle("Advanced Search Tool")
        
        # Set application icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icon.svg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.resize(1400, 900)
    
    def init_ui(self):
        """Initialize the user interface"""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Combined search and options bar
        search_options_layout = self.create_search_and_options()
        main_layout.addLayout(search_options_layout)
        
        # Main content area with three panels
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Directory tree
        dir_widget = QWidget()
        dir_layout = QVBoxLayout(dir_widget)
        dir_layout.setContentsMargins(0, 0, 0, 0)
        
        dir_label = QLabel("File Explorer:")
        dir_label.setStyleSheet("font-weight: bold; padding: 5px;")
        dir_label.setToolTip("Select a directory or file to search")
        dir_layout.addWidget(dir_label)
        
        self.dir_tree = QTreeWidget()
        self.dir_tree.setHeaderLabels(["Name"])
        self.dir_tree.setToolTip("Click a folder to search recursively or a file to search in that file\nRight-click for options")
        self.dir_tree.itemClicked.connect(self.on_dir_selected)
        self.dir_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.dir_tree.customContextMenuRequested.connect(self.show_dir_context_menu)
        self.dir_tree.itemExpanded.connect(self.on_dir_expanded)
        self.populate_directory_tree()
        dir_layout.addWidget(self.dir_tree)
        
        splitter.addWidget(dir_widget)
        
        # Middle panel - Results tree
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 0, 0, 0)
        
        results_label = QLabel("Search Results:")
        results_label.setStyleSheet("font-weight: bold; padding: 5px;")
        results_label.setToolTip("Files and matches found in search")
        results_layout.addWidget(results_label)
        
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["File", "Matches"])
        self.results_tree.setColumnWidth(0, 400)
        self.results_tree.setToolTip("Click to preview, double-click to open file, right-click for options")
        self.results_tree.itemClicked.connect(self.on_tree_item_clicked)
        self.results_tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.results_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.results_tree.customContextMenuRequested.connect(self.show_context_menu)
        results_layout.addWidget(self.results_tree)
        
        splitter.addWidget(results_widget)
        
        # Right panel - Content preview
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        
        # Preview header with navigation
        preview_header = QHBoxLayout()
        preview_label = QLabel("Preview:")
        preview_label.setStyleSheet("font-weight: bold; padding: 5px;")
        preview_label.setToolTip("File content preview with matched lines highlighted")
        preview_header.addWidget(preview_label)
        
        preview_header.addStretch()
        
        # Match navigation controls
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        prev_icon_path = os.path.join(assets_dir, "chevron_up.svg")
        self.prev_match_btn = QPushButton()
        if os.path.exists(prev_icon_path):
            self.prev_match_btn.setIcon(QIcon(prev_icon_path))
        else:
            self.prev_match_btn.setText("◄")
        self.prev_match_btn.setMaximumWidth(30)
        self.prev_match_btn.setToolTip("Go to previous match (Ctrl+Up)")
        self.prev_match_btn.clicked.connect(self.go_to_previous_match)
        self.prev_match_btn.setEnabled(False)
        preview_header.addWidget(self.prev_match_btn)
        
        self.match_counter_label = QLabel("0/0")
        self.match_counter_label.setStyleSheet("padding: 0 10px;")
        self.match_counter_label.setToolTip("Current match / Total matches")
        preview_header.addWidget(self.match_counter_label)
        
        next_icon_path = os.path.join(assets_dir, "chevron_down.svg")
        self.next_match_btn = QPushButton()
        if os.path.exists(next_icon_path):
            self.next_match_btn.setIcon(QIcon(next_icon_path))
        else:
            self.next_match_btn.setText("►")
        self.next_match_btn.setMaximumWidth(30)
        self.next_match_btn.setToolTip("Go to next match (Ctrl+Down)")
        self.next_match_btn.clicked.connect(self.go_to_next_match)
        self.next_match_btn.setEnabled(False)
        preview_header.addWidget(self.next_match_btn)
        
        preview_layout.addLayout(preview_header)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setFont(QFont("Consolas", 10))
        self.preview_text.setToolTip("File preview - search terms are highlighted in yellow")
        preview_layout.addWidget(self.preview_text)
        
        splitter.addWidget(preview_widget)
        splitter.setSizes([300, 400, 700])
        
        main_layout.addWidget(splitter)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def create_menu_bar(self):
        """Create application menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Settings menu
        settings_menu = menubar.addMenu("&Settings")
        
        preferences_action = QAction("Preferences...", self)
        preferences_action.triggered.connect(self.show_preferences)
        settings_menu.addAction(preferences_action)
        
        settings_menu.addSeparator()
        
        clear_history_action = QAction("Clear Search History", self)
        clear_history_action.triggered.connect(self.clear_search_history)
        settings_menu.addAction(clear_history_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_search_and_options(self):
        """Create combined search and options controls"""
        layout = QHBoxLayout()
        
        # Search for label and input
        search_label = QLabel("Search for:")
        search_label.setToolTip("Enter text or regular expression pattern to search for")
        layout.addWidget(search_label)
        
        self.search_input = QComboBox()
        self.search_input.setEditable(True)
        self.search_input.setInsertPolicy(QComboBox.NoInsert)
        self.search_input.lineEdit().setPlaceholderText("Enter search pattern...")
        self.search_input.setToolTip("Text or regex pattern to find in files\nPress Enter to start search\nUse Up/Down arrows to cycle through history")
        self.search_input.lineEdit().returnPressed.connect(self.start_search)
        self.search_input.setMinimumWidth(250)
        self.search_input.setMaxVisibleItems(10)
        # Enable auto-completion
        self.search_input.setCompleter(self.search_input.completer())
        self.update_search_history_dropdown()
        layout.addWidget(self.search_input)
        
        # Search and Stop buttons
        self.search_btn = QPushButton("Search")
        self.search_btn.setToolTip("Start searching in the selected directory (Enter)")
        self.search_btn.clicked.connect(self.start_search)
        self.search_btn.setDefault(True)
        layout.addWidget(self.search_btn)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setToolTip("Stop the current search operation")
        self.stop_btn.clicked.connect(self.stop_search)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)
        
        # Separator
        layout.addSpacing(20)
        
        # Checkboxes
        self.case_sensitive_cb = QCheckBox("Case sensitive")
        self.case_sensitive_cb.setToolTip("Match exact case when searching")
        self.case_sensitive_cb.stateChanged.connect(
            lambda state: self.search_engine.set_case_sensitive(state == Qt.Checked)
        )
        layout.addWidget(self.case_sensitive_cb)
        
        # Regex pattern selector button
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        chevron_icon_path = os.path.join(assets_dir, "chevron_down.svg")
        self.regex_btn = QPushButton("Regex Patterns")
        if os.path.exists(chevron_icon_path):
            self.regex_btn.setIcon(QIcon(chevron_icon_path))
            self.regex_btn.setLayoutDirection(Qt.RightToLeft)  # Icon on the right
        self.regex_btn.setToolTip("Select common regex patterns to search for")
        self.regex_btn.setMaximumWidth(150)
        self.regex_btn.clicked.connect(self.show_regex_patterns_menu)
        layout.addWidget(self.regex_btn)
        
        self.whole_word_cb = QCheckBox("Whole word")
        self.whole_word_cb.setToolTip("Only match complete words (not partial matches)")
        self.whole_word_cb.stateChanged.connect(
            lambda state: self.search_engine.set_whole_word(state == Qt.Checked)
        )
        layout.addWidget(self.whole_word_cb)
        
        self.metadata_cb = QCheckBox("Search image metadata")
        self.metadata_cb.setToolTip("Search image metadata (EXIF, GPS, etc.) for JPG, PNG, TIFF files")
        self.metadata_cb.stateChanged.connect(
            lambda state: self.search_engine.set_search_metadata(state == 2)
        )
        layout.addWidget(self.metadata_cb)
        
        self.file_metadata_cb = QCheckBox("Search file metadata")
        self.file_metadata_cb.setToolTip("Search file properties (PDF, Office docs, audio/video files): author, title, dates, etc.")
        self.file_metadata_cb.stateChanged.connect(
            lambda state: self.search_engine.set_search_file_metadata(state == 2)
        )
        layout.addWidget(self.file_metadata_cb)
        
        # Context lines dropdown
        context_label = QLabel("Context:")
        context_label.setToolTip("Number of lines to show before and after each match")
        layout.addWidget(context_label)
        
        self.context_combo = QComboBox()
        for i in range(11):  # 0 to 10
            self.context_combo.addItem(str(i))
        self.context_combo.setCurrentIndex(2)  # Default to 2
        self.context_combo.setToolTip("Lines of context to show around matches (0-10)")
        self.context_combo.currentIndexChanged.connect(
            lambda index: self.search_engine.set_context_lines(index)
        )
        self.context_combo.setMinimumWidth(50)
        self.context_combo.setMaximumWidth(70)
        layout.addWidget(self.context_combo)
        
        # File extensions filter
        ext_label = QLabel("Extensions:")
        ext_label.setToolTip("Filter files by extension (leave empty to search all files)")
        layout.addWidget(ext_label)
        
        self.extensions_input = QLineEdit()
        self.extensions_input.setPlaceholderText(".py,.txt,.js")
        self.extensions_input.setToolTip("Comma-separated file extensions to search\nExample: .py,.txt,.js\nLeave empty to search all files")
        self.extensions_input.setMaximumWidth(150)
        layout.addWidget(self.extensions_input)
        
        layout.addStretch()
        return layout
    
    def populate_directory_tree(self):
        """Populate directory tree with common locations"""
        self.dir_tree.setUpdatesEnabled(False)  # Batch updates for performance
        self.dir_tree.clear()
        
        # Add common locations
        home_item = QTreeWidgetItem(self.dir_tree)
        home_item.setText(0, "Home")
        home_item.setData(0, Qt.UserRole, {"path": os.path.expanduser("~"), "is_file": False})
        home_item.setExpanded(True)
        
        # Add subdirectories and files of home
        home_path = os.path.expanduser("~")
        self._populate_tree_item(home_item, home_path)
        
        # Add drives (Windows)
        if os.name == 'nt':
            for drive in string.ascii_uppercase:
                drive_path = f"{drive}:\\\\"
                if os.path.exists(drive_path):
                    drive_item = QTreeWidgetItem(self.dir_tree)
                    drive_item.setText(0, f"{drive}:")
                    drive_item.setData(0, Qt.UserRole, {"path": drive_path, "is_file": False})
                    # Add placeholder for lazy loading
                    placeholder = QTreeWidgetItem(drive_item)
                    placeholder.setText(0, "Loading...")
        
        self.dir_tree.setUpdatesEnabled(True)  # Re-enable updates
    
    def _populate_tree_item(self, parent_item, path, max_items=100):
        """Populate a tree item with directories and files"""
        try:
            entries = []
            for entry in os.scandir(path):
                if not entry.name.startswith('.'):
                    entries.append(entry)
            
            # Sort: directories first, then files
            entries.sort(key=lambda e: (not e.is_dir(), e.name.lower()))
            
            # Limit to prevent UI freeze
            for entry in entries[:max_items]:
                child_item = QTreeWidgetItem(parent_item)
                if entry.is_dir():
                    child_item.setText(0, entry.name)
                    child_item.setData(0, Qt.UserRole, {"path": entry.path, "is_file": False})
                    # Add placeholder for lazy loading
                    placeholder = QTreeWidgetItem(child_item)
                    placeholder.setText(0, "Loading...")
                else:
                    child_item.setText(0, entry.name)
                    child_item.setData(0, Qt.UserRole, {"path": entry.path, "is_file": True})
        except PermissionError:
            pass
    
    def on_dir_expanded(self, item):
        """Handle directory expansion - lazy load contents"""
        data = item.data(0, Qt.UserRole)
        if data and not data.get("is_file", False):
            # Check if we have a placeholder
            if item.childCount() == 1 and item.child(0).text(0) == "Loading...":
                # Remove placeholder
                item.removeChild(item.child(0))
                # Load actual contents
                self._populate_tree_item(item, data["path"])
    
    def on_dir_selected(self, item, column):
        """Handle directory or file selection"""
        data = item.data(0, Qt.UserRole)
        if data:
            path = data["path"]
            is_file = data.get("is_file", False)
            self.current_directory = path
            if is_file:
                self.status_bar.showMessage(f"Selected file: {path}")
            else:
                self.status_bar.showMessage(f"Selected directory: {path}")
    
    def show_regex_patterns_menu(self):
        """Show or hide popup menu with regex pattern options"""
        # If menu exists and is visible, close it and prevent reopening
        if self.regex_menu is not None and self.regex_menu.isVisible():
            self.regex_menu.close()
            self.regex_menu_open = False
            return
        
        # If we just closed the menu, don't reopen immediately
        if self.regex_menu_open:
            return
        
        # Mark menu as opening
        self.regex_menu_open = True
        
        # Create new menu
        self.regex_menu = QMenu(self)
        self.regex_menu.setToolTipsVisible(True)
        
        # Add header
        header_action = self.regex_menu.addAction("Select Regex Patterns:")
        header_action.setEnabled(False)
        self.regex_menu.addSeparator()
        
        # Add checkbox for each pattern
        for pattern_key, pattern_info in self.regex_patterns.items():
            action = self.regex_menu.addAction(pattern_info['label'])
            action.setCheckable(True)
            action.setChecked(pattern_info['enabled'])
            action.setToolTip(f"Pattern: {pattern_info['pattern']}")
            action.triggered.connect(lambda checked, key=pattern_key: self.toggle_regex_pattern(key, checked))
        
        self.regex_menu.addSeparator()
        
        # Add clear all option
        clear_action = self.regex_menu.addAction("Clear All")
        clear_action.triggered.connect(self.clear_all_regex_patterns)
        
        # Clean up when menu is hidden/closed
        def on_menu_hidden():
            # Use a timer to delay the flag reset to avoid immediate reopening
            from PySide6.QtCore import QTimer
            QTimer.singleShot(200, lambda: setattr(self, 'regex_menu_open', False))
        
        self.regex_menu.aboutToHide.connect(on_menu_hidden)
        
        # Show menu below button using popup (non-blocking)
        self.regex_menu.popup(self.regex_btn.mapToGlobal(self.regex_btn.rect().bottomLeft()))
    
    def toggle_regex_pattern(self, pattern_key, enabled):
        """Toggle a regex pattern on/off"""
        self.regex_patterns[pattern_key]['enabled'] = enabled
        self.update_search_with_regex_patterns()
        
        # Update button text to show active patterns count
        active_count = sum(1 for p in self.regex_patterns.values() if p['enabled'])
        if active_count > 0:
            self.regex_btn.setText(f"Regex Patterns ({active_count})")
            self.regex_btn.setStyleSheet("font-weight: bold;")
        else:
            self.regex_btn.setText("Regex Patterns")
            self.regex_btn.setStyleSheet("")
    
    def clear_all_regex_patterns(self):
        """Clear all selected regex patterns"""
        for pattern_info in self.regex_patterns.values():
            pattern_info['enabled'] = False
        self.update_search_with_regex_patterns()
        self.regex_btn.setText("Regex Patterns")
        self.regex_btn.setStyleSheet("")
    
    def update_search_with_regex_patterns(self):
        """Update search input with combined regex patterns"""
        enabled_patterns = [info['pattern'] for info in self.regex_patterns.values() if info['enabled']]
        
        if enabled_patterns:
            # Combine patterns with OR operator
            combined_pattern = '|'.join(f'({pattern})' for pattern in enabled_patterns)
            self.search_input.lineEdit().setText(combined_pattern)
            # Enable regex mode in search engine
            self.search_engine.set_regex(True)
        else:
            # If no patterns selected, keep current search text
            # and disable regex mode
            self.search_engine.set_regex(False)
    
    def show_dir_context_menu(self, position):
        """Show context menu for directory tree items"""
        item = self.dir_tree.itemAt(position)
        if not item:
            return
        
        data = item.data(0, Qt.UserRole)
        if not data or data.get("path") is None:
            return
        
        menu = QMenu()
        path = data["path"]
        is_file = data.get("is_file", False)
        
        if is_file:
            # File menu
            open_file_action = menu.addAction("Open File")
            open_file_action.triggered.connect(lambda: self.open_file(path))
            
            open_parent_action = menu.addAction("Open Parent Directory")
            open_parent_action.triggered.connect(lambda: self.open_file_directory(path))
        else:
            # Directory menu
            open_dir_action = menu.addAction("Open Directory")
            open_dir_action.triggered.connect(lambda: self.open_directory(path))
            
            parent_path = os.path.dirname(path)
            if parent_path and parent_path != path:
                open_parent_action = menu.addAction("Open Parent Directory")
                open_parent_action.triggered.connect(lambda: self.open_directory(parent_path))
        
        menu.exec(self.dir_tree.viewport().mapToGlobal(position))
    
    def open_directory(self, directory_path):
        """Open a directory in file explorer"""
        try:
            os.startfile(directory_path)
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Could not open directory: {str(e)}")
    
    def load_preferences(self):
        """Load preferences from file"""
        try:
            if os.path.exists(self.preferences_file):
                with open(self.preferences_file, 'r') as f:
                    saved_prefs = json.load(f)
                    self.preferences.update(saved_prefs)
        except Exception as e:
            print(f"Error loading preferences: {e}")
    
    def save_preferences(self):
        """Save preferences to file"""
        try:
            with open(self.preferences_file, 'w') as f:
                json.dump(self.preferences, f, indent=2)
        except Exception as e:
            print(f"Error saving preferences: {e}")
    
    def show_preferences(self):
        """Show preferences dialog"""
        dialog = PreferencesDialog(self, self.preferences)
        if dialog.exec() == QDialog.Accepted:
            # Update preferences
            self.preferences = dialog.get_preferences()
            self.save_preferences()
            
            # Apply new preferences
            self.max_cache_size = self.preferences['max_cache_size']
            self.max_file_size = self.preferences['max_preview_file_size_mb'] * 1024 * 1024
            self.search_engine.max_results = self.preferences['max_results']
            self.search_engine.max_search_file_size = self.preferences['max_search_file_size_mb'] * 1024 * 1024
            
            # Clear cache if size reduced
            if len(self.file_cache) > self.max_cache_size:
                # Keep only the last max_cache_size items
                keys = list(self.file_cache.keys())
                for key in keys[:-self.max_cache_size]:
                    del self.file_cache[key]
            
            self.status_bar.showMessage("Preferences updated", 3000)
    
    def start_search(self):
        """Start a new search"""
        pattern = self.search_input.currentText()
        root_path = self.current_directory
        
        if not pattern:
            QMessageBox.warning(self, "Warning", "Please enter a search pattern")
            return
        
        # Add to search history
        self.add_to_search_history(pattern)
        
        if not os.path.isdir(root_path):
            QMessageBox.warning(self, "Warning", "Please select a valid directory from the tree")
            return
        
        self.current_search_pattern = pattern
        
        # Update file extensions filter
        extensions_text = self.extensions_input.text().strip()
        if extensions_text:
            extensions = [ext.strip() for ext in extensions_text.split(',')]
            self.search_engine.set_file_extensions(extensions)
        else:
            self.search_engine.set_file_extensions([])
        
        # Clear previous results
        self.results_tree.clear()
        self.preview_text.clear()
        self.current_results = []
        
        # Update UI state
        self.search_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.status_bar.showMessage(f"Searching for '{pattern}'...")
        
        # Start search in background thread
        self.search_worker = SearchWorker(self.search_engine, root_path, pattern)
        self.search_worker.finished.connect(self.on_search_finished)
        self.search_worker.start()
    
    def stop_search(self):
        """Stop the current search"""
        if self.search_worker:
            self.search_worker.stop()
            self.search_worker.wait()
        self.on_search_finished([])
    
    def on_search_finished(self, results):
        """Handle search completion"""
        self.current_results = results
        
        # Group results by file
        files_dict = {}
        for match in results:
            if match.file_path not in files_dict:
                files_dict[match.file_path] = []
            files_dict[match.file_path].append(match)
        
        # Populate tree
        for file_path, matches in sorted(files_dict.items()):
            file_item = QTreeWidgetItem(self.results_tree)
            file_item.setText(0, file_path)
            file_item.setText(1, str(len(matches)))
            file_item.setData(0, Qt.UserRole, matches)
            
            # Add match items
            for match in matches:
                match_item = QTreeWidgetItem(file_item)
                match_item.setText(0, f"  Line {match.line_number}: {match.line_content[:80]}")
                match_item.setData(0, Qt.UserRole, match)
                self.results_tree.setUpdatesEnabled(True)  # Re-enable updates
                # Update UI state
        self.search_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        # Update status
        total_matches = len(results)
        total_files = len(files_dict)
        self.status_bar.showMessage(
            f"Found {total_matches} matches in {total_files} files"
        )
    
    def on_tree_item_clicked(self, item, column):
        """Handle tree item click"""
        data = item.data(0, Qt.UserRole)
        
        if isinstance(data, SearchMatch):
            # Single match - show full file with all matches
            matches = [data]
            # Try to find all matches for this file from results
            for result in self.current_results:
                if result.file_path == data.file_path and result != data:
                    matches.append(result)
            self.show_file_contents_with_matches(matches)
        elif isinstance(data, list):
            # File with multiple matches - show file contents with highlights
            self.show_file_contents_with_matches(data)
    
    def on_item_double_clicked(self, item, column):
        """Handle double-click to open file"""
        data = item.data(0, Qt.UserRole)
        
        if isinstance(data, SearchMatch):
            self.open_file(data.file_path, data.line_number)
        elif isinstance(data, list) and len(data) > 0:
            self.open_file(data[0].file_path)
    
    def show_file_contents_with_matches(self, matches):
        """Show full file contents with matched lines highlighted"""
        if not matches:
            self.current_file_matches = []
            self.current_match_index = 0
            self.update_match_navigation()
            return
        
        file_path = matches[0].file_path
        self.current_file_matches = matches
        self.current_match_index = 0
        self.preview_text.clear()
        
        try:
            # Check if this is an image file
            file_ext = os.path.splitext(file_path)[1].lower()
            image_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.gif', '.bmp', '.webp'}
            file_metadata_extensions = {'.pdf', '.docx', '.xlsx', '.pptx', '.mp3', '.flac', '.m4a', '.mp4', '.avi', '.mkv'}
            is_image = file_ext in image_extensions
            is_file_with_metadata = file_ext in file_metadata_extensions
            
            # If metadata search is enabled and this is an image, show image metadata
            if is_image and self.search_engine.search_metadata:
                self._display_image_metadata_preview(file_path, matches)
                return
            
            # If file metadata search is enabled and this has metadata, show file metadata
            if is_file_with_metadata and self.search_engine.search_file_metadata:
                self._display_file_metadata_preview(file_path, matches)
                return
            
            # Check file size first
            file_size = os.path.getsize(file_path)
            if file_size > self.max_file_size:
                self.preview_text.setPlainText(f"File too large to display ({file_size / 1024 / 1024:.1f}MB).\nMaximum size: {self.max_file_size / 1024 / 1024:.1f}MB")
                self.current_file_matches = []
                self.current_match_index = 0
                self.update_match_navigation()
                return
            
            # Check cache first
            if file_path in self.file_cache:
                cached_size, lines = self.file_cache[file_path]
                if cached_size == file_size:
                    # Use cached content
                    pass
                else:
                    # File changed, re-read
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    self._cache_file(file_path, file_size, lines)
            else:
                # Read entire file
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                self._cache_file(file_path, file_size, lines)
            
            # Build match line numbers set for quick lookup
            match_lines = {match.line_number for match in matches}
            
            # Display file with highlights (optimized with list comprehension)
            display_lines = [
                f"File: {file_path}",
                f"Total matches: {len(matches)}",
                "=" * 80,
                ""
            ]
            
            # Show all lines (optimized loop)
            display_lines.extend(
                f"{'>>> ' if i in match_lines else '    '}{i:5d} | {line.rstrip()}"
                for i, line in enumerate(lines, 1)
            )
            
            self.preview_text.setPlainText("\n".join(display_lines))
            
            # Highlight all matches
            self.highlight_all_matches()
            
            # Update navigation and go to first match
            self.update_match_navigation()
            if matches:
                self.jump_to_current_match()
                
        except Exception as e:
            self.preview_text.setPlainText(f"Error reading file: {str(e)}")
            self.current_file_matches = []
            self.current_match_index = 0
            self.update_match_navigation()
    
    def _display_image_metadata_preview(self, file_path, matches):
        """Display image metadata in preview pane"""
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS
            import os
            from datetime import datetime
            
            metadata = {}
            
            # Extract and display metadata
            with Image.open(file_path) as img:
                # File system info
                stat_info = os.stat(file_path)
                metadata['File_Size'] = f"{stat_info.st_size / 1024:.2f} KB"
                metadata['File_Created'] = datetime.fromtimestamp(stat_info.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
                metadata['File_Modified'] = datetime.fromtimestamp(stat_info.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                
                # Basic image info
                metadata['Format'] = img.format or 'Unknown'
                metadata['Mode'] = img.mode
                metadata['Size'] = f"{img.width}x{img.height}"
                
                # Try to get EXIF data using getexif() (newer API)
                try:
                    exif = img.getexif()
                    if exif:
                        for tag_id, value in exif.items():
                            tag_name = TAGS.get(tag_id, f"Tag_{tag_id}")
                            
                            # Handle GPS data specially
                            if tag_name == "GPSInfo":
                                try:
                                    gps_data = {GPSTAGS.get(gps_tag_id, f"GPS_{gps_tag_id}"): str(value[gps_tag_id]) 
                                               for gps_tag_id in value}
                                    metadata['GPS_Info'] = str(gps_data)
                                except:
                                    metadata['GPS_Info'] = str(value)
                            else:
                                # Convert value to string, handle bytes
                                if isinstance(value, bytes):
                                    try:
                                        value = value.decode('utf-8', errors='ignore')
                                    except:
                                        value = str(value)[:100]
                                elif isinstance(value, (tuple, list)) and len(str(value)) > 100:
                                    value = str(value)[:100] + "..."
                                metadata[tag_name] = str(value)
                except (AttributeError, KeyError, TypeError):
                    pass
                
                # PNG info
                if hasattr(img, 'info') and img.info:
                    for key, value in img.info.items():
                        if key not in metadata:
                            metadata[f"PNG_{key}"] = str(value)[:200]
            
            # Display using common metadata display method
            note = "This image has no EXIF metadata (typical for screenshots)" if len(metadata) <= 6 else None
            self._display_metadata_common(file_path, matches, metadata, "Image Metadata", note)
                
        except Exception as e:
            self.preview_text.setPlainText(f"Error reading image metadata: {str(e)}")
            self.current_file_matches = []
            self.current_match_index = 0
            self.update_match_navigation()
    
    def _display_file_metadata_preview(self, file_path, matches):
        """Display file metadata in preview pane (PDF, Office, audio, etc.)"""
        try:
            import os
            from datetime import datetime
            
            # Extract file metadata
            metadata = self.search_engine._extract_file_metadata(file_path)
            
            # Add file system info
            stat_info = os.stat(file_path)
            metadata['File_Size'] = f"{stat_info.st_size / 1024:.2f} KB"
            metadata['File_Created'] = datetime.fromtimestamp(stat_info.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
            metadata['File_Modified'] = datetime.fromtimestamp(stat_info.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            
            # Display using common metadata display method
            note = "No extractable metadata found for this file type" if len(metadata) <= 3 else None
            self._display_metadata_common(file_path, matches, metadata, "File Metadata", note)
                
        except Exception as e:
            self.preview_text.setPlainText(f"Error reading file metadata: {str(e)}")
            self.current_file_matches = []
            self.current_match_index = 0
            self.update_match_navigation()
    
    def _display_metadata_common(self, file_path, matches, metadata, header_text, note=None):
        """Common method to display metadata in preview pane"""
        display_lines = [
            f"{header_text}: {file_path}",
            f"Total matches: {len(matches)}",
            "=" * 80,
            ""
        ]
        
        if note:
            display_lines.append(f"    Note: {note}")
            display_lines.append("")
        
        # Build match line numbers set for quick lookup
        match_lines = {match.line_number for match in matches}
        
        # Display metadata with match indicators
        for line_num, (key, value) in enumerate(metadata.items(), start=1):
            line_text = f"{key}: {value}"
            prefix = '>>> ' if line_num in match_lines else '    '
            display_lines.append(f"{prefix}{line_num:5d} | {line_text}")
        
        self.preview_text.setPlainText("\n".join(display_lines))
        
        # Highlight all matches
        self.highlight_all_matches()
        
        # Update navigation and go to first match
        self.update_match_navigation()
        if matches:
            self.jump_to_current_match()
    
    def _cache_file(self, file_path, file_size, lines):
        """Cache file contents with LRU eviction"""
        # If cache is full, remove oldest entry
        if len(self.file_cache) >= self.max_cache_size:
            # Remove first (oldest) item
            first_key = next(iter(self.file_cache))
            del self.file_cache[first_key]
        
        self.file_cache[file_path] = (file_size, lines)
    
    def highlight_all_matches(self):
        """Highlight all search matches in the preview text (optimized)"""
        if not self.current_file_matches or not self.current_search_pattern:
            return
        
        # Get the search pattern for highlighting
        pattern = self.current_search_pattern
        
        # Build regex for highlighting
        try:
            if self.search_engine.use_regex:
                flags = 0 if self.search_engine.case_sensitive else re.IGNORECASE
                regex = re.compile(pattern, flags)
            else:
                escaped_pattern = re.escape(pattern)
                if self.search_engine.whole_word:
                    escaped_pattern = r'\b' + escaped_pattern + r'\b'
                flags = 0 if self.search_engine.case_sensitive else re.IGNORECASE
                regex = re.compile(escaped_pattern, flags)
        except re.error:
            return
        
        # Yellow highlight format
        highlight_format = QTextCharFormat()
        highlight_format.setBackground(QColor(255, 255, 0))
        
        # Get text once (optimization)
        text = self.preview_text.toPlainText()
        
        # Skip header (4 lines)
        header_lines = text.split('\n', 4)
        if len(header_lines) < 5:
            return
        header_length = sum(len(line) + 1 for line in header_lines[:4])
        
        # Batch highlight all matches (optimized)
        cursor = self.preview_text.textCursor()
        cursor.beginEditBlock()  # Batch operations
        
        for match in regex.finditer(text[header_length:]):
            cursor.setPosition(header_length + match.start())
            cursor.setPosition(header_length + match.end(), QTextCursor.KeepAnchor)
            cursor.mergeCharFormat(highlight_format)
        
        cursor.endEditBlock()  # Complete batch
    
    def jump_to_current_match(self):
        """Jump to the current match in preview"""
        if not self.current_file_matches or self.current_match_index >= len(self.current_file_matches):
            return
        
        match = self.current_file_matches[self.current_match_index]
        
        # Re-highlight all matches first (to reset orange highlight)
        self.highlight_all_matches()
        
        # Find header position (skip first 4 lines)
        header_cursor = QTextCursor(self.preview_text.document())
        header_cursor.movePosition(QTextCursor.Start)
        for _ in range(4):
            header_cursor.movePosition(QTextCursor.Down)
        header_pos = header_cursor.position()
        
        # Find all matches in the preview text (after header)
        text = self.preview_text.toPlainText()
        
        # Build regex for finding matches
        try:
            pattern = self.current_search_pattern
            if self.search_engine.use_regex:
                flags = 0 if self.search_engine.case_sensitive else re.IGNORECASE
                regex = re.compile(pattern, flags)
            else:
                escaped_pattern = re.escape(pattern)
                if self.search_engine.whole_word:
                    escaped_pattern = r'\b' + escaped_pattern + r'\b'
                flags = 0 if self.search_engine.case_sensitive else re.IGNORECASE
                regex = re.compile(escaped_pattern, flags)
            
            # Find all matches after header only
            all_matches = [m for m in regex.finditer(text) if m.start() >= header_pos]
            
            if self.current_match_index < len(all_matches):
                match_obj = all_matches[self.current_match_index]
                
                # Create cursor and select the match
                cursor = QTextCursor(self.preview_text.document())
                cursor.setPosition(match_obj.start())
                cursor.setPosition(match_obj.end(), QTextCursor.KeepAnchor)
                
                # Apply orange highlight to current match
                current_format = QTextCharFormat()
                current_format.setBackground(QColor(255, 165, 0))  # Orange
                cursor.mergeCharFormat(current_format)
                
                # Move cursor to this position and ensure visible
                cursor.setPosition(match_obj.start())
                self.preview_text.setTextCursor(cursor)
                self.preview_text.ensureCursorVisible()
                
        except re.error:
            pass
    
    def update_match_navigation(self):
        """Update match counter and navigation button states"""
        if not self.current_file_matches:
            self.match_counter_label.setText("0/0")
            self.prev_match_btn.setEnabled(False)
            self.next_match_btn.setEnabled(False)
        else:
            total = len(self.current_file_matches)
            current = self.current_match_index + 1
            self.match_counter_label.setText(f"{current}/{total}")
            # Always enable buttons if there are matches (cycling enabled)
            self.prev_match_btn.setEnabled(True)
            self.next_match_btn.setEnabled(True)
    
    def go_to_previous_match(self):
        """Navigate to previous match (wraps to last)"""
        if not self.current_file_matches:
            return
        
        if self.current_match_index > 0:
            self.current_match_index -= 1
        else:
            # Wrap to last match
            self.current_match_index = len(self.current_file_matches) - 1
        
        self.highlight_all_matches()  # Re-highlight all
        self.jump_to_current_match()
        self.update_match_navigation()
    
    def go_to_next_match(self):
        """Navigate to next match (wraps to first)"""
        if not self.current_file_matches:
            return
        
        if self.current_match_index < len(self.current_file_matches) - 1:
            self.current_match_index += 1
        else:
            # Wrap to first match
            self.current_match_index = 0
        
        self.highlight_all_matches()  # Re-highlight all
        self.jump_to_current_match()
        self.update_match_navigation()
    
    def show_context_menu(self, position):
        """Show context menu for tree items"""
        item = self.results_tree.itemAt(position)
        if not item:
            return
        
        menu = QMenu()
        
        # Get data from item
        data = item.data(0, Qt.UserRole)
        
        if isinstance(data, SearchMatch):
            # Single match
            open_action = menu.addAction("Open")
            open_action.triggered.connect(lambda: self.open_file(data.file_path, data.line_number))
            
            open_dir_action = menu.addAction("Open File Directory")
            open_dir_action.triggered.connect(lambda: self.open_file_directory(data.file_path))
            
            menu.addSeparator()
            
            copy_path_action = menu.addAction("Copy File Path")
            copy_path_action.triggered.connect(lambda: QApplication.clipboard().setText(data.file_path))
            
            copy_line_action = menu.addAction("Copy Line Content")
            copy_line_action.triggered.connect(lambda: QApplication.clipboard().setText(data.line_content))
            
        elif isinstance(data, list) and len(data) > 0:
            # File with multiple matches
            open_action = menu.addAction("Open")
            open_action.triggered.connect(lambda: self.open_file(data[0].file_path))
            
            open_dir_action = menu.addAction("Open Folder Directory")
            open_dir_action.triggered.connect(lambda: self.open_file_directory(data[0].file_path))
            
            menu.addSeparator()
            
            copy_path_action = menu.addAction("Copy File Path")
            copy_path_action.triggered.connect(lambda: QApplication.clipboard().setText(data[0].file_path))
            
            menu.addSeparator()
            
            expand_action = menu.addAction("Expand All")
            expand_action.triggered.connect(lambda: item.setExpanded(True))
            
            collapse_action = menu.addAction("Collapse All")
            collapse_action.triggered.connect(lambda: item.setExpanded(False))
        
        menu.exec(self.results_tree.viewport().mapToGlobal(position))
    
    def open_file(self, file_path, line_number=None):
        """Open file in default editor"""
        try:
            if line_number:
                # Try to open with VS Code if available
                try:
                    subprocess.Popen(['code', '-g', f'{file_path}:{line_number}'])
                except FileNotFoundError:
                    # VS Code not available, just open the file
                    os.startfile(file_path)
            else:
                # Use default application
                os.startfile(file_path)
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Could not open file: {str(e)}")
    
    def open_file_directory(self, file_path):
        """Open the directory containing the file"""
        try:
            directory = os.path.dirname(file_path)
            os.startfile(directory)
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Could not open directory: {str(e)}")
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About Advanced Search Tool",
            "<h3>Advanced Search Tool</h3>"
            "<p>Version 0.3.0-alpha</p>"
            "<p>Author: Randy Northrup</p>"
            "<p>A Windows GUI application for grep-style searching with advanced regex patterns and metadata search.</p>"
            "<p><b>Key Features:</b></p>"
            "<ul>"
            "<li>Grep-style pattern search with full regex support</li>"
            "<li>8 common regex patterns in quick-access menu</li>"
            "<li>Image metadata search (EXIF, GPS) for JPG, PNG, TIFF, etc.</li>"
            "<li>File metadata search (PDF, Office docs, audio/video)</li>"
            "<li>File browser with organized results tree</li>"
            "<li>Context display and syntax highlighting</li>"
            "<li>Performance optimizations and caching</li>"
            "</ul>"
            "<p>Built with Python, PySide6, Pillow, PyPDF2, and more</p>"
        )
    
    def load_search_history(self):
        """Load search history from file"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.search_history = json.load(f)
                    # Limit to last 50 entries
                    self.search_history = self.search_history[-50:]
        except Exception as e:
            print(f"Failed to load search history: {e}")
            self.search_history = []
    
    def save_search_history(self):
        """Save search history to file"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.search_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save search history: {e}")
    
    def add_to_search_history(self, pattern):
        """Add a search pattern to history"""
        if not pattern or pattern.strip() == "":
            return
        
        # Remove if already exists (to move to end)
        if pattern in self.search_history:
            self.search_history.remove(pattern)
        
        # Add to end
        self.search_history.append(pattern)
        
        # Limit to 50 entries
        if len(self.search_history) > 50:
            self.search_history = self.search_history[-50:]
        
        # Update dropdown and save
        self.update_search_history_dropdown()
        self.save_search_history()
    
    def update_search_history_dropdown(self):
        """Update the search input dropdown with history"""
        self.search_input.clear()
        # Add history in reverse order (most recent first)
        for pattern in reversed(self.search_history):
            self.search_input.addItem(pattern)
    
    def clear_search_history(self):
        """Clear all search history"""
        reply = QMessageBox.question(
            self,
            "Clear Search History",
            "Are you sure you want to clear all search history?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.search_history = []
            self.update_search_history_dropdown()
            self.save_search_history()
            QMessageBox.information(self, "Success", "Search history has been cleared.")


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
