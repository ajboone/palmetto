from fastapi import FastAPI

from app.routes.tides import router as tides_router


app = FastAPI(title="PALMETTO API")
app.include_router(tides_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "palmetto-api"}