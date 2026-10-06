import logging
# Rimosso: from pymongo import ReplaceOne (non necessario)
import database
import config

# Configurazione del logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def setup_economic_parameters():
    logging.info("💰 Avvio configurazione Parametri Economici...")
    
    # Inizializziamo il client a None per gestirlo in modo sicuro nel blocco finally
    client = None 
    
    # Estraiamo la costante per evitare errori di battitura e rispettare il DRY
    SCENARIO_ID = "baseline_2025"
    
    try:
        # 1. Connessione al DB di Progetto
        client = database.get_db_client()
        db = client[config.DB_NAME]
        
        # 2. Selezione della collezione
        collection = db['simulation_parameters']
        
        # 3. Il nostro dizionario con i dati economici
        pricing_data_2025 = {
            "scenario_id": SCENARIO_ID,
            "description": "Parametri economici e tariffe consolidate per l'anno 2025",
            "b2b_costs": {
                "pun_medio_kwh": 0.13,
                "oneri_e_dispacciamento_kwh": 0.10,
                "total_opex_kwh": 0.23
            },
            "b2c_tariffs": {
                "ac_quick_kwh": 0.65,
                "dc_fast_kwh": 0.90,
                "idle_fee_per_min": 0.10
            },
            "time_of_use_multipliers": {
                "F1_peak_day": 1.15, 
                "F2_mid_day": 1.00,
                "F3_night": 0.85
            }
        }
        
        # 4. Inserimento con Upsert (Idempotente)
        risultato = collection.replace_one(
            {"scenario_id": SCENARIO_ID}, # Usa la variabile
            pricing_data_2025,            # Il nuovo documento
            upsert=True
        )
        
        if risultato.upserted_id:
            logging.info(f"✅ Nuovo scenario '{SCENARIO_ID}' inserito nel database.")
        else:
            logging.info(f"🔄 Scenario '{SCENARIO_ID}' aggiornato con successo.")
            
    except Exception as e:
        logging.error(f"❌ Errore durante l'inserimento dei parametri: {e}")
        
    finally:
        # 5. Chiusura sicura della connessione garantita
        if client is not None:
            client.close()
            logging.info("🔌 Connessione al database chiusa.")

if __name__ == "__main__":
    setup_economic_parameters()