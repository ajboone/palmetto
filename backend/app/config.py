import os


NOAA_API_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
NOAA_STATION_ID = os.getenv("PALMETTO_NOAA_STATION_ID", "8665530")
NOAA_STATION_NAME = "Charleston, South Carolina"
NOAA_DATUM = "MLLW"
NOAA_TIMEOUT_SECONDS = 10.0
CHARLESTON_TIME_ZONE = "America/New_York"
NOAA_SOURCE = "NOAA CO-OPS Data API"