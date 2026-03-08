import os
import json
import datetime
from config_utils import get_config_value
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, UnstructuredEPubLoader

class BookAgent:
    """
    Agent responsible for scanning, managing, and indexing books (PDFs, EPUBs).
    """
    def __init__(self, books_dir=None, db_path="vector_db/book_library"):
        self.books_dir = books_dir or get_config_value("BOOKS_DIR", "books")
        self.db_path = db_path
        self.supported_extensions = {".pdf", ".epub"}
        
        # Initialize embedding function
        self.embedding_model = get_config_value("EMBEDDING_MODEL", "nomic-embed-text")
        try:
            self.embeddings = OllamaEmbeddings(model=self.embedding_model)
        except Exception as e:
            print(f"⚠️ Failed to initialize OllamaEmbeddings: {e}")
            self.embeddings = None

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100
        )

    def get_vector_store(self):
        """Initializes or loads the Chroma vector store."""
        return Chroma(
            persist_directory=self.db_path,
            embedding_function=self.embeddings
        )

    def scan_books(self):
        """Recursively scans the books directory."""
        if not self.books_dir or not os.path.exists(self.books_dir):
            return []
        books = []
        for root, _, files in os.walk(self.books_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in self.supported_extensions:
                    books.append({
                        "name": file,
                        "full_path": os.path.join(root, file),
                        "extension": ext
                    })
        return books

    def index_book(self, book_path):
        """Reads a book and indexes it into ChromaDB."""
        if not os.path.exists(book_path):
            return f"File not found: {book_path}"

        ext = os.path.splitext(book_path)[1].lower()
        print(f"📖 Indexing book: {os.path.basename(book_path)}...")
        
        try:
            if ext == ".pdf":
                loader = PyPDFLoader(book_path)
            elif ext == ".epub":
                loader = UnstructuredEPubLoader(book_path)
            else:
                return f"Unsupported extension {ext}"

            docs = loader.load()
            chunks = self.text_splitter.split_documents(docs)
            
            vector_store = Chroma.from_documents(
                documents=chunks,
                embedding=self.embeddings,
                persist_directory=self.db_path
            )
            return f"Successfully indexed {len(chunks)} chunks from '{os.path.basename(book_path)}'."
        except Exception as e:
            return f"Error indexing book: {e}"

    def search_books(self, query, n_results=3):
        """Searches through indexed books for relevant passages."""
        vector_store = self.get_vector_store()
        try:
            if vector_store._collection.count() == 0:
                return "No books indexed yet."
        except:
            return "No books indexed yet."

        results = vector_store.similarity_search(query, k=n_results)
        report = f"\n📚 DEEP SEARCH RESULTS FOR: '{query}'\n"
        for doc in results:
            source = os.path.basename(doc.metadata.get("source", "Unknown"))
            report += f"- From '{source}': {doc.page_content[:400].replace('\\n', ' ')}...\n"
        return report

    def get_summary(self):
        books = self.scan_books()
        vector_store = self.get_vector_store()
        try:
            count = vector_store._collection.count()
        except:
            count = 0
        return f"Library: {len(books)} books found. Index: {count} passages stored."


if __name__ == "__main__":
    agent = BookAgent()
    print(agent.get_summary())
