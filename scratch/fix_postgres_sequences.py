import os
import sys
import django

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VVITU_Portal.settings')
django.setup()

from django.db import connection

def reset_sequences():
    print("============================================================")
    print("  POSTGRESQL PRIMARY KEY SEQUENCE SYNCHRONIZER")
    print("============================================================")

    if connection.vendor != 'postgresql':
        print(f"Current DB is '{connection.vendor}', sequence reset is specific to PostgreSQL.")
        return

    with connection.cursor() as cursor:
        # Fetch all sequence reset SQL statements for installed Django apps
        sql_queries = [
            "SELECT setval(pg_get_serial_sequence('\"' || table_name || '\"', 'id'), COALESCE(MAX(id), 1)) FROM \"' || table_name || '\";'"
        ]
        
        # Get all table names in public schema
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
        """)
        tables = [row[0] for row in cursor.fetchall()]

        resets_done = 0
        for table in tables:
            try:
                # Check if table has an 'id' column
                cursor.execute(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = '{table}' AND column_name = 'id';
                """)
                if cursor.fetchone():
                    seq_reset_sql = f"""
                        SELECT setval(
                            pg_get_serial_sequence('{table}', 'id'),
                            COALESCE((SELECT MAX(id) FROM "{table}"), 1)
                        );
                    """
                    cursor.execute(seq_reset_sql)
                    resets_done += 1
            except Exception as e:
                pass

        print(f"[SUCCESS] Synchronized {resets_done} primary key sequences in PostgreSQL!")
    print("============================================================")

if __name__ == '__main__':
    reset_sequences()
