from datetime import datetime

from pydantic import BaseModel


class RoadImpact(BaseModel):
    id: str
    road_name: str | None
    description: str | None
    status: str | None
    impact_type: str | None
    reason: str | None
    start_time: datetime | None
    end_time: datetime | None
    latitude: float | None
    longitude: float | None
    source: str
    source_layer: str