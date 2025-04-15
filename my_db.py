from cs50 import SQL
import logging
from config import Config
from urllib.parse import quote

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configure CS50 Library to use SQLite database
db = SQL(f"postgresql://{Config.dbUser}:{quote(Config.dbPass)}@{Config.dbHost}:{Config.dbPort}/{Config.dbName}")

def query_db(*args):
    try:
        return db.execute(*args)
    except Exception as e:
        logging.error(f"Database error: {e}")
        db.execute("ROLLBACK;")
        raise