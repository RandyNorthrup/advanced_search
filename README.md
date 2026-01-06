# Advanced Search Tool

<div align="center">

![Version](https://img.shields.io/badge/version-0.1.0--alpha-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![License](https://img.shields.io/badge/license-MIT-orange)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

**A powerful Windows GUI application for grep-style searching with an intuitive file browser interface**

[Features](#features) • [Installation](#installation) • [Usage](#usage) • [Screenshots](#screenshots) • [Contributing](#contributing)

</div>

---

## 📋 Overview

Advanced Search Tool is a modern, high-performance desktop application that brings the power of grep-style pattern searching to Windows users with a beautiful, easy-to-use graphical interface. Search through thousands of files quickly, navigate results effortlessly, and open files directly from the app.

## ✨ Features

### Core Functionality
- 🔍 **Powerful Search Engine** - Fast grep-style pattern matching across files and directories
- 🔄 **Regex Support** - Full regular expression support for complex pattern matching
- 📁 **File Browser** - Integrated file explorer with lazy loading for smooth navigation
- 🎯 **Smart Highlighting** - Yellow highlights for all matches, orange for current match
- 📊 **Results Tree** - Organized results grouped by file with match counts

### Advanced Capabilities
- ⚡ **Performance Optimized** 
  - Multi-threaded search engine
  - File content caching (LRU eviction)
  - Batch UI updates
  - Configurable file size limits
- 🎨 **Modern UI**
  - Fluent Design icons
  - Three-panel layout (Explorer | Results | Preview)
  - Responsive interface with progress indicators
- 🔧 **Flexible Options**
  - Case-sensitive search
  - Whole word matching
  - Configurable context lines
  - File extension filtering
- 💾 **Persistent Settings**
  - Search history with auto-complete
  - User preferences (file size limits, cache size, max results)
  - Session state preservation

### Navigation & Workflow
- ⬆️⬇️ **Match Navigation** - Cycle through matches with keyboard shortcuts or buttons
- 🖱️ **Context Menus** - Right-click for quick actions (open, copy path, etc.)
- 📂 **Direct File Access** - Double-click to open files in default editor
- 🔗 **VS Code Integration** - Opens files at specific line numbers if VS Code is installed

## 🚀 Installation

### Option 1: Download Executable (Recommended)
1. Download the latest `AdvancedSearch.exe` from [Releases](../../releases)
2. Run the executable - no installation required!

### Option 2: Run from Source

**Requirements:**
- Python 3.8 or higher
- Windows OS

**Steps:**
```bash
# Clone the repository
git clone https://github.com/yourusername/advanced_search.git
cd advanced_search

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

## 📖 Usage

### Quick Start
1. **Select Directory** - Click on a folder in the left panel (File Explorer)
2. **Enter Pattern** - Type your search term in the search box
3. **Configure Options** - Set case sensitivity, regex mode, file extensions, etc.
4. **Search** - Click "Search" or press Enter
5. **Browse Results** - Click on results to preview, double-click to open files

### Search Options

| Option | Description |
|--------|-------------|
| **Case Sensitive** | Match exact case |
| **Use Regex** | Enable regular expression patterns |
| **Whole Word** | Match complete words only |
| **Context** | Lines of context to show (0-10) |
| **Extensions** | Filter by file extensions (e.g., `.py,.txt,.js`) |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Start search |
| `Ctrl+Up` | Previous match |
| `Ctrl+Down` | Next match |
| `Ctrl+Q` | Quit application |

### Preferences

Access preferences via **Settings → Preferences** to configure:
- **Max Search Results** - Limit total results (0 = unlimited)
- **Max Preview File Size** - Maximum file size to display (MB)
- **Max Search File Size** - Maximum file size to search (MB)
- **File Cache Size** - Number of files to cache in memory

## 📸 Screenshots

*Screenshots coming soon*

## 🏗️ Architecture

```
advanced_search/
├── assets/              # Icons and images
│   ├── icon.svg
│   ├── chevron_up.svg
│   └── chevron_down.svg
├── src/                 # Source code
│   ├── main.py         # Main application & GUI
│   └── search_engine.py # Core search functionality
├── main.py             # Application entry point
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

### Technology Stack
- **GUI Framework:** PySide6 (Qt6)
- **Search Engine:** Python `re` module with optimizations
- **Threading:** QThread for background operations
- **Persistence:** JSON for settings and history

## 🛠️ Development

### Building from Source
```bash
# Install development dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Creating Executable
The project includes a GitHub Actions workflow that automatically builds executables on push:

```bash
# Or build manually with PyInstaller
pip install pyinstaller
pyinstaller --name="AdvancedSearch" --windowed --onefile --icon=assets/icon.ico main.py
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👤 Author

**Randy Northrup**

## 🙏 Acknowledgments

- Icons by [Icons8](https://icons8.com)
- Built with [PySide6](https://wiki.qt.io/Qt_for_Python)

## 📮 Support

If you encounter any issues or have suggestions, please [open an issue](../../issues).

---

<div align="center">
Made with ❤️ by Randy Northrup
</div>
