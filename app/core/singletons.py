from functools import lru_cache

from app.llm.ollama_client import OllamaClient
from app.rag.embedder import Embedder
from app.rag.retriever import Retriever
from app.services.chat_service import ChatService
from app.services.session_service import SessionService


@lru_cache
def get_embedder() -> Embedder:
    return Embedder()


@lru_cache
def get_ollama_client() -> OllamaClient:
    return OllamaClient()


@lru_cache
def get_session_service() -> SessionService:
    return SessionService()


@lru_cache
def get_retriever() -> Retriever:
    return Retriever()


@lru_cache
def get_chat_service() -> ChatService:
    return ChatService()