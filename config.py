import os
from dotenv import load_dotenv

# Carica le variabili dal file .env
load_dotenv()

_mongo_uri = os.getenv("MONGO_URI")
_neo4j_password = os.getenv("NEO4J_PASSWORD")

if not _mongo_uri:
    raise ValueError("⚠️ Manca la stringa MONGO_URI nel file .env!")
if not _neo4j_password:
    raise ValueError("⚠️ Manca la stringa NEO4J_PASSWORD nel file .env!")

# Dopo la validazione, i tipi sono garantiti come 'str' (non più str | None)
MONGO_URI: str = _mongo_uri
NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD: str = _neo4j_password

# Coordinate del Comune di Milano
MILANO_LAT = 45.4642
MILANO_LON = 9.1900
RADIUS_KM = 8



DB_NAME = "ev_analytics_milano"
COLLECTION_NAME = "charging_events"


HEADERS = {
    "User-Agent": "Milano_EV_University_Project/2.0 (junior_dev@mail.com)"
}