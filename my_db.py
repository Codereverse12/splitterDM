from cs50 import SQL
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///autoSplitter.db")

def query_db(*args):
    try:
        return db.execute(*args)
    except Exception as e:
        logging.error(f"Database error: {e}")