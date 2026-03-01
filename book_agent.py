import os
import json
import datetime
from main import get_config_value

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup
except ImportError:
    ebooklib = None

try:
    import chromadb
    from chromadb.utils import embedding_functions
except ImportError:
    chromadb = None

class BookAgent:
    """
    Agent responsible for scanning, managing, and indexing books (PDFs, EPUBs, Images).
    """
    def __init__(self, books_dir=None, db_path="vector_db"):
        self.books_dir = books_dir or get_config_value("BOOKS_DIR", None)
        self.supported_extensions = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".epub"}
        self.db_path = db_path
        
        if chromadb:
            self.chroma_client = chromadb.PersistentClient(path=self.db_path)
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
            self.collection = self.chroma_client.get_or_create_collection(
                name="book_library",
                embedding_function=self.embedding_fn
            )
        else:
            self.collection = None

    def scan_books(self):
        """
        Recursively scans the books directory and returns a list of book file paths.
        """
        if not self.books_dir or not os.path.exists(self.books_dir):
            return []

        books = []
        for root, _, files in os.walk(self.books_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in self.supported_extensions:
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, self.books_dir)
                    books.append({
                        "name": file,
                        "relative_path": relative_path,
                        "full_path": full_path,
                        "extension": ext
                    })
        return books

    def index_book(self, book_path):
        """
        Reads a book page by page and indexes it into ChromaDB for deep search.
        """
        if not self.collection:
            return "ChromaDB not available."
        
        if not os.path.exists(book_path):
            return f"File not found: {book_path}"

        ext = os.path.splitext(book_path)[1].lower()
        book_name = os.path.basename(book_path)
        
        print(f"📖 Indexing book: {book_name}...")
        
        pages_indexed = 0
        try:
            if ext == ".pdf" and PyPDF2:
                with open(book_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for i, page in enumerate(reader.pages):
                        text = page.extract_text()
                        if text and len(text.strip()) > 50:
                            doc_id = f"{book_name}_p{i}"
                            self.collection.upsert(
                                documents=[text],
                                metadatas=[{"path": book_path, "page": i, "book": book_name}],
                                ids=[doc_id]
                            )
                            pages_indexed += 1
            elif ext == ".epub" and ebooklib:
                book = epub.read_epub(book_path)
                for i, item in enumerate(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
                    soup = BeautifulSoup(item.get_body_content(), 'html.parser')
                    text = soup.get_text()
                    if text and len(text.strip()) > 50:
                        doc_id = f"{book_name}_i{i}"
                        self.collection.upsert(
                            documents=[text],
                            metadatas=[{"path": book_path, "index": i, "book": book_name}],
                            ids=[doc_id]
                        )
                        pages_indexed += 1
            else:
                return f"Unsupported or missing library for extension {ext}."
        except Exception as e:
            return f"Error indexing book: {e}"

        return f"Successfully indexed {pages_indexed} sections from '{book_name}'."

    def search_books(self, query, n_results=5):
        """
        Searches through indexed books for relevant passages.
        """
        if not self.collection or self.collection.count() == 0:
            return "No books indexed for deep search yet."

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )

        search_report = f"\n📚 DEEP SEARCH RESULTS FOR: '{query}'\n"
        documents = results.get('documents', [[]])[0]
        metadatas = results.get('metadatas', [[]])[0]
        
        for doc, meta in zip(documents, metadatas):
            book = meta.get('book', 'Unknown Book')
            location = f"Page {meta.get('page')}" if 'page' in meta else f"Section {meta.get('index')}"
            snippet = doc[:400].replace("\n", " ")
            search_report += f"- From '{book}' ({location}): ...{snippet}...\n"
            
        return search_report

    def get_summary(self):
        """
        Returns a human-readable summary of the books found and indexing status.
        """
        books = self.scan_books()
        if not books:
            return "No books found or BOOKS_DIR not configured."
        
        summary = f"Found {len(books)} books in your library:\n"
        # Group by extension
        stats = {}
        for b in books:
            ext = b['extension']
            stats[ext] = stats.get(ext, 0) + 1
        
        for ext, count in stats.items():
            summary += f"- {ext.upper()}: {count} files\n"
        
        if self.collection:
            indexed_count = self.collection.count()
            summary += f"\nDeep Search Index: {indexed_count} passages stored.\n"
        
        # List first 10 books
        summary += "\nRecent Books:\n"
        for b in books[:10]:
            summary += f"- {b['name']} (Path: {b['full_path']})\n"
        
        return summary

    def read_book_content(self, book_path, max_chars=5000):
        """
        Extracts text content from a book file (PDF or EPUB).
        """
        if not os.path.exists(book_path):
            return "File not found."

        ext = os.path.splitext(book_path)[1].lower()
        content = ""

        try:
            if ext == ".pdf" and PyPDF2:
                with open(book_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    # Extract first few pages
                    for page in reader.pages[:10]:
                        content += page.extract_text() + "\n"
                        if len(content) > max_chars:
                            break
            elif ext == ".epub" and ebooklib:
                book = epub.read_epub(book_path)
                for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                    soup = BeautifulSoup(item.get_body_content(), 'html.parser')
                    content += soup.get_text() + "\n"
                    if len(content) > max_chars:
                        break
            elif ext in {".jpg", ".jpeg", ".png", ".webp"}:
                return f"[Image File: {book_path}] Use visual AI to analyze this."
            else:
                return f"Unsupported or missing library for extension {ext}."
        except Exception as e:
            return f"Error reading book: {e}"

        return content[:max_chars] + ("..." if len(content) > max_chars else "")

    def query_books(self, query):
        """
        Searches for books matching the query string.
        """
        books = self.scan_books()
        matches = [b for b in books if query.lower() in b['name'].lower()]
        return matches

if __name__ == "__main__":
    agent = BookAgent()
    print(agent.get_summary())
