from pathlib import Path
import pandas as pd
import logging
from pymongo import UpdateOne
import database
import config

# Configurazione del logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def esegui_data_enrichment():
    logging.info("🧠 Avvio Data Enrichment: Fusione Popolazione + Densità...")
    
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "data"
    
    # 1. Puntiamo DIRETTAMENTE al file Excel originale
    file_pop = DATA_DIR / "Popolazione_residente_al_31_12_2025_NIL_(Nuclei_di_Identità_Locale).xlsx"
    file_den = DATA_DIR / "densita_abitativa_per_nil.csv"
    
    if not file_pop.exists() or not file_den.exists():
        logging.error("❌ File mancanti. Assicurati di avere l'XLSX e il CSV in 'data/'.")
        return
        
    try:
        # --- FIX 1: Lettura diretta Excel ---
        # Usiamo engine='openpyxl' per leggere il formato xlsx
        df_pop = pd.read_excel(file_pop, sheet_name=0, engine='openpyxl')
        
        # Pulizia File Popolazione
        df_pop = df_pop[df_pop['NIL (Nuclei di Identità Locale)'] != 'Totale'].copy()
        df_pop['id_nil'] = df_pop['NIL (Nuclei di Identità Locale)'].astype(str).str.split('_').str[0].astype(int)
        df_pop.rename(columns={'Residenti': 'popolazione_residente'}, inplace=True)
        df_pop = df_pop[['id_nil', 'popolazione_residente']] 
        
        # --- FIX 2 & 3: Lettura Densità senza Header e come Stringa ---
        colonne_densita = ['id_nil', 'densita_ab_km2', 'nome_nil', 'coordinate_centroide', 'etichetta']
        
        # header=None evita che la prima riga (Duomo) venga cancellata.
        # dtype={...} forza Pandas a leggere la densità come testo puro, evitando che "11.060" diventi "11.06"
        df_den = pd.read_csv(file_den, names=colonne_densita, header=None, dtype={'densita_ab_km2': str})
        
        # Ora che è una stringa pura ("11.060"), togliamo il punto e convertiamo in Float (11060.0)
        df_den['densita_ab_km2'] = df_den['densita_ab_km2'].str.replace('.', '', regex=False).astype(float)
        df_den['id_nil'] = df_den['id_nil'].astype(int)
        
        # 3. FUSIONE DEI DATI (OUTER JOIN)
        # Usiamo 'outer' per non perdere nessun quartiere, anche se manca in uno dei due file
        df_merged = pd.merge(df_pop, df_den, on='id_nil', how='outer')
        
        # Trasformiamo in dizionario
        dati_quartieri = df_merged.set_index('id_nil').to_dict('index')
        logging.info(f"📊 Dati fusi con successo per {len(dati_quartieri)} quartieri.")

        # 4. CONNESSIONE A MONGODB
        client = database.get_db_client()
        db = client[config.DB_NAME]
        collection = db['stations_registry']
        
        stazioni = list(collection.find({}, {"_id": 1, "id_nil": 1}))
        
        # 5. PREPARAZIONE DEL BULK UPDATE
        operazioni_bulk = []
        
        for stazione in stazioni:
            nil_corrente = stazione.get("id_nil", -1)
            
            # Se il nil non c'è, mettiamo valori sicuri di default
            dati_nil = dati_quartieri.get(nil_corrente, {})
            pop_res = dati_nil.get('popolazione_residente', 0)
            den_km2 = dati_nil.get('densita_ab_km2', 0.0)
            
            # Gestione sicura dei NaN di Pandas
            if pd.isna(pop_res): pop_res = 0
            if pd.isna(den_km2): den_km2 = 0.0
            
            campi_da_aggiornare = {
                "popolazione_residente": int(pop_res),
                "densita_ab_km2": float(den_km2)
            }
            
            # Estrazione Centroide
            centroide_str = dati_nil.get('coordinate_centroide')
            if pd.notna(centroide_str) and isinstance(centroide_str, str):
                parti = centroide_str.split() # Divide "45.4637 9.187" in ["45.4637", "9.187"]
                if len(parti) == 2:
                    campi_da_aggiornare["centroide_nil"] = {
                        "type": "Point",
                        "coordinates": [float(parti[1]), float(parti[0])] # GeoJSON: [Longitudine, Latitudine]
                    }

            operazione = UpdateOne(
                {"_id": stazione["_id"]},
                {"$set": campi_da_aggiornare}
            )
            operazioni_bulk.append(operazione)
        
        # 6. ESECUZIONE
        if operazioni_bulk:
            risultato = collection.bulk_write(operazioni_bulk)
            logging.info(f"✅ Successo! Iniettati i super-dati in {risultato.modified_count} colonnine.")
            
            # Creiamo l'indice spaziale anche sul centro del quartiere
            collection.create_index([("centroide_nil", "2dsphere")])
            
        client.close()
        
    except Exception as e:
        logging.error(f"❌ Errore critico durante l'arricchimento: {e}")

if __name__ == "__main__":
    esegui_data_enrichment()