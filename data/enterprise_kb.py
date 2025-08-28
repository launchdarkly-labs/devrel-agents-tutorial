"""
Enterprise Knowledge Base
Advanced AI/ML Documentation for Technical Support
"""

import os
import glob
from .pdf_processor import create_knowledge_base_from_pdf

# Knowledge base directory
KB_DIR = os.path.join(os.path.dirname(__file__), "..", "kb")

# Initialize the knowledge base
ENTERPRISE_KB = None

def get_knowledge_base():
    """Get the enterprise knowledge base, loading it if necessary"""
    global ENTERPRISE_KB
    
    if ENTERPRISE_KB is None:
        # Find all PDF files in the kb directory
        pdf_pattern = os.path.join(KB_DIR, "*.pdf")
        pdf_files = glob.glob(pdf_pattern)
        
        if not pdf_files:
            raise ValueError(f"No PDF files found in knowledge base directory: {KB_DIR}")
        
        print(f"Loading enterprise knowledge base from {len(pdf_files)} PDF(s)...")
        
        # Combine documents from all PDFs
        all_documents = []
        for pdf_path in sorted(pdf_files):  # Sort for consistent ordering
            print(f"  Processing: {os.path.basename(pdf_path)}")
            pdf_docs = create_knowledge_base_from_pdf(pdf_path)
            if pdf_docs:
                all_documents.extend(pdf_docs)
            else:
                print(f"  Warning: No content extracted from {os.path.basename(pdf_path)}")
        
        if not all_documents:
            raise ValueError(f"No content could be extracted from PDF files in: {KB_DIR}")
        
        ENTERPRISE_KB = all_documents
        print(f"Knowledge base loaded: {len(all_documents)} total chunks from {len(pdf_files)} PDF(s)")
    
    return ENTERPRISE_KB