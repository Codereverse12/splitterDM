import os
import psycopg2
from psycopg2 import pool
from flask import g, current_app
from config import Config

class Database:
    def __init__(self):
        self.pool = None

    def init_app(self, app):
        """Initialize connection pool"""
        app.teardown_appcontext(self.close_connection)
        
        self.pool = pool.SimpleConnectionPool(
            minconn=Config.dbMinConn,
            maxconn=Config.dbMaxConn,
            host=Config.dbHost,
            database=Config.dbName, 
            user=Config.dbUser,
            password=Config.dbPass,
            port=Config.dbPort
        )

    def get_connection(self):
        """Get a connection from pool"""
        if not hasattr(g, 'db_conn'):
            g.db_conn = self.pool.getconn()
        return g.db_conn

    def close_connection(self, exception=None):
        """Return connection to pool"""
        conn = getattr(g, 'db_conn', None)
        if conn is not None:
            self.pool.putconn(conn)
            g.pop('db_conn', None)

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
            current_app.logger.error(f"Database error: {e}")
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

# Initialize database instance
db = Database()