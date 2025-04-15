from config import Config
from db_pool import conn_pool
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class db:
    def __init__(self):
        self.conn = None
    
    def get_connection(self):
        """Get a connection from pool"""
        if self.conn is None:
            return conn_pool.getconn()
        return self.conn
    
    def put_connection(self):
        """Put a connection from pool"""
        if self.conn:
            conn_pool.putconn(self.conn)

    def execute(self, query, args=(), commit=False):
        """Execute SQL query and return cursor"""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, args)
            if commit:
                conn.commit()
            return cur
        except Exception as e:
            conn.rollback()
            logging.error(f"Database error: {e}")
            raise

    def fetch(self, query, args=(), one=False):
        """Fetch results as dictionaries"""
        with self.execute(query, args) as cur:
            columns = [desc[0] for desc in cur.description]
            results = [dict(zip(columns, row)) for row in cur.fetchall()]
            return results[0] if (one and results) else results

    def update(self, query, args=()):
        """Update or Delete or Insert records"""
        with self.execute(query, args, commit=True) as cur:
            return cur.rowcount