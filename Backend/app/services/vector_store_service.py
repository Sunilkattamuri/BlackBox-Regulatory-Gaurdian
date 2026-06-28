"""
Pinecone Vector Store Service.
Manages embeddings generation and Pinecone semantic search for internal policies.
"""

import logging
from typing import List, Dict, Any, Optional
from ..config import settings

logger = logging.getLogger(__name__)

# Global instances cache
_pinecone_client = None
_embeddings_model = None


def get_embeddings_model():
    """Lazy initialize and cache the configured embedding model."""
    global _embeddings_model
    if _embeddings_model is not None:
        return _embeddings_model

    provider = settings.EMBEDDING_PROVIDER.lower()
    logger.info(f"Initializing embedding provider: {provider}")

    try:
        if provider == "local":
            # Using HuggingFace sentence-transformers locally
            from langchain_community.embeddings import HuggingFaceEmbeddings
            model_name = settings.LOCAL_EMBEDDING_MODEL
            _embeddings_model = HuggingFaceEmbeddings(model_name=model_name)
            logger.info(f"Local HuggingFace embeddings ({model_name}) initialized")
            
        elif provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is not configured in .env")
            from langchain_openai import OpenAIEmbeddings
            _embeddings_model = OpenAIEmbeddings(api_key=settings.OPENAI_API_KEY)
            logger.info("OpenAI embeddings initialized")
            
        elif provider == "google":
            if not settings.GOOGLE_API_KEY:
                raise ValueError("GOOGLE_API_KEY is not configured in .env")
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            _embeddings_model = GoogleGenerativeAIEmbeddings(
                model="models/embedding-001",
                google_api_key=settings.GOOGLE_API_KEY
            )
            logger.info("Google Gemini embeddings initialized")
            
        elif provider == "ollama":
            from langchain_ollama import OllamaEmbeddings
            model_name = getattr(settings, "OLLAMA_EMBEDDING_MODEL", "mxbai-embed-large")
            _embeddings_model = OllamaEmbeddings(
                model=model_name,
                base_url=settings.LLM_BASE_URL
            )
            logger.info(f"Ollama embeddings ({model_name}) initialized")
            
        else:
            raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {provider}")
            
    except Exception as e:
        logger.error(f"Error initializing embedding model: {e}")
        _embeddings_model = None

    return _embeddings_model


def get_pinecone_index() -> Optional[Any]:
    """Lazy initialize Pinecone and return the Index instance, creating it if needed."""
    global _pinecone_client
    if not settings.PINECONE_API_KEY:
        logger.warning("PINECONE_API_KEY not configured. Pinecone operations will be skipped.")
        return None

    try:
        from pinecone import Pinecone, ServerlessSpec
        
        # Initialize Pinecone Client
        if _pinecone_client is None:
            _pinecone_client = Pinecone(api_key=settings.PINECONE_API_KEY)

        index_name = settings.PINECONE_INDEX_NAME
        existing_indexes = [idx.name for idx in _pinecone_client.list_indexes()]

        if index_name not in existing_indexes:
            # Determine dimensions based on embedding provider
            provider = settings.EMBEDDING_PROVIDER.lower()
            if provider == "openai":
                dimension = 1536
            elif provider == "google":
                dimension = 768
            elif provider == "ollama":
                model_name = getattr(settings, "OLLAMA_EMBEDDING_MODEL", "mxbai-embed-large").lower()
                if "large" in model_name or "1024" in model_name:
                    dimension = 1024
                elif "nomic" in model_name:
                    dimension = 768
                else:
                    dimension = 1024
            else:  # local
                model_name = settings.LOCAL_EMBEDDING_MODEL.lower()
                if "large" in model_name or "1024" in model_name:
                    dimension = 1024
                else:
                    dimension = 384

            logger.info(f"Creating Pinecone Index '{index_name}' (dimension: {dimension})...")
            _pinecone_client.create_index(
                name=index_name,
                dimension=dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region=settings.PINECONE_ENVIRONMENT or "us-east-1"
                )
            )
            logger.info(f"Pinecone Index '{index_name}' created successfully")

        return _pinecone_client.Index(index_name)

    except Exception as e:
        logger.error(f"Failed to initialize Pinecone: {e}")
        return None


