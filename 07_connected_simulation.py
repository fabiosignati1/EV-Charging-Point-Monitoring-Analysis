import random
import logging
from datetime import datetime, timedelta
import database
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class StationState:
    AVAILABLE = "AVAILABLE"
    CHARGING = "CHARGING"
    IDLE = "IDLE"

class ChargingPoint:
    def __init__(self, db_document, parametri_eco, presa_index=0):
        self.id = str(db_document.get('_id'))
        self.presa_index = presa_index  # Indice della presa (0-based) all'interno della stazione
        self.nil_id = db_document.get('id_nil', 0)
        self.is_dc = (db_document.get('tipo_corrente', 'AC') == 'DC')
        self.max_power_kw = 50.0 if self.is_dc else 22.0
        self.parametri_eco = parametri_eco
        
        # --- ENRICHMENT: Estraiamo i nomi descrittivi dal documento di MongoDB ---
        self.nil_nome = db_document.get('nome_nil', 'Quartiere Sconosciuto')
        self.nome_colonnina = db_document.get('details', {}).get('localita', 'Indirizzo Sconosciuto')
        self.numero_pdr = db_document.get('numero_pdr', 1)
        
        # Assegnazione Probabilità Base basata sul quartiere (NIL)
        if self.nil_id <= 9:      
            self.prob_base = 0.12
        elif 10 <= self.nil_id <= 45: 
            self.prob_base = 0.08
        else:                             
            self.prob_base = 0.04
            
        self.state = StationState.AVAILABLE
        self.minutes_remaining = 0
        
        self.current_car = None
        self.session_start = None
        self.session_kwh = 0.0
        self.session_revenue = 0.0

    def start_charging(self, car_model, current_time):
        self.state = StationState.CHARGING
        self.current_car = car_model
        self.session_start = current_time
        
        soc_iniziale = random.randint(10, 50)
        kwh_necessari = car_model['battery_specs']['capacity_kwh'] * ((80 - soc_iniziale) / 100)
        car_max_power = car_model['charging_specs']['max_dc_kw'] if self.is_dc else car_model['charging_specs']['max_ac_kw']
        
        potenza_effettiva = min(self.max_power_kw, car_max_power)
        durata_ore = kwh_necessari / potenza_effettiva if potenza_effettiva > 0 else 0
        
        self.minutes_remaining = int(durata_ore * 60)
        self.session_kwh = 0.0
        self.session_revenue = 0.0

    def update_tick(self, current_time, tick_minutes=15):
        log_entry = None 
        
        if self.state == StationState.CHARGING:
            self.minutes_remaining -= tick_minutes
            
            car_max_power = self.current_car['charging_specs']['max_dc_kw'] if self.is_dc else self.current_car['charging_specs']['max_ac_kw']
            potenza_effettiva = min(self.max_power_kw, car_max_power)
            
            kwh_tick = potenza_effettiva * (tick_minutes / 60)
            self.session_kwh += kwh_tick
            
            tariffa = self.parametri_eco['b2c_tariffs']['dc_fast_kwh'] if self.is_dc else self.parametri_eco['b2c_tariffs']['ac_quick_kwh']
            self.session_revenue += kwh_tick * tariffa
            
            if self.minutes_remaining <= 0:
                # --- ENRICHMENT NEI LOG DI RICARICA ---
                log_entry = {
                    "id_colonnina": self.id,
                    "presa_index": self.presa_index,         # Identifica la presa specifica
                    "numero_pdr": self.numero_pdr,           # Prese totali della stazione
                    "nome_colonnina": self.nome_colonnina,
                    "id_nil": self.nil_id,
                    "nome_nil": self.nil_nome,
                    "tipo_evento": "CHARGING",
                    "timestamp_inizio": self.session_start,
                    "timestamp_fine": current_time,
                    "modello_auto": self.current_car['model'],
                    "energia_kwh": round(self.session_kwh, 2),
                    "ricavo_euro": round(self.session_revenue, 2)
                }
                
                if random.random() < 0.20:
                    self.state = StationState.IDLE
                    self.session_start = current_time
                    self.minutes_remaining = random.randint(15, 60)
                    self.session_kwh = 0.0
                    self.session_revenue = 0.0
                else:
                    self.state = StationState.AVAILABLE
                    self.current_car = None

        elif self.state == StationState.IDLE:
            self.minutes_remaining -= tick_minutes
            self.session_revenue += tick_minutes * self.parametri_eco['b2c_tariffs']['idle_fee_per_min']
            
            if self.minutes_remaining <= 0:
                # --- ENRICHMENT NEI LOG DI SOSTA ABUSIVA (IDLE) ---
                log_entry = {
                    "id_colonnina": self.id,
                    "presa_index": self.presa_index,         # Identifica la presa specifica
                    "numero_pdr": self.numero_pdr,           # Prese totali della stazione
                    "nome_colonnina": self.nome_colonnina,
                    "id_nil": self.nil_id,
                    "nome_nil": self.nil_nome,
                    "tipo_evento": "IDLE",
                    "timestamp_inizio": self.session_start,
                    "timestamp_fine": current_time,
                    "energia_kwh": 0,
                    "ricavo_euro": round(self.session_revenue, 2)
                }
                self.state = StationState.AVAILABLE
                
        return log_entry

