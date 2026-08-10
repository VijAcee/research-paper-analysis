import logging
import pymongo
import chromadb
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize MongoDB client with fallback
try:
    mongo_client = pymongo.MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=2000)
    mongo_client.admin.command('ping')
    db = mongo_client[settings.MONGODB_DB_NAME]
    logger.info("Connected to live MongoDB database.")
except Exception as e:
    import mongomock
    logger.warning(f"Local MongoDB instance unreachable ({e}). Using in-memory MongoMock database.")
    mongo_client = mongomock.MongoClient()
    db = mongo_client[settings.MONGODB_DB_NAME]

# ChromaDB client
# Note: Google Colab files or local persistent directories will be used based on configuration.
chroma_client = chromadb.PersistentClient(path=settings.CHROMADB_DIR)

def get_db():
    """Returns the PyMongo database instance."""
    return db

def get_chroma():
    """Returns the ChromaDB persistent client."""
    return chroma_client
