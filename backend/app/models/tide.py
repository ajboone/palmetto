from datetime import datetime

from pydantic import BaseModel


class TideObservation(BaseModel):
    station_id: str
    station_name: str
    value: float
    unit: str
    timestamp: datetime
    datum: str
    source: str


class TidePrediction(BaseModel):
    station_id: str
    station_name: str
    timestamp: datetime
    height: float
    unit: str
    datum: str
    type: str | None
    source: str