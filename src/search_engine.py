"""
Search engine module for grep-style searching
"""
import os
import re
from typing import List, Dict, Any
from dataclasses import dataclass

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    from mutagen import File as MutagenFile
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


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
    
    # Class constants for supported file types
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.gif', '.bmp', '.webp'}
    FILE_METADATA_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.pptx', '.mp3', '.flac', '.m4a', '.mp4', '.avi', '.mkv'}
    
    def __init__(self):
        self.case_sensitive = False
        self.use_regex = False
        self.whole_word = False
        self.search_metadata = False  # Image metadata
        self.search_file_metadata = False  # File metadata (PDF, Office, audio, video)
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
            
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # Check if this is an image file and image metadata search is enabled
            if self.search_metadata and file_ext in self.IMAGE_EXTENSIONS:
                # Search ONLY image metadata when metadata search is enabled
                metadata_matches = self._search_image_metadata(file_path, regex)
                matches.extend(metadata_matches)
                return matches  # Skip text search for images
            
            # Check if this is a file with metadata and file metadata search is enabled
            if self.search_file_metadata and file_ext in self.FILE_METADATA_EXTENSIONS:
                # Search ONLY file metadata when file metadata search is enabled
                metadata_matches = self._search_file_metadata(file_path, regex)
                matches.extend(metadata_matches)
                return matches  # Skip text search for these files
            
            # If either metadata search is enabled but this file doesn't match, skip it
            if self.search_metadata or self.search_file_metadata:
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
    
    def _search_image_metadata(self, file_path: str, regex: re.Pattern) -> List[SearchMatch]:
        """Search image metadata for pattern matches"""
        matches = []
        
        if not PILLOW_AVAILABLE:
            return matches
        
        try:
            with Image.open(file_path) as img:
                metadata = self._extract_image_metadata(img)
                
                # Convert metadata to searchable text
                line_num = 1
                for key, value in metadata.items():
                    # Create searchable line from metadata
                    line_text = f"{key}: {value}"
                    
                    # Search for matches in this metadata line
                    for match in regex.finditer(line_text):
                        search_match = SearchMatch(
                            file_path=file_path,
                            line_number=line_num,
                            line_content=line_text,
                            match_start=match.start(),
                            match_end=match.end(),
                            context_before=[],
                            context_after=[]
                        )
                        matches.append(search_match)
                    
                    line_num += 1
        
        except Exception:
            # Skip files that can't be opened as images
            pass
        
        return matches
    
    def _extract_image_metadata(self, img: 'Image.Image') -> Dict[str, Any]:
        """Extract metadata from an image"""
        metadata = {}
        
        # Basic image info
        metadata['Format'] = img.format or 'Unknown'
        metadata['Mode'] = img.mode
        metadata['Size'] = f"{img.width}x{img.height}"
        
        # EXIF data
        try:
            exif_data = img._getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, f"Unknown_{tag_id}")
                    
                    # Handle GPS data specially
                    if tag_name == "GPSInfo":
                        gps_data = {}
                        for gps_tag_id, gps_value in value.items():
                            gps_tag_name = GPSTAGS.get(gps_tag_id, f"GPS_{gps_tag_id}")
                            gps_data[gps_tag_name] = str(gps_value)
                        metadata[tag_name] = str(gps_data)
                    else:
                        # Convert value to string, handle bytes
                        if isinstance(value, bytes):
                            try:
                                value = value.decode('utf-8', errors='ignore')
                            except:
                                value = str(value)
                        metadata[tag_name] = str(value)
        except (AttributeError, KeyError, TypeError):
            pass
        
        # PNG info
        if hasattr(img, 'info'):
            for key, value in img.info.items():
                if key not in metadata:
                    metadata[f"PNG_{key}"] = str(value)
        
        return metadata
    
    def _search_file_metadata(self, file_path: str, regex: re.Pattern) -> List[SearchMatch]:
        """Search file metadata for pattern matches"""
        matches = []
        metadata = self._extract_file_metadata(file_path)
        
        # Convert metadata to searchable text
        line_num = 1
        for key, value in metadata.items():
            # Create searchable line from metadata
            line_text = f"{key}: {value}"
            
            # Search for matches in this metadata line
            for match in regex.finditer(line_text):
                search_match = SearchMatch(
                    file_path=file_path,
                    line_number=line_num,
                    line_content=line_text,
                    match_start=match.start(),
                    match_end=match.end(),
                    context_before=[],
                    context_after=[]
                )
                matches.append(search_match)
            
            line_num += 1
        
        return matches
    
    def _extract_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata from various file types"""
        metadata = {}
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            # PDF files
            if file_ext == '.pdf' and PYPDF2_AVAILABLE:
                with open(file_path, 'rb') as f:
                    pdf = PyPDF2.PdfReader(f)
                    if pdf.metadata:
                        for key, value in pdf.metadata.items():
                            metadata[f"PDF_{key.strip('/')}"] = str(value)[:200]
                    metadata['PDF_Pages'] = str(len(pdf.pages))
            
            # Word documents
            elif file_ext == '.docx' and DOCX_AVAILABLE:
                doc = docx.Document(file_path)
                props = doc.core_properties
                if props.author: metadata['Author'] = props.author
                if props.title: metadata['Title'] = props.title
                if props.subject: metadata['Subject'] = props.subject
                if props.keywords: metadata['Keywords'] = props.keywords
                if props.category: metadata['Category'] = props.category
                if props.comments: metadata['Comments'] = props.comments[:200]
                if props.created: metadata['Created'] = str(props.created)
                if props.modified: metadata['Modified'] = str(props.modified)
                metadata['Paragraphs'] = str(len(doc.paragraphs))
            
            # Excel files
            elif file_ext == '.xlsx' and OPENPYXL_AVAILABLE:
                wb = openpyxl.load_workbook(file_path, read_only=True)
                props = wb.properties
                if props.creator: metadata['Creator'] = props.creator
                if props.title: metadata['Title'] = props.title
                if props.subject: metadata['Subject'] = props.subject
                if props.keywords: metadata['Keywords'] = props.keywords
                if props.category: metadata['Category'] = props.category
                if props.description: metadata['Description'] = props.description[:200]
                if props.created: metadata['Created'] = str(props.created)
                if props.modified: metadata['Modified'] = str(props.modified)
                metadata['Sheets'] = str(len(wb.sheetnames))
                wb.close()
            
            # Audio files (MP3, FLAC, M4A, etc.)
            elif file_ext in {'.mp3', '.flac', '.m4a', '.ogg', '.wma'} and MUTAGEN_AVAILABLE:
                audio = MutagenFile(file_path)
                if audio and audio.tags:
                    for key, value in audio.tags.items():
                        # Clean up tag name
                        clean_key = str(key).replace('\x00', '')
                        metadata[f"Audio_{clean_key}"] = str(value)[:200]
                if audio and hasattr(audio.info, 'length'):
                    metadata['Duration'] = f"{int(audio.info.length // 60)}:{int(audio.info.length % 60):02d}"
                if audio and hasattr(audio.info, 'bitrate'):
                    metadata['Bitrate'] = f"{audio.info.bitrate // 1000} kbps"
        
        except Exception as e:
            # If metadata extraction fails, just skip this file
            pass
        
        return metadata
    
    def set_case_sensitive(self, enabled: bool):
        """Enable or disable case-sensitive search"""
        self.case_sensitive = enabled
    
    def set_regex(self, enabled: bool):
        """Enable or disable regex search"""
        self.use_regex = enabled
    
    def set_whole_word(self, enabled: bool):
        """Enable or disable whole word search"""
        self.whole_word = enabled
    
    def set_search_metadata(self, enabled: bool):
        """Enable or disable metadata search for images"""
        self.search_metadata = enabled
    
    def set_search_file_metadata(self, enabled: bool):
        """Enable or disable metadata search for files (PDF, Office, audio, video)"""
        self.search_file_metadata = enabled
    
    def set_context_lines(self, lines: int):
        """Set number of context lines to include"""
        self.context_lines = max(0, lines)
    
    def set_file_extensions(self, extensions: List[str]):
        """Set file extensions to filter (e.g., ['.py', '.txt'])"""
        self.file_extensions = extensions
    
    def add_exclude_pattern(self, pattern: str):
        """Add a pattern to exclude from search"""
        self.exclude_patterns.append(pattern)