class VectorStoreService:
    """Service to handle embedding generation, upserting, and querying Pinecone."""

    @staticmethod
    def is_configured() -> bool:
        """Check if Pinecone has been configured with an API key."""
        return bool(settings.PINECONE_API_KEY)

    @staticmethod
    def embed_text(text: str) -> List[float]:
        """Generate vector embedding for a given text."""
        model = get_embeddings_model()
        if not model:
            raise ValueError("Embedding model could not be initialized")
        return model.embed_query(text)

    @classmethod
    def upsert_policies(cls, policies: List[Dict[str, Any]]) -> bool:
        """
        Upsert a list of policy documents to Pinecone.
        Each policy should be a dict with: 'id', 'name', 'summary', 'department', 'categories', 'version', 'regulatory_references'.
        """
        index = get_pinecone_index()
        if not index:
            logger.error("Pinecone index is not ready for upsert")
            return False

        try:
            vectors_to_upsert = []
            for policy in policies:
                policy_id = policy.get("id")
                # Combine name and summary for the text representation to embed
                text_to_embed = f"Policy Name: {policy.get('name')}\nSummary: {policy.get('summary')}\nCategories: {', '.join(policy.get('categories', []))}"
                
                logger.info(f"Generating embedding for policy: {policy_id}")
                embedding = cls.embed_text(text_to_embed)

                metadata = {
                    "id": policy_id,
                    "name": policy.get("name"),
                    "summary": policy.get("summary"),
                    "department": policy.get("department"),
                    "categories": ",".join(policy.get("categories", [])),
                    "version": policy.get("version"),
                    "last_updated": policy.get("last_updated", ""),
                    "regulatory_references": ",".join(policy.get("regulatory_references", []))
                }

                vectors_to_upsert.append((policy_id, embedding, metadata))

            logger.info(f"Upserting {len(vectors_to_upsert)} policies into Pinecone...")
            index.upsert(vectors=vectors_to_upsert)
            logger.info("Pinecone upsert complete")
            return True

        except Exception as e:
            logger.error(f"Error during Pinecone upsert: {e}")
            return False

    @classmethod
    def search_policies(cls, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Semantically query Pinecone for relevant policy documents.
        Returns a list of matching policies formatted as dictionaries.
        """
        index = get_pinecone_index()
        if not index:
            logger.warning("Pinecone index not initialized; skipping semantic search")
            return []

        try:
            logger.info(f"Generating embedding for search query: '{query}'")
            query_vector = cls.embed_text(query)

            logger.info(f"Querying Pinecone semantic search for: '{query}'")
            results = index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True
            )

            matches = []
            for match in results.get("matches", []):
                metadata = match.get("metadata", {})
                score = match.get("score", 0.0)
                
                # Reconstruct policy dict from metadata
                policy_dict = {
                    "id": metadata.get("id"),
                    "name": metadata.get("name"),
                    "version": metadata.get("version"),
                    "department": metadata.get("department"),
                    "categories": metadata.get("categories", "").split(",") if metadata.get("categories") else [],
                    "summary": metadata.get("summary"),
                    "last_updated": metadata.get("last_updated"),
                    "regulatory_references": metadata.get("regulatory_references", "").split(",") if metadata.get("regulatory_references") else [],
                    "score": score
                }
                matches.append(policy_dict)

            return matches

        except Exception as e:
            logger.error(f"Error during Pinecone query: {e}")
            return []

    @classmethod
    def upsert_contract(cls, contract_id: int, filename: str, text: str) -> bool:
        """
        Chunk and upsert an uploaded contract into Pinecone.
        """
        index = get_pinecone_index()
        if not index:
            logger.error("Pinecone index is not ready for contract upsert")
            return False

        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            chunks = text_splitter.split_text(text)

            vectors_to_upsert = []
            for i, chunk in enumerate(chunks):
                chunk_id = f"contract_{contract_id}_chunk_{i}"
                embedding = cls.embed_text(chunk)
                metadata = {
                    "id": str(contract_id),
                    "type": "contract",
                    "filename": filename,
                    "chunk_index": i,
                    "text": chunk
                }
                vectors_to_upsert.append((chunk_id, embedding, metadata))

            logger.info(f"Upserting {len(vectors_to_upsert)} chunks for contract {contract_id} into Pinecone...")
            
            # Pinecone has a batch limit (usually 100)
            batch_size = 100
            for i in range(0, len(vectors_to_upsert), batch_size):
                index.upsert(vectors=vectors_to_upsert[i:i + batch_size])
                
            logger.info("Pinecone contract upsert complete")
            return True
        except Exception as e:
            logger.error(f"Error during Pinecone contract upsert: {e}")
            return False

    @classmethod
    def delete_contract(cls, contract_id: int) -> bool:
        """
        Delete all vector chunks associated with a contract ID.
        """
        index = get_pinecone_index()
        if not index:
            return False
            
        try:
            # Delete vectors where metadata matches contract ID and type
            index.delete(filter={"id": str(contract_id), "type": "contract"})
            logger.info(f"Deleted vectors for contract {contract_id} from Pinecone.")
            return True
        except Exception as e:
            logger.error(f"Error deleting contract {contract_id} from Pinecone: {e}")
            return False


# Singleton instance helper
vector_store_service = VectorStoreService()
