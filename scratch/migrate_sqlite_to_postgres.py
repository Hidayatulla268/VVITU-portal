import os
import sys
import subprocess

def run_step(description, command):
    print(f"\n[STEP] {description}...")
    print(f"Command: {command}")
    res = subprocess.run(command, shell=True, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"[SUCCESS] {description} completed.")
        if res.stdout.strip():
            print("Output:", res.stdout.strip()[:300])
        return True
    else:
        print(f"[ERROR] {description} failed!")
        print("Error output:", res.stderr.strip()[:500])
        return False

def main():
    print("============================================================")
    print("  VVITU Portal — SQLite to PostgreSQL Migration Helper")
    print("============================================================")

    # 1. Export Data from SQLite
    dump_cmd = (
        f"{sys.executable} manage.py dumpdata "
        f"--natural-foreign --natural-primary "
        f"--exclude contenttypes --exclude auth.permission --exclude sessions "
        f"--indent 2 -o sqlite_datadump.json"
    )
    if not run_step("Exporting SQLite database to sqlite_datadump.json", dump_cmd):
        print("\nExport failed. Check logs above.")
        return

    dump_size = os.path.getsize("sqlite_datadump.json") if os.path.exists("sqlite_datadump.json") else 0
    print(f"\n[OK] Exported Data Dump File: sqlite_datadump.json ({dump_size / 1024:.2f} KB)")

    print("""
============================================================
  POSTGRESQL MIGRATION INSTRUCTIONS
============================================================

1. Ensure PostgreSQL is installed and running on your machine (or remote server).
2. Create a new PostgreSQL database in pgAdmin or via psql:
   CREATE DATABASE vvitu_portal_db;

3. Add your PostgreSQL connection credentials to your .env file:

   DB_ENGINE=postgresql
   DB_NAME=vvitu_portal_db
   DB_USER=postgres
   DB_PASSWORD=your_postgres_password
   DB_HOST=localhost
   DB_PORT=5432

   (OR for cloud databases like Render/Neon/Supabase/Railway):
   DATABASE_URL=postgres://user:password@host:5432/vvitu_portal_db

4. Run the following 2 commands to apply schema & import all data into PostgreSQL:
   
   venv\\Scripts\\python.exe manage.py migrate
   venv\\Scripts\\python.exe manage.py loaddata sqlite_datadump.json

============================================================
""")

if __name__ == '__main__':
    main()
