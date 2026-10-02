import os


NOAA_API_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
NOAA_STATION_ID = os.getenv("PALMETTO_NOAA_STATION_ID", "8665530")
NOAA_STATION_NAME = "Charleston, South Carolina"
NOAA_DATUM = "MLLW"
NOAA_TIMEOUT_SECONDS = 10.0
CHARLESTON_TIME_ZONE = "America/New_York"
NOAA_SOURCE = "NOAA CO-OPS Data API"

NWS_API_BASE = "https://api.weather.gov"
NWS_LATITUDE = float(os.getenv("PALMETTO_NWS_LATITUDE", "32.7765"))
NWS_LONGITUDE = float(os.getenv("PALMETTO_NWS_LONGITUDE", "-79.9311"))
NWS_TIMEOUT_SECONDS = 10.0
NWS_USER_AGENT = "PALMETTO flood decision intelligence prototype"

CHARLESTON_GIS_MAPSERVER = (
	"https://gis.charleston-sc.gov/arcgis2/rest/services/External/"
	"RoadClosuresViewer/MapServer"
)
CHARLESTON_GIS_TIMEOUT_SECONDS = 10.0

PALMETTO_OPENAI_MODEL = os.getenv("PALMETTO_OPENAI_MODEL", "gpt-5-mini")
PALMETTO_AGENT_MAX_TOOL_ITERATIONS = 6

# PALMETTO prototype rules; these are not government flood thresholds.
RISK_COMPONENT_WEIGHTS = {
	"water_level": 30,
	"tide": 20,
	"precipitation": 20,
	"weather_alerts": 15,
	"road_impacts": 15,
}
RISK_CATEGORY_BOUNDS = (
	(int(os.getenv("PALMETTO_LOW_MAX_SCORE", "19")), "LOW"),
	(int(os.getenv("PALMETTO_MODERATE_MAX_SCORE", "39")), "MODERATE"),
	(int(os.getenv("PALMETTO_HIGH_MAX_SCORE", "69")), "HIGH"),
	(100, "SEVERE"),
)

PALMETTO_WATER_LEVEL_ELEVATED_FT = float(
	os.getenv("PALMETTO_WATER_LEVEL_ELEVATED_FT", "4.0")
)
PALMETTO_WATER_LEVEL_HIGH_FT = float(
	os.getenv("PALMETTO_WATER_LEVEL_HIGH_FT", "5.0")
)
PALMETTO_WATER_LEVEL_SEVERE_FT = float(
	os.getenv("PALMETTO_WATER_LEVEL_SEVERE_FT", "6.0")
)
PALMETTO_TIDE_ELEVATED_FT = float(os.getenv("PALMETTO_TIDE_ELEVATED_FT", "4.0"))
PALMETTO_TIDE_HIGH_FT = float(os.getenv("PALMETTO_TIDE_HIGH_FT", "5.0"))
PALMETTO_TIDE_SEVERE_FT = float(os.getenv("PALMETTO_TIDE_SEVERE_FT", "6.0"))
PALMETTO_WATER_LEVEL_MAX_AGE_HOURS = float(
	os.getenv("PALMETTO_WATER_LEVEL_MAX_AGE_HOURS", "3")
)
PALMETTO_PRECIPITATION_THRESHOLDS_MM = tuple(
	float(value)
	for value in os.getenv("PALMETTO_PRECIPITATION_THRESHOLDS_MM", "10,25,50,75").split(",")
)
PALMETTO_PRECIPITATION_POP_THRESHOLDS = tuple(
	float(value)
	for value in os.getenv("PALMETTO_PRECIPITATION_POP_THRESHOLDS", "20,50,80").split(",")
)
PALMETTO_RISK_TIME_HORIZON_HOURS = 24