from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(include_in_schema=False)

STATIC = Path(__file__).resolve().parent.parent / "static"


@router.get("/service-worker.js")
def service_worker():
    """Serve the service worker from the site root so its scope covers the whole app."""
    return FileResponse(
        STATIC / "service-worker.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )
