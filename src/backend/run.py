import os
import sys
from pathlib import Path

import uvicorn


def main() -> None:
    backend_root = Path(__file__).resolve().parent
    sys.path.insert(0, str(backend_root))

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host=host, port=port)


if __name__ == "__main__":
    main()
