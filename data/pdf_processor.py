import fitz  # PyMuPDF
import tiktoken
from typing import List, Dict
import os
import re

class PDFProcessor:
    def __init__(self, chunk_size: int = 1000, overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF file"""
        doc = fitz.open(pdf_path)
        text = ""
        
        for page in doc:
            text += page.get_text()
        
        doc.close()
        return text
    
    def clean_text(self, text: str) -> str:
        """Clean extracted text"""
        # Remove excessive whitespace
        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r'\s+', ' ', text)
        
        # Remove page numbers and headers/footers (basic heuristics)
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Skip very short lines that might be page numbers
            if len(line.strip()) < 10:
                continue
            # Skip lines that are mostly numbers (likely page numbers)
            if re.match(r'^\s*\d+\s*$', line):
                continue
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.encoding.encode(text))
    
    def chunk_text(self, text: str) -> List[Dict[str, str]]:
        """Chunk text into smaller pieces with metadata"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)
            
            # If adding this sentence would exceed chunk size, save current chunk
            if current_tokens + sentence_tokens > self.chunk_size and current_chunk:
                chunks.append({
                    "text": current_chunk.strip(),
                    "tokens": current_tokens,
                    "chunk_id": len(chunks)
                })
                
                # Start new chunk with overlap
                if self.overlap > 0:
                    overlap_text = current_chunk[-self.overlap:] if len(current_chunk) > self.overlap else current_chunk
                    current_chunk = overlap_text + " " + sentence
                    current_tokens = self.count_tokens(current_chunk)
                else:
                    current_chunk = sentence
                    current_tokens = sentence_tokens
            else:
                current_chunk += " " + sentence if current_chunk else sentence
                current_tokens += sentence_tokens
        
        # Add final chunk
        if current_chunk:
            chunks.append({
                "text": current_chunk.strip(),
                "tokens": current_tokens,
                "chunk_id": len(chunks)
            })
        
        return chunks
    
    def process_pdf(self, pdf_path: str) -> List[str]:
        """Process PDF and return list of text chunks"""
        print(f"Processing PDF: {pdf_path}")
        
        # Extract text
        raw_text = self.extract_text_from_pdf(pdf_path)
        print(f"Extracted {len(raw_text)} characters")
        
        # Clean text
        clean_text = self.clean_text(raw_text)
        print(f"Cleaned text: {len(clean_text)} characters")
        
        # Chunk text
        chunks = self.chunk_text(clean_text)
        print(f"Created {len(chunks)} chunks")
        
        # Return just the text content
        return [chunk["text"] for chunk in chunks]

def create_knowledge_base_from_pdf(pdf_path: str) -> List[str]:
    """Create knowledge base from PDF file"""
    if not os.path.exists(pdf_path):
        print(f"PDF file not found: {pdf_path}")
        return []
    
    processor = PDFProcessor()
    chunks = processor.process_pdf(pdf_path)
    
    # Filter out very short chunks
    filtered_chunks = [chunk for chunk in chunks if len(chunk.strip()) > 100]
    
    print(f"Final knowledge base: {len(filtered_chunks)} chunks")
    return filtered_chunks