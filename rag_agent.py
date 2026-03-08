import os
import chromadb
from chromadb.utils import embedding_functions
import datetime
import contextlib
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, DirectoryLoader
from config_utils import get_config_value

class RAGAgent:
    def __init__(self, workspace_dir=None, logseq_dir=None, db_path="vector_db/markdown_notes"):
        self.workspace_dir = workspace_dir or get_config_value("WORKSPACE_DIR", ".")
        self.logseq_dir = logseq_dir or get_config_value("LOGSEQ_DIR", None)
        self.db_path = db_path
        
        # Initialize embedding function
        self.embedding_model = get_config_value("EMBEDDING_MODEL", "nomic-embed-text")
        try:
            self.embeddings = OllamaEmbeddings(model=self.embedding_model)
        except Exception as e:
            print(f"⚠️ Failed to initialize OllamaEmbeddings: {e}. Falling back to SentenceTransformer.")
            # Fallback to SentenceTransformer if Ollama is not available
            self.embeddings = None # Will be handled in get_vector_store

        # Text splitter for better chunking
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            add_start_index=True
        )

    def get_vector_store(self):
        """Initializes or loads the Chroma vector store."""
        if self.embeddings:
            return Chroma(
                persist_directory=self.db_path,
                embedding_function=self.embeddings
            )
        else:
            # Fallback using chromadb's native SentenceTransformer
            client = chromadb.PersistentClient(path=self.db_path)
            embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
            return Chroma(
                client=client,
                embedding_function=embedding_fn
            )

    def index_vault(self):
        """
        Scans Obsidian and LogSeq directories, chunks content, and indexes all markdown files.
        """
        print(f"🔍 RAG Agent: Indexing vault context into {self.db_path}...")
        
        all_docs = []
        targets = []
        if self.workspace_dir and os.path.exists(self.workspace_dir):
            targets.append(("Obsidian", self.workspace_dir))
        if self.logseq_dir and os.path.exists(self.logseq_dir):
            targets.append(("Logseq", self.logseq_dir))
            
        for source, root_dir in targets:
            loader = DirectoryLoader(root_dir, glob="**/*.md", loader_cls=TextLoader, loader_kwargs={'encoding': 'utf-8'})
            try:
                docs = loader.load()
                for doc in docs:
                    doc.metadata["source"] = source
                all_docs.extend(docs)
            except Exception as e:
                print(f"⚠️ Error loading from {root_dir}: {e}")
        
        if not all_docs:
            print("ℹ️ No markdown files found to index.")
            return

        chunks = self.text_splitter.split_documents(all_docs)
        print(f"📄 Created {len(chunks)} chunks from {len(all_docs)} documents.")
        
        vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings if self.embeddings else embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2"),
            persist_directory=self.db_path
        )
        # Chroma in LangChain 0.1+ persists automatically, but some versions might need it
        if hasattr(vector_store, 'persist'):
            vector_store.persist()
            
        print(f"✅ RAG Agent: Indexing complete.")

    def query_context(self, task_query, n_results=3):
        """
        Retrieves relevant snippets for a given task.
        """
        vector_store = self.get_vector_store()
        
        # Check if empty (approximate check for Chroma)
        try:
            if not vector_store or vector_store._collection.count() == 0:
                return ""
        except:
            return ""
            
        results = vector_store.similarity_search(task_query, k=n_results)
        
        if not results:
            return ""

        context_str = "\nRELEVANT CONTEXT FROM YOUR NOTES:\n"
        for doc in results:
            source = doc.metadata.get("source", "Unknown")
            path = doc.metadata.get("source_file") or doc.metadata.get("path") or "Unknown"
            filename = os.path.basename(path)
            context_str += f"- From {source} ('{filename}'): {doc.page_content[:400].replace('\\n', ' ')}\n"
            
        return context_str

if __name__ == "__main__":
    # Test (with dummy path or current dir)
    agent = RAGAgent(workspace_dir=".")
    agent.index_vault()
    print(agent.query_context("testing RAG logic"))


if __name__ == "__main__":
    # Test (with dummy path)
    agent = RAGAgent(workspace_dir=".")
    agent.index_vault()
    print(agent.query_context("testing RAG logic"))
