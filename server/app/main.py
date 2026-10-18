from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import admin, auth, claims, flags, notifications, reports

app = FastAPI(title="TIET LostLink API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.client_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "lostlink-backend",
        "time": datetime.now(timezone.utc).isoformat(),
    }


app.include_router(auth.router)
app.include_router(reports.router)
app.include_router(claims.router)
app.include_router(notifications.router)
app.include_router(flags.router)
app.include_router(admin.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, reload=True)
