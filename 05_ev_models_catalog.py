import logging
import database
import config

# Configurazione del logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def setup_ev_models_catalog():
    logging.info("🚗 Avvio creazione Catalogo Modelli EV per il simulatore...")
    
    client = None 
    
    # Dataset curato dei modelli BEV e PHEV più rappresentativi in Italia
    # I pesi (market_share_weight) sommano a 1.00 e servono per il campionamento stocastico
    ev_models_data = [
        {
            "make": "Tesla", "model": "Model Y Long Range", "vehicle_type": "BEV",
            "battery_specs": {"capacity_kwh": 78.1, "usable_kwh": 75.0},
            "charging_specs": {"max_ac_kw": 11.0, "max_dc_kw": 250.0},
            "efficiency": {"consumption_kwh_per_100km": 17.5, "real_world_range_km": 430},
            "market_share_weight": 0.15
        },
        {
            "make": "Fiat", "model": "500e 42kWh", "vehicle_type": "BEV",
            "battery_specs": {"capacity_kwh": 42.0, "usable_kwh": 37.3},
            "charging_specs": {"max_ac_kw": 11.0, "max_dc_kw": 85.0},
            "efficiency": {"consumption_kwh_per_100km": 14.5, "real_world_range_km": 250},
            "market_share_weight": 0.15
        },
        {
            "make": "Tesla", "model": "Model 3 RWD", "vehicle_type": "BEV",
            "battery_specs": {"capacity_kwh": 60.0, "usable_kwh": 57.5},
            "charging_specs": {"max_ac_kw": 11.0, "max_dc_kw": 170.0},
            "efficiency": {"consumption_kwh_per_100km": 14.4, "real_world_range_km": 400},
            "market_share_weight": 0.10
        },
        {
            "make": "Smart", "model": "EQ fortwo", "vehicle_type": "BEV",
            "battery_specs": {"capacity_kwh": 17.6, "usable_kwh": 16.7},
            "charging_specs": {"max_ac_kw": 22.0, "max_dc_kw": 0.0}, # Molto comune a Milano, ricarica veloce solo in AC
            "efficiency": {"consumption_kwh_per_100km": 16.7, "real_world_range_km": 100},
            "market_share_weight": 0.10
        },
        {
            "make": "Jeep", "model": "Compass 4xe", "vehicle_type": "PHEV",
            "battery_specs": {"capacity_kwh": 11.4, "usable_kwh": 11.4},
            "charging_specs": {"max_ac_kw": 7.4, "max_dc_kw": 0.0}, # Ibride plug-in: caricamento lento, niente DC
            "efficiency": {"consumption_kwh_per_100km": 18.0, "real_world_range_km": 45},
            "market_share_weight": 0.10
        },
        {
            "make": "Dacia", "model": "Spring Electric 65", "vehicle_type": "BEV",
            "battery_specs": {"capacity_kwh": 26.8, "usable_kwh": 26.8},
            "charging_specs": {"max_ac_kw": 7.4, "max_dc_kw": 30.0},
            "efficiency": {"consumption_kwh_per_100km": 13.5, "real_world_range_km": 190},
            "market_share_weight": 0.08
        },
        {
            "make": "Peugeot", "model": "e-208", "vehicle_type": "BEV",
            "battery_specs": {"capacity_kwh": 50.0, "usable_kwh": 46.3},
            "charging_specs": {"max_ac_kw": 11.0, "max_dc_kw": 100.0},
            "efficiency": {"consumption_kwh_per_100km": 16.0, "real_world_range_km": 290},
            "market_share_weight": 0.08
        },
        {
            "make": "MG", "model": "MG4 Standard", "vehicle_type": "BEV",
            "battery_specs": {"capacity_kwh": 51.0, "usable_kwh": 50.8},
            "charging_specs": {"max_ac_kw": 6.6, "max_dc_kw": 117.0},
            "efficiency": {"consumption_kwh_per_100km": 17.0, "real_world_range_km": 300},
            "market_share_weight": 0.08
        },
        {
            "make": "Ford", "model": "Kuga PHEV", "vehicle_type": "PHEV",
            "battery_specs": {"capacity_kwh": 14.4, "usable_kwh": 14.4},
            "charging_specs": {"max_ac_kw": 3.7, "max_dc_kw": 0.0}, # Occupa la colonnina a lungo comprando pochi kWh
            "efficiency": {"consumption_kwh_per_100km": 16.5, "real_world_range_km": 50},
            "market_share_weight": 0.08
        },
        {
            "make": "Audi", "model": "Q4 e-tron 40", "vehicle_type": "BEV",
            "battery_specs": {"capacity_kwh": 82.0, "usable_kwh": 76.6},
            "charging_specs": {"max_ac_kw": 11.0, "max_dc_kw": 135.0},
            "efficiency": {"consumption_kwh_per_100km": 18.5, "real_world_range_km": 410},
            "market_share_weight": 0.08
        }
    ]
    
    try:
        # 1. Connessione al DB
        client = database.get_db_client()
        db = client[config.DB_NAME]
        
        # 2. Selezione della collezione
        collection = db['ev_models_catalog']
        
        # 3. Inserimento iterativo e idempotente (Upsert)
        inseriti = 0
        aggiornati = 0
        
        for vehicle in ev_models_data:
            # Creiamo un identificativo logico unico (es. "Tesla_Model Y Long Range")
            model_id = f"{vehicle['make']}_{vehicle['model']}"
            
            # Aggiungiamo l'ID logico al documento per comodità di ricerca futura
            vehicle['model_id'] = model_id
            
            risultato = collection.replace_one(
                {"model_id": model_id}, # Cerca se esiste già questo specifico modello
                vehicle,                # Sostituisci o inserisci i dati completi
                upsert=True
            )
            
            if risultato.upserted_id:
                inseriti += 1
            else:
                aggiornati += 1
                
        logging.info(f"✅ Operazione completata. Nuovi modelli inseriti: {inseriti}. Modelli aggiornati: {aggiornati}.")
            
    except Exception as e:
        logging.error(f"❌ Errore durante la creazione del catalogo EV: {e}")
        
    finally:
        # Chiusura sicura
        if client is not None:
            client.close()
            logging.info("🔌 Connessione al database chiusa.")

if __name__ == "__main__":
    setup_ev_models_catalog()