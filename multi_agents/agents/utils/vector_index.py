import os
import json
import time
from dotenv import load_dotenv
from typing import List, Dict, Tuple
from langchain_huggingface.embeddings.huggingface_endpoint import HuggingFaceEndpointEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# Load environment variables
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
GLOBAL_VECTOR_DIR = "./outputs/global_vector_store"

# Initialize embeddings using the stable models endpoint
embeddings = HuggingFaceEndpointEmbeddings(
    model=MODEL_NAME,
    task="feature-extraction",
    huggingfacehub_api_token=HF_TOKEN
)

def create_vector_index(content: str, output_dir: str):
    # Split content into chunks
    chunks = content.split('\n\n')
    # Create Document objects for LangChain
    documents = [Document(page_content=chunk) for chunk in chunks]
    # Create FAISS vector store
    vector_store = FAISS.from_documents(documents, embeddings)
    # Save the vector store
    vector_store.save_local(os.path.join(output_dir, "faiss_index"))
    # Save chunks for reference
    with open(os.path.join(output_dir, "chunks.json"), 'w') as f:
        json.dump(chunks, f)

def load_vector_index(output_dir: str):
    # Load FAISS vector store
    vector_store = FAISS.load_local(
        os.path.join(output_dir, "faiss_index"),
        embeddings,
        allow_dangerous_deserialization=True
    )
    # Load chunks
    with open(os.path.join(output_dir, "chunks.json"), 'r') as f:
        chunks = json.load(f)
    return vector_store, chunks

def retrieve_chunks(query: str, vector_store, chunks, k=3):
    # Perform similarity search
    results = vector_store.similarity_search(query, k=k)
    # Map results back to original chunks
    retrieved_chunks = [chunks[doc.metadata.get('index', i)] for i, doc in enumerate(results)]
    return retrieved_chunks

def init_global_vector_store():
    if not os.path.exists(GLOBAL_VECTOR_DIR):
        os.makedirs(GLOBAL_VECTOR_DIR)
    index_path = os.path.join(GLOBAL_VECTOR_DIR, "faiss_index")
    chunks_path = os.path.join(GLOBAL_VECTOR_DIR, "chunks.json")
    if not os.path.exists(index_path):
        # Create empty vector store
        empty_doc = [Document(page_content="")]
        vector_store = FAISS.from_documents(empty_doc, embeddings)
        vector_store.save_local(index_path)
        with open(chunks_path, 'w') as f:
            json.dump([], f)

def add_to_global_vector_store(task_id, chunks):
    init_global_vector_store()
    index_path = os.path.join(GLOBAL_VECTOR_DIR, "faiss_index")
    chunks_path = os.path.join(GLOBAL_VECTOR_DIR, "chunks.json")
    
    # Load existing vector store and chunks
    vector_store = FAISS.load_local(
        index_path,
        embeddings,
        allow_dangerous_deserialization=True
    )
    with open(chunks_path, 'r') as f:
        existing_chunks = json.load(f)
    
    # Create new documents with metadata
    new_documents = [
        Document(
            page_content=chunk,
            metadata={"task_id": task_id}
        ) for chunk in chunks
    ]
    
    # Add new documents to vector store
    vector_store.add_documents(new_documents)
    
    # Update chunks with task_id
    new_chunks = [{"text": chunk, "task_id": task_id} for chunk in chunks]
    existing_chunks.extend(new_chunks)
    
    # Save updated vector store and chunks
    vector_store.save_local(index_path)
    with open(chunks_path, 'w') as f:
        json.dump(existing_chunks, f)

def query_global_vector_store(query: str, k=3, threshold=1.0):
    index_path = os.path.join(GLOBAL_VECTOR_DIR, "faiss_index")
    chunks_path = os.path.join(GLOBAL_VECTOR_DIR, "chunks.json")
    
    if not os.path.exists(index_path) or not os.path.exists(chunks_path):
        return []
    
    # Load vector store and chunks
    vector_store = FAISS.load_local(
        index_path,
        embeddings,
        allow_dangerous_deserialization=True
    )
    with open(chunks_path, 'r') as f:
        chunks = json.load(f)
    

    results = vector_store.similarity_search_with_score(query, k=k)

    retrieved = []
    for doc, score in results:
        if score < threshold:
            # Find matching chunk with task_id
            for chunk in chunks:
                if chunk["text"] == doc.page_content:
                    retrieved.append(chunk)
                    break
    
    return retrieved
