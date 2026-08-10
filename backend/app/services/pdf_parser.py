import io
import re
from typing import Dict, Any, List

# Try imports and define fallbacks if needed
try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

def clean_text(text: str) -> str:
    """Cleans excess spacing and control characters from text."""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_pdf_content(file_bytes: bytes) -> Dict[str, Any]:
    """
    Extracts text, metadata, abstract, and pages from a PDF byte stream.
    Tries pdfplumber first, falling back to pypdf if unavailable or failing.
    """
    pdf_file = io.BytesIO(file_bytes)
    
    metadata = {
        "title": "Unknown Title",
        "authors": [],
        "abstract": "",
        "raw_text": "",
        "pages": []
    }
    
    # Try pypdf for initial metadata parsing
    if pypdf:
        try:
            reader = pypdf.PdfReader(pdf_file)
            info = reader.metadata
            if info:
                if info.title and len(info.title.strip()) > 3:
                    metadata["title"] = info.title.strip()
                if info.author:
                    # Split authors by standard separators
                    metadata["authors"] = [a.strip() for a in re.split(r'[,;]|\band\b', info.author) if a.strip()]
        except Exception as e:
            print(f"Error reading PDF metadata: {e}")
            
    # Extract page text
    pdf_file.seek(0)
    pages_text = []
    
    use_pdfplumber = pdfplumber is not None
    if use_pdfplumber:
        try:
            with pdfplumber.open(pdf_file) as pdf:
                for idx, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    pages_text.append({
                        "page_number": idx + 1,
                        "text": text
                    })
        except Exception as e:
            print(f"pdfplumber extraction failed: {e}. Falling back to pypdf.")
            use_pdfplumber = False
            
    if not use_pdfplumber and pypdf:
        try:
            pdf_file.seek(0)
            reader = pypdf.PdfReader(pdf_file)
            pages_text = []
            for idx, page in enumerate(reader.pages):
                try:
                    text = page.extract_text() or ""
                    pages_text.append({
                        "page_number": idx + 1,
                        "text": text
                    })
                except Exception as page_err:
                    print(f"Failed extracting page {idx+1}: {page_err}")
        except Exception as e:
            print(f"pypdf extraction failed: {e}")
            
    # Build complete raw text string
    raw_text_parts = []
    for p in pages_text:
        raw_text_parts.append(f"--- Page {p['page_number']} ---\n{p['text']}")
    raw_text = "\n\n".join(raw_text_parts)
    
    metadata["raw_text"] = raw_text
    metadata["pages"] = pages_text
    
    # Heuristically extract title, author, abstract if missing
    first_page_text = pages_text[0]["text"] if pages_text else ""
    
    # 1. Parse Title
    if metadata["title"] in ["Unknown Title", "", None] and first_page_text:
        lines = [line.strip() for line in first_page_text.split("\n") if line.strip()]
        if lines:
            # Exclude lines that look like journals or arxiv info
            candidate = lines[0]
            if len(candidate) < 120 and not any(k in candidate.lower() for k in ["proceedings", "vol.", "arxiv", "journal", "http", "issn", "doi"]):
                metadata["title"] = candidate
            elif len(lines) > 1 and len(lines[1]) < 120 and not any(k in lines[1].lower() for k in ["arxiv", "journal", "http", "doi"]):
                metadata["title"] = lines[1]
            else:
                metadata["title"] = " ".join(lines[0:2])[:120]
                
    # Clean Title of odd artifacts
    metadata["title"] = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', metadata["title"])
    if not metadata["title"].strip():
        metadata["title"] = "Research Paper File"
        
    # 2. Parse Authors
    if not metadata["authors"] and first_page_text:
        lines = [line.strip() for line in first_page_text.split("\n") if line.strip()]
        # Skip title and try to find line with authors
        for line in lines[1:5]:
            # Heuristics: Skip lines with emails, affiliations, numbers, abstract markers
            if "@" in line or any(k in line.lower() for k in ["university", "department", "abstract", "institute", "laboratory"]):
                continue
            if re.search(r'\d{3,}', line): # skip lines with zip codes / long numbers
                continue
            potential_authors = re.split(r',| and |;', line)
            cleaned_auths = [a.strip() for a in potential_authors if len(a.strip()) > 3 and len(a.strip()) < 45]
            if cleaned_auths:
                metadata["authors"] = cleaned_auths
                break
                
    if not metadata["authors"]:
        metadata["authors"] = ["Authors Unspecified"]
        
    # 3. Parse Abstract
    if first_page_text:
        abstract_match = re.search(r'(?i)\babstract\b(.*)', first_page_text, re.DOTALL)
        if abstract_match:
            abstract_text = abstract_match.group(1).strip()
            # Split abstract text before next standard section name
            parts = re.split(r'(?i)\n\s*(?:1\.?\s+|introduction|background|methods|ii\.)', abstract_text, maxsplit=1)
            metadata["abstract"] = clean_text(parts[0])[:1200]
            
    if not metadata["abstract"] and first_page_text:
        # Fallback: take first paragraph with sufficient length that isn't title/author metadata
        paragraphs = [p.strip() for p in first_page_text.split("\n\n") if p.strip()]
        for p in paragraphs:
            if len(p) > 180 and not any(k in p.lower() for k in ["author", "university", "department", "@", "abstract"]):
                metadata["abstract"] = clean_text(p)[:800]
                break
                
    return metadata
