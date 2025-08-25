"""
Enterprise Knowledge Base
Advanced AI/ML Documentation for Technical Support
"""

import os
from .pdf_processor import create_knowledge_base_from_pdf

# Path to the PDF knowledge base
PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "kb", "SuttonBartoIPRLBook2ndEd.pdf")

# Initialize the knowledge base
ENTERPRISE_KB = None

def get_knowledge_base():
    """Get the enterprise knowledge base, loading it if necessary"""
    global ENTERPRISE_KB
    
    if ENTERPRISE_KB is None:
        print("Loading enterprise knowledge base from PDF...")
        ENTERPRISE_KB = create_knowledge_base_from_pdf(PDF_PATH)
        
        # No fallback - PDF processing must succeed
        if not ENTERPRISE_KB:
            raise ValueError(f"Failed to load knowledge base from PDF: {PDF_PATH}. Ensure the PDF file exists and is readable.")
    
    return ENTERPRISE_KB