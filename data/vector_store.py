"""
Persistent Vector Database for Knowledge Base
Multi-provider support: OpenAI API or AWS Bedrock embeddings with FAISS for efficient similarity search

DEVELOPER PATTERN: Provider Abstraction Pattern
==========================================

This module demonstrates a clean provider abstraction pattern that allows developers to:

1. **Pluggable Provider Architecture**:
   - Common interface (_get_embeddings, _initialize_*_client)
   - Provider-specific implementations (OpenAI vs Bedrock)
   - Easy extension point for new embedding providers

2. **Environment-Based Auto-Detection**:
   - 4-level hierarchy: explicit env var → auth method → API keys → defaults
   - Graceful fallbacks with clear logging for debugging
   - Migration-friendly with backward compatibility

3. **Provider Validation & Migration Support**:
   - Store metadata includes provider info for compatibility checking
   - Intelligent migration guidance (dimension matching, rebuild requirements)
   - Cross-provider compatibility validation

4. **Key Extension Points for Developers**:
   - Add new provider: Implement _initialize_<provider>() and _get_<provider>_embeddings()
   - Custom detection logic: Override _detect_provider()
   - Migration logic: Extend check_migration_compatibility()

Provider auto-detection priority:
1. EMBEDDING_PROVIDER env var (explicit)
2. AUTH_METHOD=sso → bedrock (if no OpenAI key)
3. OPENAI_API_KEY present → openai
4. Default → openai (backward compatible)

Example Extension (hypothetical):
```python
def _initialize_huggingface(self):
    self.client = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    self.embedding_model = "all-MiniLM-L6-v2"
    self.dimension = 384

def _get_huggingface_embeddings(self, texts: List[str]) -> np.ndarray:
    return np.array(self.client.embed_documents(texts)).astype('float32')
```
"""

import os
import pickle
import numpy as np
from typing import List, Tuple, Optional
from openai import OpenAI
import faiss
from pathlib import Path
from utils.logger import log_debug, log_student
import boto3
from langchain_aws import BedrockEmbeddings