class AnnualSimulationEngine:
    def __init__(self):
        logging.info("🔌 Connessione a MongoDB e Setup Iniziale...")
        self.client = database.get_db_client()
        self.db = self.client[config.DB_NAME]
        
        self.eco_params = self.db['simulation_parameters'].find_one({"scenario_id": "baseline_2025"})
        self.ev_catalog = list(self.db['ev_models_catalog'].find({}))
        self.ev_weights = [car['market_share_weight'] for car in self.ev_catalog]
        
        # Query corretta con Dot Notation sul campo 'details.titolare'
        stazioni_db = list(self.db['stations_registry'].find({
            "details.titolare": {"$regex": "A2A Energy Solutions", "$options": "i"}
        }))
        # Crea un ChargingPoint per ogni presa (numero_pdr) della stazione
        self.stations = []
        for doc in stazioni_db:
            n_pdr = doc.get('numero_pdr', 1)
            for i in range(n_pdr):
                self.stations.append(ChargingPoint(doc, self.eco_params, presa_index=i))
        
        logging.info(f"✅ Setup completato. Caricate in memoria {len(self.stations)} colonnine A2A sparse su tutta Milano.")
        
        self.logs_buffer = [] 
        self.BATCH_SIZE = 5000 
        self.db['charging_sessions_log'].drop()

    def get_time_multiplier(self, hour):
        if 0 <= hour < 6:
            return 0.1
        if 7 <= hour <= 10:
            return 1.5
        if 17 <= hour <= 20:
            return 1.8
        return 1.0

    def get_weather_multiplier(self, month):
        if month in [12, 1, 2]:
            return 1.25
        if month in [6, 7, 8]:
            return 1.10
        return 1.0

    def run_full_year(self):
        tick_minutes = 15
        start_time = datetime(2025, 1, 1, 0, 0)
        end_time = datetime(2025, 12, 31, 23, 59)
        current_time = start_time
        
        total_ticks = int((end_time - start_time).total_seconds() / 60 / tick_minutes)
        current_tick = 0
        
        logging.info(f"📅 Avvio Motore. Simulazione dal {start_time.date()} al {end_time.date()}...")
        
        while current_time < end_time:
            current_time += timedelta(minutes=tick_minutes)
            current_tick += 1
            
            if current_time.day == 1 and current_time.hour == 0 and current_time.minute == 0:
                logging.info(f"⏳ Simulazione in corso... Mese raggiunto: {current_time.strftime('%B %Y')} (Completato {int((current_tick/total_ticks)*100)}%)")
            
            molt_orario = self.get_time_multiplier(current_time.hour)
            molt_meteo = self.get_weather_multiplier(current_time.month)
            
            for station in self.stations:
                finito_log = station.update_tick(current_time, tick_minutes)
                
                if finito_log:
                    self.logs_buffer.append(finito_log)
                    if len(self.logs_buffer) >= self.BATCH_SIZE:
                        self.flush_logs()
                
                if station.state == StationState.AVAILABLE:
                    probabilita_finale = station.prob_base * molt_orario * molt_meteo
                    
                    if random.random() < probabilita_finale:
                        auto_scelta = random.choices(self.ev_catalog, weights=self.ev_weights, k=1)[0]
                        if station.is_dc and auto_scelta['charging_specs']['max_dc_kw'] == 0:
                            continue
                        
                        station.start_charging(auto_scelta, current_time)

        if self.logs_buffer:
            self.flush_logs()
            
        logging.info("✅ Simulazione Completata con successo per tutta Milano.")
        self.client.close()

    def flush_logs(self):
        if self.logs_buffer:
            self.db['charging_sessions_log'].insert_many(self.logs_buffer)
            logging.info(f"💾 Salvato blocco di {len(self.logs_buffer)} eventi nel database...")
            self.logs_buffer = []

if __name__ == "__main__":
    motore = AnnualSimulationEngine()
    motore.run_full_year()