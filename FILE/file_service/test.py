
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_milvus import Milvus

class DummyEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[0.1] * 8 for _ in texts]

    def embed_query(self, text):
        return [0.1] * 8

store = Milvus(
    embedding_function=DummyEmbeddings(),
    collection_name="rag_documents",
    connection_args={"uri": "http://localhost:19530", "token": "root:Milvus"},
)

store.add_documents([
    Document(page_content="hello", metadata={"user_id": "u1"})
])
print("ok")