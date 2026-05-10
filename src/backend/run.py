import os
import sys
from pathlib import Path

import uvicorn


def main() -> None:
    backend_root = Path(__file__).resolve().parent
    sys.path.insert(0, str(backend_root))

    project_root = backend_root.parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        with open(env_file, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("\"'")
                if key not in os.environ:
                    os.environ[key] = value

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host=host, port=port)


if __name__ == "__main__":
    main()
