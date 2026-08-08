import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from decouple import config

def create_db():
    user = config('DB_USER', default='postgres')
    password = config('DB_PASSWORD', default='postgres')
    host = config('DB_HOST', default='localhost')
    port = config('DB_PORT', default='5432')
    db_name = config('DB_NAME', default='vvitu_portal_db')

    print("============================================================")
    print("  AUTOMATIC POSTGRESQL DATABASE CREATOR")
    print("============================================================")
    print(f"Connecting to PostgreSQL server at {host}:{port} as user '{user}'...")

    try:
        # Connect to default 'postgres' database first
        conn = psycopg2.connect(
            dbname='postgres',
            user=user,
            password=password,
            host=host,
            port=port
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Check if database already exists
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s;", (db_name,))
        exists = cursor.fetchone()

        if not exists:
            print(f"Creating database '{db_name}'...")
            cursor.execute(f'CREATE DATABASE "{db_name}";')
            print(f"[SUCCESS] Database '{db_name}' created successfully!")
        else:
            print(f"[OK] Database '{db_name}' already exists.")

        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] Failed to connect or create database: {e}")
        print("\nTip: Ensure your DB_USER and DB_PASSWORD in .env match your PostgreSQL superuser credentials.")
        return False

if __name__ == '__main__':
    create_db()
