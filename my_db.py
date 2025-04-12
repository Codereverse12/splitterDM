from cs50 import SQL

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///autoSplitter.db")

def query_db(*args):
    return db.execute(*args)
