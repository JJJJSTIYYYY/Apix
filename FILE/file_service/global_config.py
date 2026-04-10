DEBUG = True
TRACE = True

AI_SERVICE_URL = "http://localhost:5091"

MEMO_REDIS_URL = "redis://localhost:6379"

WORKER_COUNT = 4 # Number of worker tasks in DataServerManager, to process query.

MYSQL_DOCKER_BASE_URL = "localhost"
MYSQL_DOCKER_PORT = 3307
MYSQL_USER = "apix"
MYSQL_PASSWORD = "apixapix"
MYSQL_DATABASE = "apix_database"
MYSQL_CHARSET = "utf8mb4"
AUTO_COMMIT = True

MILVUS_DOCKER_BASE_URI = "http://localhost:19530"
MILVUS_TOKEN = "root:Milvus"
COLLECTION_NAME = "rag_documents"

FILE_STORE_BASE_DIR = "./data/files"

BASE_URL = {       # Base URL for the LLM service
    # Ollama
    'ollama:local': 'http://localhost:11434',  # Local
    'ollama': 'http://localhost:11434',
}  