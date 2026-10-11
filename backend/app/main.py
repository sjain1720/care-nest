from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.routers import case, health, policy

app = FastAPI(title="CareNest API", version="0.3.0")

app.include_router(health.router, prefix="/api")
app.include_router(policy.router, prefix="/api")
app.include_router(case.router, prefix="/api")

# In the container the Angular build is copied here; locally Angular runs on :4200 instead.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@app.get("/{full_path:path}", include_in_schema=False)
def serve_spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")

    index = STATIC_DIR / "index.html"
    if not index.exists():
        return {"message": "CareNest API is running. Start the UI with 'npm start' in frontend/."}

    requested = (STATIC_DIR / full_path).resolve()
    if requested.is_file() and requested.is_relative_to(STATIC_DIR.resolve()):
        return FileResponse(requested)
    return FileResponse(index)
