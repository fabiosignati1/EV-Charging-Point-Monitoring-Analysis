from pymongo import MongoClient
import config

def get_db_client() -> MongoClient:
    """Crea e restituisce la connessione al database usando la stringa nascosta."""
    return MongoClient(config.MONGO_URI)

def setup_timeseries_collection():
    """Inizializza la Time Series Collection in MongoDB se non esiste."""
    client = get_db_client()
    db = client[config.DB_NAME]
    
    # Controlliamo se la collezione esiste già
    if config.COLLECTION_NAME not in db.list_collection_names():
        db.create_collection(
            config.COLLECTION_NAME,
            timeseries={
                "timeField": "timestamp",        # Il campo temporale obbligatorio
                "metaField": "station_metadata", # I dati statici della colonnina
                "granularity": "minutes"         # Ottimizza per polling a minuti
            }
        )
        print(f"✅ Time Series Collection '{config.COLLECTION_NAME}' creata con successo.")
    else:
        print(f"ℹ️ La collezione '{config.COLLECTION_NAME}' esiste già.")
    client.close()

def log_status_change(station_id: int, status: str, power_kw: float, timestamp):
    """Scrive il documento strutturato per la Time Series."""
    client = get_db_client()
    db = client[config.DB_NAME]
    collection = db[config.COLLECTION_NAME]
    
    document = {
        "timestamp": timestamp,
        "station_metadata": {
            "station_id": station_id,
            "max_power_kw": power_kw
        },
        "status": status
    }
    
    collection.insert_one(document)
    client.close()




# In fondo al file database.py, sotto le altre funzioni
if __name__ == "__main__":
    print("🔄 Test di connessione a MongoDB Atlas in corso...")
    try:
        setup_timeseries_collection()
        print("🚀 Connessione riuscita e collezione inizializzata su Atlas!")
    except Exception as e:
        print(f"❌ Errore durante il test di connessione: {e}")