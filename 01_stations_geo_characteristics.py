from pathlib import Path
import geopandas as gpd
import pandas as pd
import logging
from datetime import datetime, timezone
import database
import config

# Configurazione del logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def load_infrastructure_geodata():
    logging.info("🌍 Avvio caricamento Master Data Colonnine (GeoJSON -> MongoDB)...")
    
    # 1. Definizione Percorsi
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "data"
    file_colonnine = DATA_DIR / "ricarica_colonnine.geojson"
    
    if not file_colonnine.exists():
        logging.error(f"❌ File non trovato: {file_colonnine}")
        return
        
    try:
        # 2. Lettura tramite GeoPandas
        gdf = gpd.read_file(file_colonnine)
        logging.info(f"✅ Lette {len(gdf)} colonnine dal file GeoJSON.")
        
        # 3. Connessione a MongoDB Atlas
        client = database.get_db_client()
        db = client[config.DB_NAME]
        collection = db['stations_registry']
        
        # Pulizia per evitare duplicati
        collection.delete_many({})
        
        # 4. Costruzione dello Schema Arricchito
        documenti_da_salvare = []
        for index, row in gdf.iterrows():
            # Estrazione Geometry
            lon = row.geometry.x if row.geometry else None
            lat = row.geometry.y if row.geometry else None
            
            # Scartiamo record privi di coordinate valide
            if pd.isna(lon) or pd.isna(lat):
                continue
            
            # Gestione sicura dell'id_nil
            try:
                nil_val = int(row.get('id_nil')) if pd.notna(row.get('id_nil')) else -1
            except (ValueError, TypeError):
                nil_val = -1

            # Creazione del Documento Completo
            doc = {
                "station_id": str(row.get('id', index)),
                "location": {
                    "type": "Point",
                    "coordinates": [lon, lat]
                },
                "details": {
                    "titolare": str(row.get('titolare', 'Sconosciuto')),
                    "infrastruttura": str(row.get('infrastruttura', 'Sconosciuto')), # Corrisponde al tuo 'infra'
                    "tipologia": str(row.get('tipologia', 'Sconosciuto')),
                    "localita": str(row.get('localita', 'Sconosciuta')),
                    "cerchia": str(row.get('cerchia', 'Sconosciuta'))
                },
                # ---- DATI DI QUARTIERE E PREDISPOSIZIONE ENRICHMENT ----
                "id_nil": nil_val,
                "nome_nil": str(row.get('nome_nil', 'Sconosciuto')),
                "densita_ab_km2": 0.0,  # Spazio allocato per lo script 03
                # ---- DATI INFRASTRUTTURALI ----
                "numero_col": int(row.get('numero_col', 1)),  # Colonnine fisiche nel punto
                "numero_pdr": int(row.get('numero_pdr', 1)),  # Prese di ricarica totali
                # --------------------------------------------------------
                "created_at": datetime.now(timezone.utc)
            }
            documenti_da_salvare.append(doc)
            
        # 5. Inserimento Bulk e Creazione Indici
        if documenti_da_salvare:
            logging.info("💾 Invio dati ad Atlas in corso...")
            collection.insert_many(documenti_da_salvare)
            logging.info(f"✅ Salvate {len(documenti_da_salvare)} anagrafiche complete!")
            
            # Indice 1: Ottimizzazione Spaziale (Mappe)
            collection.create_index([("location", "2dsphere")])
            logging.info("📌 Indice spaziale '2dsphere' creato.")
            
            # Indice 2: Ottimizzazione Relazionale (Merge futuro)
            collection.create_index([("id_nil", 1)])
            logging.info("📌 Indice B-Tree creato su 'id_nil'.")
            
        client.close()
        
    except Exception as e:
        logging.error(f"❌ Errore critico durante l'elaborazione: {e}")

if __name__ == "__main__":
    load_infrastructure_geodata()