class VectorStore:
    def __init__(self, store_path: str = "data/vector_store", provider: str = None):
        self.store_path = Path(store_path)
        self.store_path.mkdir(exist_ok=True)

        # Auto-detect provider if not specified
        self.provider = provider or self._detect_provider()

        # Log provider selection with migration context
        explicit_provider = os.getenv('EMBEDDING_PROVIDER', '').lower()
        if explicit_provider:
            log_student(f"EMBEDDINGS: Using explicit provider: {self.provider}")
            log_debug(f"MIGRATION: Provider explicitly set via EMBEDDING_PROVIDER={explicit_provider}")
        else:
            log_student(f"EMBEDDINGS: Auto-detected provider: {self.provider}")
            auth_method = os.getenv('AUTH_METHOD', 'api-key').lower()
            has_openai = os.getenv('OPENAI_API_KEY')

            if auth_method == 'sso' and not has_openai:
                log_debug("MIGRATION: Auto-selected Bedrock (AUTH_METHOD=sso, no OpenAI key)")
            elif has_openai:
                log_debug("MIGRATION: Auto-selected OpenAI (API key available)")
            else:
                log_debug("MIGRATION: Defaulted to OpenAI (backward compatibility)")

        # Initialize provider-specific client and settings
        self._initialize_embedding_client()

        self.index = None
        self.documents = []
        self.metadata = []

        # Try to load existing store
        self._load_store()

    def _detect_provider(self) -> str:
        """
        Auto-detect embedding provider based on environment configuration.

        4-level priority hierarchy:
        1. Explicit provider selection via EMBEDDING_PROVIDER env var
        2. Auto-detect based on AUTH_METHOD
        3. Check for OpenAI API key availability
        4. Default to OpenAI for backward compatibility

        Returns:
            str: Provider name ('openai' or 'bedrock')
        """
        # 1. Explicit provider selection via EMBEDDING_PROVIDER env var
        env_provider = os.getenv('EMBEDDING_PROVIDER', '').lower()
        if env_provider in ['openai', 'bedrock']:
            log_debug(f"EMBEDDINGS: Using explicit provider: {env_provider}")
            return env_provider

        # 2. Auto-detect based on AUTH_METHOD
        auth_method = os.getenv('AUTH_METHOD', 'api-key').lower()
        has_openai = os.getenv('OPENAI_API_KEY')

        if auth_method == 'sso' and not has_openai:
            log_debug("EMBEDDINGS: Auto-detected provider: bedrock (AUTH_METHOD=sso)")
            return "bedrock"
        elif has_openai:
            log_debug("EMBEDDINGS: Auto-detected provider: openai (API key found)")
            return "openai"
        else:
            log_debug("EMBEDDINGS: Defaulting to provider: openai (backward compatible)")
            return "openai"

    def _initialize_embedding_client(self):
        """
        Initialize provider-specific embedding client and settings.

        DEVELOPER PATTERN: Provider Factory Pattern
        =========================================

        This method demonstrates the factory pattern for provider initialization:
        1. Dispatch to provider-specific initializers
        2. Set common attributes (client, embedding_model, dimension)
        3. Uniform error handling and logging

        Extension Point: Add new providers by:
        1. Adding provider check: elif self.provider == 'your_provider':
        2. Implementing _initialize_your_provider() method
        3. Setting self.client, self.embedding_model, self.dimension
        """
        if self.provider == 'openai':
            self._initialize_openai()
        elif self.provider == 'bedrock':
            self._initialize_bedrock()
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

        log_debug(f"EMBEDDINGS: Initialized {self.provider} client (model: {self.embedding_model}, dimension: {self.dimension})")

    def _initialize_openai(self):
        """Initialize OpenAI embedding client and settings."""
        if not os.getenv('OPENAI_API_KEY'):
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI provider")

        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.embedding_model = "text-embedding-3-small"
        self.dimension = 1536  # text-embedding-3-small dimension

    def _initialize_bedrock(self):
        """Initialize Bedrock embedding client and settings."""
        auth_method = os.getenv('AUTH_METHOD', 'api-key').lower()
        if auth_method != 'sso':
            raise ValueError("Bedrock embeddings require AUTH_METHOD=sso. Run: aws sso login")

        # Get AWS session (this will be set up by config_manager)
        aws_region = os.getenv('AWS_REGION', 'us-east-1')
        session = boto3.Session(region_name=aws_region)

        # Test AWS credentials
        try:
            sts = session.client('sts')
            identity = sts.get_caller_identity()
            log_debug(f"BEDROCK EMBEDDINGS: Connected to AWS account {identity['Account']}")
        except Exception as e:
            raise ValueError(f"AWS SSO session not available for Bedrock embeddings: {e}")

        # Configure Bedrock embeddings
        self.embedding_model = os.getenv('BEDROCK_EMBEDDING_MODEL', 'amazon.titan-embed-text-v2:0')
        self.dimension = int(os.getenv('BEDROCK_EMBEDDING_DIMENSIONS', '1024'))

        # Create Bedrock embeddings client with normalization for cosine similarity
        self.client = BedrockEmbeddings(
            client=session.client('bedrock-runtime', region_name=aws_region),
            model_id=self.embedding_model,
            region_name=aws_region,
            normalize=True  # Required for cosine similarity with FAISS
        )
    
    def _get_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Get embeddings for a list of texts using configured provider.

        DEVELOPER PATTERN: Provider Strategy Pattern
        ==========================================

        This method demonstrates the strategy pattern for provider-specific operations:
        1. Common interface regardless of provider
        2. Provider dispatch to specialized implementations
        3. Consistent return type (np.ndarray of float32)

        Extension Point: Add new providers by:
        1. Adding elif self.provider == 'your_provider': return self._get_your_provider_embeddings(texts)
        2. Implementing _get_your_provider_embeddings() method
        3. Ensuring return type is np.ndarray with dtype='float32'
        """
        if self.provider == 'openai':
            return self._get_openai_embeddings(texts)
        elif self.provider == 'bedrock':
            return self._get_bedrock_embeddings(texts)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _get_openai_embeddings(self, texts: List[str]) -> np.ndarray:
        """Get embeddings using OpenAI API."""
        response = self.client.embeddings.create(
            input=texts,
            model=self.embedding_model
        )
        embeddings = np.array([data.embedding for data in response.data])
        return embeddings.astype('float32')

    def _get_bedrock_embeddings(self, texts: List[str]) -> np.ndarray:
        """Get embeddings using Bedrock Titan."""
        # BedrockEmbeddings.embed_documents returns a list of lists
        embeddings_list = self.client.embed_documents(texts)
        embeddings = np.array(embeddings_list)
        return embeddings.astype('float32')
    
    def create_index(self, documents: List[str], metadata: Optional[List[dict]] = None):
        """Create and save vector index from documents"""
        print(f"Creating embeddings for {len(documents)} documents...")
        
        # Get embeddings in batches to avoid API limits
        batch_size = 100
        all_embeddings = []
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            batch_embeddings = self._get_embeddings(batch)
            all_embeddings.append(batch_embeddings)
            print(f"Processed batch {i//batch_size + 1}/{(len(documents)-1)//batch_size + 1}")
        
        embeddings = np.vstack(all_embeddings)
        
        # Create FAISS index
        self.index = faiss.IndexFlatIP(self.dimension)  # Inner product for cosine similarity
        
        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)
        self.index.add(embeddings)
        
        self.documents = documents
        self.metadata = metadata or [{} for _ in documents]
        
        # Save to disk
        self._save_store()
        print(f"Vector store created and saved with {len(documents)} documents")
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float, dict]]:
        """Search for similar documents"""
        if self.index is None:
            raise ValueError("No vector index loaded. Create index first.")
        
        # Get query embedding
        query_embedding = self._get_embeddings([query])
        faiss.normalize_L2(query_embedding)
        
        # Search
        scores, indices = self.index.search(query_embedding, top_k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx != -1:  # Valid result
                results.append((
                    self.documents[idx],
                    float(score),
                    self.metadata[idx]
                ))
        
        return results
    
    def _save_store(self):
        """Save vector store to disk"""
        # Save FAISS index
        faiss.write_index(self.index, str(self.store_path / "faiss.index"))
        
        # Save documents and metadata with provider information
        with open(self.store_path / "documents.pkl", "wb") as f:
            pickle.dump({
                "documents": self.documents,
                "metadata": self.metadata,
                "dimension": self.dimension,
                "model": self.embedding_model,
                "provider": self.provider  # Add provider for validation
            }, f)
        
        print(f"Vector store saved to {self.store_path}")
    
    def _load_store(self):
        """Load vector store from disk with provider validation."""
        index_path = self.store_path / "faiss.index"
        docs_path = self.store_path / "documents.pkl"

        if index_path.exists() and docs_path.exists():
            # Load documents and metadata first for validation
            with open(docs_path, "rb") as f:
                data = pickle.load(f)
                stored_provider = data.get("provider", "openai")  # Default to openai for old stores
                stored_dimension = data.get("dimension", 1536)
                stored_model = data.get("model", "text-embedding-3-small")

            # Validate provider compatibility
            if stored_provider != self.provider:
                log_student(
                    f"⚠️  PROVIDER MISMATCH: Vector store uses {stored_provider}, "
                    f"but current config uses {self.provider}. "
                    f"Run 'initialize_embeddings.py --force' to rebuild for {self.provider}."
                )

                # Enhanced migration guidance
                if stored_provider == "openai" and self.provider == "bedrock":
                    log_debug("MIGRATION: OpenAI → Bedrock transition detected")
                    log_debug("MIGRATION: Consider hybrid setup: keep OpenAI embeddings, use Bedrock chat")
                    log_debug("MIGRATION: Set EMBEDDING_PROVIDER=openai to preserve embeddings")
                elif stored_provider == "bedrock" and self.provider == "openai":
                    log_debug("MIGRATION: Bedrock → OpenAI transition detected")
                    log_debug("MIGRATION: Embeddings will change from Titan to OpenAI model")
                else:
                    log_debug(f"MIGRATION: {stored_provider} → {self.provider} transition requires rebuild")

                self.index = None
                self.documents = []
                self.metadata = []
                return

            # Validate dimension compatibility
            if stored_dimension != self.dimension:
                log_student(
                    f"⚠️  DIMENSION MISMATCH: Vector store has {stored_dimension} dims, "
                    f"but current config expects {self.dimension}. "
                    f"Run 'initialize_embeddings.py --force' to rebuild."
                )

                # Enhanced dimension migration guidance
                if stored_dimension == 1536 and self.dimension == 1024:
                    log_debug("MIGRATION: OpenAI (1536) → Bedrock (1024) dimension change")
                    log_debug("MIGRATION: Bedrock Titan V2 uses configurable dimensions")
                    log_debug("MIGRATION: Set BEDROCK_EMBEDDING_DIMENSIONS=1536 to match OpenAI")
                elif stored_dimension == 1024 and self.dimension == 1536:
                    log_debug("MIGRATION: Bedrock (1024) → OpenAI (1536) dimension change")
                    log_debug("MIGRATION: OpenAI text-embedding-3-small uses fixed 1536 dimensions")
                else:
                    log_debug(f"MIGRATION: Dimension change {stored_dimension} → {self.dimension}")

                self.index = None
                self.documents = []
                self.metadata = []
                return

            # If validation passes, load the store
            self.index = faiss.read_index(str(index_path))
            self.documents = data["documents"]
            self.metadata = data["metadata"]

            log_student(f"Vector store loaded with {len(self.documents)} documents ({stored_provider} provider)")
            log_debug(f"EMBEDDINGS: Loaded store - provider: {stored_provider}, model: {stored_model}, dimension: {stored_dimension}")
        else:
            log_debug("No existing vector store found")
    
    def exists(self) -> bool:
        """Check if vector store exists"""
        return self.index is not None and len(self.documents) > 0