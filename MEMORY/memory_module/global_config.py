DEBUG = True
TRACE = False

AI_SERVICE_URL = "http://localhost:5091"

MEMO_REDIS_URL = "redis://localhost:6379"
REDIS_POOL_SIZE = 3
DEFAULT_EXPIRE_SECONDS = 600

WORKER_COUNT = 4 # Number of worker tasks in DataServerManager, to process query.

MYSQL_DOCKER_BASE_URL = "localhost"
MYSQL_DOCKER_PORT = 3307
MYSQL_USER = "apix"
MYSQL_PASSWORD = "apixapix"
MYSQL_DATABASE = "apix_database"
MYSQL_CHARSET = "utf8mb4"
AUTO_COMMIT = True