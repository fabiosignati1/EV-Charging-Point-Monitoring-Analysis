from pathlib import Path
import requests
import pandas as pd
import logging
import database
import config

# Configurazione del logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def pipeline_meteo_completa():
    logging.info("🚀 Avvio Pipeline ETL Meteo: API -> CSV -> MongoDB")
    
    # ==========================================
    # SETUP PERCORSI (Cartella 'data')
    # ==========================================
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "data"
    
    # Assicuriamoci che la cartella 'data' esista, altrimenti la creiamo
    DATA_DIR.mkdir(exist_ok=True)
    
    csv_path = DATA_DIR / "storico_meteo.csv"

    # ==========================================
    # FASE 1 & 2: EXTRACT (API) & STAGING (CSV)
    # ==========================================
    logging.info("📡 Fase 1: Download dati da API Open-Meteo...")
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": config.MILANO_LAT,
        "longitude": config.MILANO_LON,
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "hourly": "temperature_2m,precipitation,cloud_cover",
        "timezone": "GMT"  # Manteniamo la correzione UTC
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code != 200:
            logging.error(f"❌ Errore API Meteo: {response.text}")
            return
            
        dati_api = response.json()["hourly"]
        
        # Creiamo un DataFrame temporaneo per salvare il CSV
        df_staging = pd.DataFrame({
            "timestamp": dati_api["time"],
            "temperature": dati_api["temperature_2m"],
            "precipitation": dati_api["precipitation"],
            "cloud_cover": dati_api["cloud_cover"]
        })
        
        # Salvataggio fisico nella cartella data/
        df_staging.to_csv(csv_path, index=False)
        logging.info(f"💾 Fase 2: Dati salvati con successo in staging locale: {csv_path}")
        
    except Exception as e:
        logging.error(f"❌ Errore durante il download o il salvataggio CSV: {e}")
        return

    # ==========================================
    # FASE 3: LOAD (Lettura CSV -> MongoDB)
    # ==========================================
    logging.info("☁️ Fase 3: Lettura da 'data/' e caricamento su MongoDB...")
    try:
        # Lettura del file appena salvato
        df_weather = pd.read_csv(csv_path)
        
        # Correzione del fuso orario (UTC garantito)
        df_weather["timestamp"] = pd.to_datetime(df_weather["timestamp"], utc=True)
        
        # Connessione al database
        client = database.get_db_client()
        db = client[config.DB_NAME]
        collection = db['weather_history']
        
        # Pulizia collezione per evitare duplicati
        collection.delete_many({})
        
        # Preparazione documenti JSON/BSON
        documenti_da_salvare = []
        for _, row in df_weather.iterrows():
            doc = {
                "timestamp": row["timestamp"].to_pydatetime(),
                "location": "Milano",
                "metrics": {
                    "temperature_c": float(row["temperature"]) if pd.notna(row["temperature"]) else 0.0,
                    "precipitation_mm": float(row["precipitation"]) if pd.notna(row["precipitation"]) else 0.0,
                    "cloud_cover_pct": int(row["cloud_cover"]) if pd.notna(row["cloud_cover"]) else 0
                }
            }
            documenti_da_salvare.append(doc)
            
        # Inserimento Bulk e Indicizzazione
        if documenti_da_salvare:
            collection.insert_many(documenti_da_salvare)
            logging.info(f"✅ Inseriti {len(documenti_da_salvare)} record in MongoDB Atlas.")
            
            collection.create_index([("timestamp", 1)])
            logging.info("📌 Indice B-Tree creato sul campo 'timestamp'.")
            
        client.close()
        logging.info("🎉 Pipeline ETL Meteo completata con successo!")
        
    except Exception as e:
        logging.error(f"❌ Errore critico durante il caricamento in MongoDB: {e}")

if __name__ == "__main__":
    pipeline_meteo_completa()