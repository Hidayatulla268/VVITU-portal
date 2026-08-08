import os

def fix_encoding():
    print("Reading sqlite_datadump.json with cp1252 encoding...")
    with open("sqlite_datadump.json", "r", encoding="cp1252", errors="replace") as f:
        content = f.read()

    print("Writing sqlite_datadump.json with clean UTF-8 encoding...")
    with open("sqlite_datadump.json", "w", encoding="utf-8") as f:
        f.write(content)

    print("[SUCCESS] sqlite_datadump.json converted to UTF-8.")

if __name__ == '__main__':
    fix_encoding()
