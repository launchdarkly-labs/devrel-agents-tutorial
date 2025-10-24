from langchain.tools import BaseTool
import re

class RedactionTool(BaseTool):
    name: str = "pii_redaction"
    description: str = "Redact personally identifiable information from text"
    
    def _run(self, text: str) -> str:
        # Simple PII redaction patterns
        redacted = text
        
        # Redact email addresses
        redacted = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]', redacted)
        
        # Redact phone numbers (basic patterns)
        redacted = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE_REDACTED]', redacted)
        
        # Redact SSN patterns
        redacted = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN_REDACTED]', redacted)
        
        return f"Redacted text: {redacted}"