"""Postgres + pgvector connection. Same code local and on Cloud SQL.

Local:  connects to DB_HOST:DB_PORT (docker-compose).
Prod:   if INSTANCE_CONNECTION_NAME is set, connects via the Cloud SQL
        Unix socket that Cloud Run mounts at /cloudsql/<INSTANCE>.
"""
import psycopg2
from pgvector.psycopg2 import register_vector
from . import config


def connect():
    if config.INSTANCE_CONNECTION_NAME:
        # Cloud Run mounts the socket here when deployed with
        #   --add-cloudsql-instances <INSTANCE_CONNECTION_NAME>
        conn = psycopg2.connect(
            host=f"/cloudsql/{config.INSTANCE_CONNECTION_NAME}",
            dbname=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
        )
    else:
        conn = psycopg2.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            dbname=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
        )
    register_vector(conn)
    return conn
