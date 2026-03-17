import os

env_path = "/home/zack/dev/promaia/.env"

try:
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()
    has_backend = False
    for i, line in enumerate(lines):
        if line.startswith("STORE_BACKEND"):
            lines[i] = "STORE_BACKEND=libsql"
            has_backend = True

    if not has_backend:
        lines.append("STORE_BACKEND=libsql")

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
        
    print(f"Successfully set STORE_BACKEND=libsql in {env_path}")
except Exception as e:
    print(f"Failed to update .env: {e}")
