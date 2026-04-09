"""
Enterprise Knowledge Base
Support Documentation for Technical Support
"""

import os
import glob
import re
import tiktoken
from typing import List
from .pdf_processor import create_knowledge_base_from_pdf

# Knowledge base directory
KB_DIR = os.path.join(os.path.dirname(__file__), "..", "kb")

# Initialize the knowledge base
ENTERPRISE_KB = None


def chunk_markdown(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
    """Chunk markdown text into smaller pieces using section headers as boundaries"""
    encoding = tiktoken.get_encoding("cl100k_base")

    # Split on markdown headers (##, ###) to create semantic sections
    sections = re.split(r'\n(?=##+ )', text)
    chunks = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        section_tokens = len(encoding.encode(section))

        # If section is small enough, keep it as one chunk
        if section_tokens <= chunk_size:
            if len(section) > 50:  # Min length filter
                chunks.append(section)
        else:
            # Split large sections on paragraph boundaries
            paragraphs = re.split(r'\n\n+', section)
            current_chunk = ""
            current_tokens = 0

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                para_tokens = len(encoding.encode(para))

                if current_tokens + para_tokens > chunk_size and current_chunk:
                    if len(current_chunk) > 50:
                        chunks.append(current_chunk.strip())
                    current_chunk = para
                    current_tokens = para_tokens
                else:
                    current_chunk += "\n\n" + para if current_chunk else para
                    current_tokens += para_tokens

            if current_chunk and len(current_chunk) > 50:
                chunks.append(current_chunk.strip())

    return chunks


def load_markdown_file(filepath: str) -> List[str]:
    """Load and chunk a markdown file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Clean the markdown - remove excessive whitespace
        content = re.sub(r'\n{3,}', '\n\n', content)

        chunks = chunk_markdown(content)
        return chunks
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
        return []


def get_knowledge_base():
    """Get the enterprise knowledge base, loading it if necessary"""
    global ENTERPRISE_KB

    if ENTERPRISE_KB is None:
        # Find all supported files in the kb directory
        pdf_pattern = os.path.join(KB_DIR, "*.pdf")
        md_pattern = os.path.join(KB_DIR, "*.md")

        pdf_files = glob.glob(pdf_pattern)
        md_files = glob.glob(md_pattern)

        total_files = len(pdf_files) + len(md_files)

        if total_files == 0:
            raise ValueError(f"No PDF or Markdown files found in knowledge base directory: {KB_DIR}")

        print(f"Loading enterprise knowledge base from {total_files} file(s)...")

        # Combine documents from all files
        all_documents = []

        # Process PDFs
        for pdf_path in sorted(pdf_files):
            print(f"  Processing PDF: {os.path.basename(pdf_path)}")
            pdf_docs = create_knowledge_base_from_pdf(pdf_path)
            if pdf_docs:
                all_documents.extend(pdf_docs)
            else:
                print(f"  Warning: No content extracted from {os.path.basename(pdf_path)}")

        # Process Markdown files
        for md_path in sorted(md_files):
            print(f"  Processing Markdown: {os.path.basename(md_path)}")
            md_docs = load_markdown_file(md_path)
            if md_docs:
                all_documents.extend(md_docs)
            else:
                print(f"  Warning: No content extracted from {os.path.basename(md_path)}")

        if not all_documents:
            raise ValueError(f"No content could be extracted from files in: {KB_DIR}")

        ENTERPRISE_KB = all_documents
        print(f"Knowledge base loaded: {len(all_documents)} total chunks from {total_files} file(s)")

    return ENTERPRISE_KB