"""
Search engine module for grep-style searching
"""
import os
import re
from typing import List
from dataclasses import dataclass


@dataclass
class SearchMatch:
    """Represents a search match in a file"""
    file_path: str
    line_number: int
    line_content: str
    match_start: int
    match_end: int
    context_before: List[str]
    context_after: List[str]


class SearchEngine:
    """Grep-style search engine"""
    
    def __init__(self):
        self.case_sensitive = False
        self.use_regex = False
        self.whole_word = False
        self.context_lines = 2
        self.file_extensions = []  # Empty means all files
        self.max_results = 0  # 0 = unlimited
        self.max_search_file_size = 50 * 1024 * 1024  # 50MB default
        self.exclude_patterns = [
            r'\.git', r'\.svn', r'__pycache__', r'node_modules',
            r'\.pyc$', r'\.exe$', r'\.dll$', r'\.so$', r'\.bin$'
        ]
    
    def search(self, root_path: str, pattern: str) -> List[SearchMatch]:
        """
        Search for pattern in files under root_path or in a specific file
        
        Args:
            root_path: Directory to search in or specific file path
            pattern: Search pattern (text or regex)
            
        Returns:
            List of SearchMatch objects
        """
        matches = []
        
        if not pattern:
            return matches
        
        # Compile regex pattern
        try:
            if self.use_regex:
                flags = 0 if self.case_sensitive else re.IGNORECASE
                regex = re.compile(pattern, flags)
            else:
                # Escape special regex characters for literal search
                escaped_pattern = re.escape(pattern)
                if self.whole_word:
                    escaped_pattern = r'\b' + escaped_pattern + r'\b'
                flags = 0 if self.case_sensitive else re.IGNORECASE
                regex = re.compile(escaped_pattern, flags)
        except re.error as e:
            print(f"Invalid regex pattern: {e}")
            return matches
        
        # Check if root_path is a file or directory
        if os.path.isfile(root_path):
            # Search in single file
            if not self._is_excluded(root_path):
                # Check file extension filter
                if not self.file_extensions or any(root_path.endswith(ext) for ext in self.file_extensions):
                    file_matches = self._search_file(root_path, regex)
                    matches.extend(file_matches)
        else:
            # Walk directory tree
            for root, dirs, files in os.walk(root_path):
                # Early exit if max results reached (when limit is set)
                if self.max_results > 0 and len(matches) >= self.max_results:
                    break
                    
                # Filter out excluded directories
                dirs[:] = [d for d in dirs if not self._is_excluded(os.path.join(root, d))]
                
                for file in files:
                    # Early exit if max results reached (when limit is set)
                    if self.max_results > 0 and len(matches) >= self.max_results:
                        break
                        
                    file_path = os.path.join(root, file)
                    
                    # Skip excluded files
                    if self._is_excluded(file_path):
                        continue
                    
                    # Check file extension filter
                    if self.file_extensions:
                        if not any(file.endswith(ext) for ext in self.file_extensions):
                            continue
                    
                    # Search in file
                    file_matches = self._search_file(file_path, regex)
                    matches.extend(file_matches)
        
        return matches
    
    def _is_excluded(self, path: str) -> bool:
        """Check if path should be excluded"""
        path = path.replace('\\', '/')
        for pattern in self.exclude_patterns:
            if re.search(pattern, path):
                return True
        return False
    
    def _search_file(self, file_path: str, regex: re.Pattern) -> List[SearchMatch]:
        """Search for pattern in a single file (optimized)"""
        matches = []
        
        try:
            # Check file size first (skip very large files)
            file_size = os.path.getsize(file_path)
            if file_size > self.max_search_file_size:
                return matches
            
            # Try to read as text file
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Search each line
            for i, line in enumerate(lines):
                for match in regex.finditer(line):
                    # Get context lines
                    context_before = []
                    context_after = []
                    
                    start_idx = max(0, i - self.context_lines)
                    end_idx = min(len(lines), i + self.context_lines + 1)
                    
                    if self.context_lines > 0:
                        context_before = [lines[j].rstrip('\n\r') for j in range(start_idx, i)]
                        context_after = [lines[j].rstrip('\n\r') for j in range(i + 1, end_idx)]
                    
                    search_match = SearchMatch(
                        file_path=file_path,
                        line_number=i + 1,  # 1-based line numbers
                        line_content=line.rstrip('\n\r'),
                        match_start=match.start(),
                        match_end=match.end(),
                        context_before=context_before,
                        context_after=context_after
                    )
                    matches.append(search_match)
        
        except (IOError, OSError, UnicodeDecodeError):
            # Skip files that can't be read
            pass
        
        return matches
    
    def set_case_sensitive(self, enabled: bool):
        """Enable or disable case-sensitive search"""
        self.case_sensitive = enabled
    
    def set_regex(self, enabled: bool):
        """Enable or disable regex search"""
        self.use_regex = enabled
    
    def set_whole_word(self, enabled: bool):
        """Enable or disable whole word search"""
        self.whole_word = enabled
    
    def set_context_lines(self, lines: int):
        """Set number of context lines to include"""
        self.context_lines = max(0, lines)
    
    def set_file_extensions(self, extensions: List[str]):
        """Set file extensions to filter (e.g., ['.py', '.txt'])"""
        self.file_extensions = extensions
    
    def add_exclude_pattern(self, pattern: str):
        """Add a pattern to exclude from search"""
        self.exclude_patterns.append(pattern)
