from flask import g, current_app
from config import Config
from db_pool import conn_pool

def get_connection():
    """Get a connection from pool"""
    if not hasattr(g, 'db_conn'):
        g.db_conn = conn_pool.getconn()
    return g.db_conn

def execute(query, args=(), commit=False):
    """Execute SQL query and return cursor"""
    conn = get_connection()
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

def fetch(query, args=(), one=False):
    """Fetch results as dictionaries"""
    with execute(query, args) as cur:
        columns = [desc[0] for desc in cur.description]
        results = [dict(zip(columns, row)) for row in cur.fetchall()]
        return results[0] if (one and results) else results

def update(query, args=()):
    """Update or Delete or Insert records"""
    with execute(query, args, commit=True) as cur:
        return cur.rowcount