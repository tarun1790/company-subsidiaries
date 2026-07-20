import uuid
import torch
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer, CrossEncoder
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from app.core.logging import logger

class VectorRetrievalService:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing VectorRetrievalService on device: {self.device}")
        
        # Load local embedding and cross-encoder reranking models
        try:
            # BAAI/bge-m3 outputs 1024-dimension embeddings
            self.embed_model = SentenceTransformer("BAAI/bge-m3", device=self.device)
            logger.info("Local BAAI/bge-m3 embedding model loaded successfully.")
        except Exception as e:
            logger.warning(f"Failed to load BAAI/bge-m3: {str(e)}. Falling back to all-MiniLM-L6-v2.")
            self.embed_model = SentenceTransformer("all-MiniLM-L6-v2", device=self.device)
            
        try:
            self.reranker = CrossEncoder("BAAI/bge-reranker-v2-m3", device=self.device)
            logger.info("Local BAAI/bge-reranker-v2-m3 cross-encoder model loaded successfully.")
        except Exception as e:
            logger.warning(f"Failed to load BAAI/bge-reranker-v2-m3: {str(e)}. Falling back to ms-marco-MiniLM-L-6-v2.")
            self.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device=self.device)

        # In-memory Qdrant client for local high-speed vector storage
        self.qdrant_client = QdrantClient(":memory:")
        self.collection_name = "corporate_docs"
        
        vector_size = self.embed_model.get_sentence_embedding_dimension()
        self.qdrant_client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        logger.info(f"Qdrant local collection '{self.collection_name}' initialized with dimension {vector_size}.")

    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Splits a document text block into overlapping chunks."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks

    async def index_document(self, doc_url: str, text: str):
        """Chunks a document, generates embeddings, and saves them to local Qdrant collection."""
        if not text or len(text.strip()) < 100:
            return

        chunks = self.chunk_text(text)
        logger.info(f"Indexing document: {doc_url} ({len(chunks)} chunks)...")
        
        # Generate embeddings in bulk
        embeddings = self.embed_model.encode(chunks, convert_to_numpy=True).tolist()
        
        points = []
        for idx, (chunk, vector) in enumerate(zip(chunks, embeddings)):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_url}_{idx}"))
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={"url": doc_url, "text": chunk, "chunk_index": idx}
                )
            )
            
        self.qdrant_client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        logger.info(f"Indexed {len(points)} chunks for document: {doc_url}")

    async def retrieve_relevant_chunks(self, query: str, top_k: int = 10, rerank_k: int = 3) -> List[Dict[str, Any]]:
        """Queries Qdrant for semantic similarity and reranks candidate chunks using CrossEncoder."""
        query_vector = self.embed_model.encode(query, convert_to_numpy=True).tolist()
        
        search_results = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k
        )
        
        if not search_results or not search_results.points:
            return []
            
        # Format candidates for reranking
        candidates = [res.payload for res in search_results.points]
        pairs = [[query, cand["text"]] for cand in candidates]
        
        # Compute reranking scores
        scores = self.reranker.predict(pairs)
        
        # Associate scores and sort candidates
        scored_candidates = []
        for score, cand in zip(scores, candidates):
            cand_copy = cand.copy()
            cand_copy["rerank_score"] = float(score)
            scored_candidates.append(cand_copy)
            
        scored_candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        return scored_candidates[:rerank_k]

# Singleton service instance
retrieval_service = VectorRetrievalService()
