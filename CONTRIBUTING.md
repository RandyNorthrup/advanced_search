# Contributing to Advanced Search Tool

Thank you for your interest in contributing to Advanced Search Tool! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow

## How to Contribute

### Reporting Bugs

If you find a bug, please create an issue with:
- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Screenshots if applicable
- Your environment (Windows version, Python version)

### Suggesting Features

Feature requests are welcome! Please:
- Check if it's already been suggested
- Clearly describe the feature and its benefits
- Provide use cases

### Pull Requests

1. **Fork the repository**
   ```bash
   git clone https://github.com/yourusername/advanced_search.git
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow the existing code style
   - Add comments for complex logic
   - Keep functions focused and small

4. **Test your changes**
   - Run the application and test thoroughly
   - Test edge cases
   - Ensure no regressions

5. **Commit your changes**
   ```bash
   git commit -m "Add feature: description"
   ```

6. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Create a Pull Request**
   - Provide a clear description
   - Reference any related issues
   - List what was changed and why

## Development Setup

### Requirements
- Python 3.8+
- Windows OS (for testing)

### Installation
```bash
# Clone the repository
git clone https://github.com/yourusername/advanced_search.git
cd advanced_search

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

## Code Style

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep lines under 120 characters when possible

### Example
```python
def search_files(self, pattern: str, root_path: str) -> List[SearchMatch]:
    """
    Search for pattern in files under root_path
    
    Args:
        pattern: Search pattern (text or regex)
        root_path: Directory to search in
        
    Returns:
        List of SearchMatch objects
    """
    # Implementation
    pass
```

## Project Structure

```
advanced_search/
├── .github/
│   └── workflows/       # GitHub Actions
├── assets/             # Icons and resources
├── src/                # Source code
│   ├── main.py        # Main GUI application
│   └── search_engine.py # Search functionality
├── main.py            # Entry point
├── requirements.txt   # Dependencies
└── README.md         # Documentation
```

## Testing

Currently, manual testing is used. Automated tests are welcome contributions!

Areas to test:
- Search functionality (text, regex, case-sensitive)
- File operations (open, preview, navigate)
- UI interactions (buttons, menus, shortcuts)
- Edge cases (large files, many results, special characters)

## Building Executables

```bash
pip install pyinstaller
pyinstaller --name="AdvancedSearch" --windowed --onefile --add-data "assets;assets" main.py
```

## Questions?

Feel free to open an issue for any questions or clarifications.

Thank you for contributing! 🎉
