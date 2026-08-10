import uuid
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.utils import embedding_functions

from app.config import settings
from app.db import get_chroma

def get_embedding_function():
    """
    Returns the OpenAI embedding function if an API key is available,
    otherwise returns the default ChromaDB sentence-transformer embedding function.
    """
    if settings.OPENAI_API_KEY:
        try:
            return embedding_functions.OpenAIEmbeddingFunction(
                api_key=settings.OPENAI_API_KEY,
                model_name="text-embedding-3-small"
            )
        except Exception as e:
            print(f"Failed to initialize OpenAI embedding function: {e}. Falling back to default.")
    
    return embedding_functions.DefaultEmbeddingFunction()

def chunk_text(pages: List[Dict[str, Any]], chunk_size: int = 1000, overlap: int = 150) -> List[Dict[str, Any]]:
    """
    Splits text from pages into smaller overlapping chunks while preserving page associations.
    """
    chunks = []
    for page in pages:
        page_num = page["page_number"]
        text = page["text"] or ""
        
        if not text.strip():
            continue
            
        start = 0
        while start < len(text):
            end = start + chunk_size
            
            # Avoid cutting words in half if possible
            if end < len(text):
                last_space = text[start:end].rfind(' ')
                if last_space > (chunk_size // 2):
                    end = start + last_space + 1
            
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({
                    "text": chunk_text,
                    "page_number": page_num
                })
            
            start += (end - start) - overlap
            if (end - start) <= overlap:
                break
    return chunks

def index_paper_chunks(paper_id: str, pages: List[Dict[str, Any]]) -> bool:
    """
    Chunks and indexes the pages of a research paper in ChromaDB.
    """
    try:
        chroma_client = get_chroma()
        emb_fn = get_embedding_function()
        
        # We index all chunks in a single global collection for ease of search filter
        collection = chroma_client.get_or_create_collection(
            name="researchgpt_chunks",
            embedding_function=emb_fn
        )
        
        chunks = chunk_text(pages)
        if not chunks:
            return False
            
        documents = []
        metadatas = []
        ids = []
        
        for idx, chunk in enumerate(chunks):
            documents.append(chunk["text"])
            metadatas.append({
                "paper_id": paper_id,
                "page_number": chunk["page_number"]
            })
            ids.append(f"{paper_id}_chunk_{idx}")
            
        # Delete pre-existing chunks for this paper if any
        try:
            collection.delete(where={"paper_id": paper_id})
        except Exception:
            pass
            
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        return True
    except Exception as e:
        print(f"Error indexing paper chunks in ChromaDB: {e}")
        return False

def query_paper_chunks(paper_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Searches ChromaDB for chunks matching the query under a specific paper.
    """
    try:
        chroma_client = get_chroma()
        emb_fn = get_embedding_function()
        
        collection = chroma_client.get_or_create_collection(
            name="researchgpt_chunks",
            embedding_function=emb_fn
        )
        
        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            where={"paper_id": paper_id}
        )
        
        formatted_results = []
        if results and results["documents"] and len(results["documents"]) > 0:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            ids = results["ids"][0]
            distances = results["distances"][0] if "distances" in results and results["distances"] else [0.0] * len(docs)
            
            for idx in range(len(docs)):
                formatted_results.append({
                    "chunk_id": ids[idx],
                    "text": docs[idx],
                    "page_number": metas[idx]["page_number"],
                    "score": float(distances[idx])
                })
        return formatted_results
    except Exception as e:
        print(f"Error querying ChromaDB: {e}")
        return []

def delete_paper_chunks(paper_id: str) -> bool:
    """
    Deletes all indexed chunks for a specific paper.
    """
    try:
        chroma_client = get_chroma()
        collection = chroma_client.get_or_create_collection(name="researchgpt_chunks")
        collection.delete(where={"paper_id": paper_id})
        return True
    except Exception as e:
        print(f"Error deleting chunks from ChromaDB: {e}")
        return False
