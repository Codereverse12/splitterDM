from psycopg2.pool import ThreadedConnectionPool
from config import Config 

# Initialize during app creation
conn_pool = ThreadedConnectionPool(
    minconn=Config.dbMinConn,
    maxconn=Config.dbMaxConn,
    host=Config.dbHost,
    database=Config.dbName, 
    user=Config.dbUser,
    password=Config.dbPass,
    port=Config.dbPort
)