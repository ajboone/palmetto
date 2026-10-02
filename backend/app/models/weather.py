from datetime import datetime

from pydantic import BaseModel


class WeatherPeriod(BaseModel):
    start_time: datetime
    end_time: datetime | None
    temperature: float | None
    temperature_unit: str | None
    precipitation_probability: float | None
    short_forecast: str | None
    wind_speed: str | None
    wind_direction: str | None
    source: str


class PrecipitationForecast(BaseModel):
    start_time: datetime
    end_time: datetime | None
    amount: float
    unit: str
    source: str


class WeatherAlert(BaseModel):
    id: str
    event: str
    severity: str | None
    urgency: str | None
    certainty: str | None
    headline: str | None
    description: str | None
    instruction: str | None
    effective: datetime | None
    onset: datetime | None
    expires: datetime | None
    source: str