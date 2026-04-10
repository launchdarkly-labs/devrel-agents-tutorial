#!/usr/bin/env python3
"""
Build a RAG-augmented dataset for offline LLM evaluation.

Reads `datasets/answer-tests.csv` (questions + expected outputs), runs the
real RAG pipeline against each question, and writes a new CSV where the
`input` field bundles the question together with the retrieved chunks.

The resulting dataset can be uploaded to LaunchDarkly's Datasets feature
and run through the Playground. The model receives the same context it
would in production, but without the Playground needing to execute tools.

Usage:
    uv run python tools/build_rag_dataset.py
    uv run python tools/build_rag_dataset.py --top-k 5
    uv run python tools/build_rag_dataset.py --in datasets/answer-tests.csv \\
                                              --out datasets/answer-tests-with-context.csv
"""

import argparse
import csv
import os
import sys
from pathlib import Path

# Add parent directory to path so `data.vector_store` resolves
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from data.vector_store import VectorStore


def build_input(question: str, chunks: list[tuple[str, float, dict]]) -> str:
    """Bundle a question and its retrieved chunks into a single-line prompt.

    Newlines inside the input field break LaunchDarkly's CSV parser
    (it treats \\n as a row terminator even inside quoted fields), so the
    bundled prompt is flattened to one line. The `---` separator and the
    `Question:` prefix preserve the visual structure for the model without
    requiring multi-line fields.
    """
    flat_chunks = []
    for doc, _score, _meta in chunks:
        flat = " ".join(doc.split())  # collapse whitespace + newlines into spaces
        flat_chunks.append(flat)
    body = " --- ".join(flat_chunks)
    return f"Documentation context: --- {body} --- Question: {question}"


def main():
    parser = argparse.ArgumentParser(
        description="Bundle RAG retrieval into an offline eval dataset."
    )
    parser.add_argument(
        "--in",
        dest="input_path",
        default="datasets/answer-tests.csv",
        help="Source CSV with question + expected_output rows",
    )
    parser.add_argument(
        "--out",
        dest="output_path",
        default="datasets/answer-tests-with-context.csv",
        help="Destination CSV with bundled input field",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of chunks to retrieve per question (default 10)",
    )
    args = parser.parse_args()

    in_path = Path(args.input_path)
    out_path = Path(args.output_path)

    if not in_path.exists():
        print(f"Input file not found: {in_path}")
        sys.exit(1)

    vs = VectorStore()
    if not vs.exists():
        print("Vector store not found. Run initialize_embeddings.py first.")
        sys.exit(1)

    with in_path.open() as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print(f"No rows in {in_path}")
        sys.exit(1)

    print(f"Building RAG context for {len(rows)} rows (top_k={args.top_k})...")

    out_rows = []
    for i, row in enumerate(rows, 1):
        # Idempotent: if the source has been previously bundled (has an
        # `original_question` column), use that as the search query so we
        # don't recursively bundle a bundled prompt. Otherwise treat
        # `input` (or legacy `question`) as the question itself.
        question = (
            row.get("original_question")
            or row.get("input")
            or row.get("question")
            or ""
        )
        expected = row.get("expected_output") or row.get("expected_answer") or ""
        if not question:
            print(f"  Row {i}: skipping (no input)")
            continue

        chunks = vs.search(question, top_k=args.top_k)
        bundled_input = build_input(question, chunks)

        out_rows.append({
            "input": bundled_input,
            "expected_output": expected,
            "original_question": question,
        })
        print(f"  Row {i}: {len(chunks)} chunks for {question[:60]!r}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["input", "expected_output", "original_question"]
        )
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"\nWrote {len(out_rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
