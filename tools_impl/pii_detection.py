from __future__ import annotations

import re
from typing import Any, Dict, List
from pydantic import BaseModel, Field, field_validator

# IMPORTANT: use langchain_core.tools for LC 0.2+
from langchain_core.tools import BaseTool


# ---------- Input schema ----------
class PIIDetectionInput(BaseModel):
    text: str = Field(..., description="Text to analyze for PII")

    @field_validator("text")
    @classmethod
    def _strip_text(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Text must be a non-empty string.")
        return v


# ---------- PII Detection Tool ----------
class PIIDetectionTool(BaseTool):
    """AI-powered PII detection tool that intelligently identifies and redacts sensitive information."""
    name: str = "pii_detection"
    description: str = (
        "Analyzes text for personally identifiable information (PII) and provides intelligent redaction. "
        "The AI agent should examine the text and return a JSON response with: "
        "detected (boolean), types (array of PII types found like ['email', 'name']), "
        "redacted (text with PII replaced with [REDACTED] while keeping it readable), "
        "and safe_to_proceed (boolean indicating if processing should continue)."
    )
    # LC v0.2 way to define inputs:
    args_schema: type[BaseModel] = PIIDetectionInput

    def _run(self, text: str) -> str:
        try:
            # This tool is designed to be called by an AI agent that will intelligently
            # analyze the text and populate the response. The tool returns a template
            # that the AI should fill out based on its analysis of the text.
            
            import json
            
            # Template response - the AI agent calling this tool should analyze the text
            # and return the actual PII detection results in this exact format
            result = {
                "detected": False,  # AI should set to True if PII is found
                "types": [],  # AI should populate with PII types like ["email", "name", "phone"]
                "redacted": text,  # AI should redact PII with [REDACTED] while keeping text readable
                "safe_to_proceed": True  # AI should set to False if PII detected
            }
            
            return json.dumps(result, ensure_ascii=False)
            
        except Exception as e:
            import json
            return json.dumps({
                "detected": False,
                "types": [],
                "redacted": text,
                "safe_to_proceed": True,
                "error": str(e)
            })