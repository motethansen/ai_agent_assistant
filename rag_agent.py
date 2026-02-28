import os
import chromadb
from chromadb.utils import embedding_functions
import datetime

class RAGAgent:
    def __init__(self, workspace_dir, logseq_dir=None, db_path="vector_db"):
        self.workspace_dir = workspace_dir
        self.logseq_dir = logseq_dir
        self.db_path = db_path
        
        # Initialize Chromadb (Local)
        self.client = chromadb.PersistentClient(path=self.db_path)
        
        # Use a lightweight embedding function
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        
        # Collection for notes
        self.collection = self.client.get_or_create_collection(
            name="markdown_notes",
            embedding_function=self.embedding_fn
        )

    def index_vault(self):
        """
        Scans Obsidian and LogSeq directories and indexes all markdown files.
        """
        print("🔍 RAG Agent: Indexing vault context...")
        
        targets = []
        if self.workspace_dir and os.path.exists(self.workspace_dir):
            targets.append(self.workspace_dir)
        if self.logseq_dir and os.path.exists(self.logseq_dir):
            targets.append(self.logseq_dir)
            
        for root_dir in targets:
            for root, _, files in os.walk(root_dir):
                for file in files:
                    if file.endswith(".md"):
                        path = os.path.join(root, file)
                        try:
                            with open(path, 'r', encoding='utf-8') as f:
                                content = f.read().strip()
                                if not content: continue
                                
                                # Use file path as unique ID
                                doc_id = os.path.relpath(path, start=root_dir)
                                
                                # Metadata for filtering if needed
                                metadata = {
                                    "path": path,
                                    "last_modified": os.path.getmtime(path),
                                    "source": "Obsidian" if root_dir == self.workspace_dir else "Logseq"
                                }
                                
                                # Upsert into chromadb
                                self.collection.upsert(
                                    documents=[content[:5000]], # Limit size per doc
                                    metadatas=[metadata],
                                    ids=[doc_id]
                                )
                        except Exception as e:
                            print(f"Error indexing {path}: {e}")
        
        print(f"✅ RAG Agent: Indexed {self.collection.count()} notes.")

    def query_context(self, task_query, n_results=3):
        """
        Retrieves relevant snippets for a given task.
        """
        if self.collection.count() == 0:
            return ""
            
        results = self.collection.query(
            query_texts=[task_query],
            n_results=n_results
        )
        
        context_str = "
RELEVANT CONTEXT FROM YOUR NOTES:
"
        documents = results.get('documents', [[]])[0]
        metadatas = results.get('metadatas', [[]])[0]
        
        for doc, meta in zip(documents, metadatas):
            filename = os.path.basename(meta['path'])
            # Take a small snippet for the prompt
            snippet = doc[:300].replace("
", " ")
            context_str += f"- From '{filename}': "...{snippet}..."
"
            
        return context_str

if __name__ == "__main__":
    # Test (with dummy path)
    agent = RAGAgent(workspace_dir=".")
    agent.index_vault()
    print(agent.query_context("testing RAG logic"))
