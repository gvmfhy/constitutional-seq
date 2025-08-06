"""Input parsing for various file formats."""

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import openpyxl
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class InputParser:
    """Parser for various input file formats."""
    
    # Common encodings to try
    ENCODINGS = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
    
    # Common delimiters
    DELIMITERS = [',', '\t', ';', '|']
    
    def __init__(self):
        """Initialize the parser."""
        self.last_format = None
        self.last_encoding = None
        self.last_delimiter = None
    
    def parse_file(self, file_path: Union[str, Path], 
                   encoding: Optional[str] = None,
                   delimiter: Optional[str] = None) -> List[str]:
        """
        Parse a file and extract gene names/symbols.
        
        Args:
            file_path: Path to input file
            encoding: File encoding (auto-detected if None)
            delimiter: Delimiter for CSV files (auto-detected if None)
            
        Returns:
            List of gene names/symbols
            
        Raises:
            ValueError: If file format is not supported
            FileNotFoundError: If file doesn't exist
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {file_path}")
        
        # Determine file format
        suffix = path.suffix.lower()
        
        if suffix in ['.txt', '.text']:
            return self._parse_text_file(path, encoding)
        elif suffix in ['.csv', '.tsv']:
            return self._parse_csv_file(path, encoding, delimiter)
        elif suffix in ['.xlsx', '.xls']:
            return self._parse_excel_file(path)
        elif suffix == '.json':
            return self._parse_json_file(path, encoding)
        else:
            # Try to detect format by content
            return self._parse_auto_detect(path, encoding, delimiter)
    
    def _parse_text_file(self, path: Path, encoding: Optional[str] = None) -> List[str]:
        """Parse plain text file with one gene per line."""
        encoding = encoding or self._detect_encoding(path)
        genes = []
        
        with open(path, 'r', encoding=encoding) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):  # Skip comments
                    # Handle comma or tab separated values on same line
                    if ',' in line or '\t' in line:
                        delimiter = ',' if ',' in line else '\t'
                        genes.extend(part.strip() for part in line.split(delimiter) if part.strip())
                    else:
                        genes.append(line)
        
        self.last_format = 'text'
        self.last_encoding = encoding
        return genes
    
    def _parse_csv_file(self, path: Path, 
                        encoding: Optional[str] = None,
                        delimiter: Optional[str] = None) -> List[str]:
        """Parse CSV/TSV file."""
        encoding = encoding or self._detect_encoding(path)
        delimiter = delimiter or self._detect_delimiter(path, encoding)
        
        genes = []
        
        with open(path, 'r', encoding=encoding, newline='') as f:
            reader = csv.reader(f, delimiter=delimiter)
            
            # Try to detect if there's a header
            first_row = next(reader, None)
            if not first_row:
                return genes
            
            # Check if first row looks like a header
            has_header = False
            if first_row:
                for cell in first_row:
                    if isinstance(cell, str) and any(keyword in cell.lower() for keyword in ['gene', 'symbol', 'name', 'hugo']):
                        has_header = True
                        break
            
            if has_header:
                # Find the column with gene names
                gene_col = self._find_gene_column(first_row)
                if gene_col is not None:
                    for row in reader:
                        if gene_col < len(row) and row[gene_col].strip():
                            genes.append(row[gene_col].strip())
                else:
                    # No obvious gene column, take first column
                    for row in reader:
                        if row and row[0].strip():
                            genes.append(row[0].strip())
            else:
                # No header, process first row
                genes.extend(cell.strip() for cell in first_row if cell.strip())
                # Process remaining rows
                for row in reader:
                    genes.extend(cell.strip() for cell in row if cell.strip())
        
        self.last_format = 'csv'
        self.last_encoding = encoding
        self.last_delimiter = delimiter
        return genes
    
    def _parse_excel_file(self, path: Path) -> List[str]:
        """Parse Excel file."""
        if PANDAS_AVAILABLE:
            return self._parse_excel_pandas(path)
        elif EXCEL_AVAILABLE:
            return self._parse_excel_openpyxl(path)
        else:
            raise ImportError(
                "Excel parsing requires either pandas or openpyxl. "
                "Install with: pip install pandas or pip install openpyxl"
            )
    
    def _parse_excel_pandas(self, path: Path) -> List[str]:
        """Parse Excel using pandas."""
        genes = []
        
        # Read all sheets
        xls = pd.ExcelFile(path)
        
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            
            # Find gene column
            gene_col = None
            for col in df.columns:
                if isinstance(col, str) and col.lower() in ['gene', 'symbol', 'name', 'gene_symbol', 'gene_name']:
                    gene_col = col
                    break
            
            if gene_col:
                genes.extend(df[gene_col].dropna().astype(str).str.strip().tolist())
            else:
                # Take first column
                first_col = df.iloc[:, 0]
                genes.extend(first_col.dropna().astype(str).str.strip().tolist())
        
        self.last_format = 'excel'
        return genes
    
    def _parse_excel_openpyxl(self, path: Path) -> List[str]:
        """Parse Excel using openpyxl."""
        genes = []
        wb = openpyxl.load_workbook(path, read_only=True)
        
        for sheet in wb.worksheets:
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                continue
            
            # Check for header
            first_row = rows[0]
            gene_col = self._find_gene_column(first_row) if first_row else None
            
            if gene_col is not None:
                # Skip header row
                for row in rows[1:]:
                    if row and gene_col < len(row) and row[gene_col]:
                        genes.append(str(row[gene_col]).strip())
            else:
                # No header, take all non-empty cells
                for row in rows:
                    if row:
                        genes.extend(str(cell).strip() for cell in row if cell)
        
        wb.close()
        self.last_format = 'excel'
        return genes
    
    def _parse_json_file(self, path: Path, encoding: Optional[str] = None) -> List[str]:
        """Parse JSON file."""
        encoding = encoding or self._detect_encoding(path)
        
        with open(path, 'r', encoding=encoding) as f:
            data = json.load(f)
        
        genes = []
        
        # Handle various JSON structures
        if isinstance(data, list):
            # List of strings or objects
            for item in data:
                if isinstance(item, str):
                    genes.append(item.strip())
                elif isinstance(item, dict):
                    # Look for gene-related keys
                    for key in ['gene', 'symbol', 'name', 'gene_symbol', 'gene_name']:
                        if key in item:
                            genes.append(str(item[key]).strip())
                            break
        elif isinstance(data, dict):
            # Look for gene list in dictionary
            for key in ['genes', 'gene_list', 'symbols', 'names']:
                if key in data and isinstance(data[key], list):
                    genes.extend(str(g).strip() for g in data[key] if g)
                    break
        
        self.last_format = 'json'
        self.last_encoding = encoding
        return genes
    
    def _parse_auto_detect(self, path: Path, 
                          encoding: Optional[str] = None,
                          delimiter: Optional[str] = None) -> List[str]:
        """Auto-detect file format and parse."""
        # Try as CSV first
        try:
            genes = self._parse_csv_file(path, encoding, delimiter)
            if genes:
                return genes
        except:
            pass
        
        # Fall back to text file
        return self._parse_text_file(path, encoding)
    
    def _detect_encoding(self, path: Path) -> str:
        """Detect file encoding."""
        # First check if file has BOM
        with open(path, 'rb') as f:
            bom = f.read(3)
            if bom == b'\xef\xbb\xbf':  # UTF-8 BOM
                return 'utf-8-sig'
        
        # Try different encodings
        for encoding in self.ENCODINGS:
            try:
                with open(path, 'r', encoding=encoding) as f:
                    f.read(1024)  # Read first 1KB
                return encoding
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        # Default to utf-8
        return 'utf-8'
    
    def _detect_delimiter(self, path: Path, encoding: str) -> str:
        """Detect CSV delimiter."""
        with open(path, 'r', encoding=encoding) as f:
            sample = f.read(4096)  # Read first 4KB
        
        # Count occurrences of each delimiter
        counts = {}
        for delim in self.DELIMITERS:
            counts[delim] = sample.count(delim)
        
        # Return delimiter with highest count
        if max(counts.values()) > 0:
            return max(counts.items(), key=lambda x: x[1])[0]
        
        # Default to comma
        return ','
    
    def _find_gene_column(self, header_row: List[Any]) -> Optional[int]:
        """Find column index containing gene names."""
        if not header_row:
            return None
        
        # Look for gene-related column names with priority
        # Higher priority keywords should be checked first
        priority_keywords = [
            ['hugo', 'gene_symbol', 'gene symbol'],  # Most specific
            ['symbol'],  # Gene symbol
            ['gene_name', 'gene name'],  # Gene name
            ['gene'],  # Generic gene
            ['name']  # Most generic
        ]
        
        for keyword_group in priority_keywords:
            for i, cell in enumerate(header_row):
                if cell and isinstance(cell, str):
                    cell_lower = cell.lower().strip()
                    if any(keyword in cell_lower for keyword in keyword_group):
                        return i
        
        return None
    
    def get_format_info(self) -> Dict[str, Any]:
        """Get information about the last parsed file."""
        return {
            'format': self.last_format,
            'encoding': self.last_encoding,
            'delimiter': self.last_delimiter
        }