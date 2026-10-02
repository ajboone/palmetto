from fastapi import FastAPI

from app.routes.roads import router as roads_router
from app.routes.risk import router as risk_router
from app.routes.tides import router as tides_router
from app.routes.weather import router as weather_router


app = FastAPI(title="PALMETTO API")
app.include_router(tides_router)
app.include_router(weather_router)
app.include_router(roads_router)
app.include_router(risk_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "palmetto-api"}