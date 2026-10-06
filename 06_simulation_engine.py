import random
import logging
import pandas as pd
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(message)s')

# --- 1. VARIABILI DI SIMULAZIONE (ASSUNZIONI) ---
# Queste sono le leve che guidano il motore stocastico
SIM_VARS = {
    "prob_arrivo_15min": 0.12,  # 12% di chance che arrivi un'auto ogni quarto d'ora
    "prob_sosta_abusiva": 0.30, # 30% di chance che l'utente non sposti l'auto a fine carica
    "tariffa_kwh": 0.65,        # €/kWh per la ricarica
    "tariffa_idle_min": 0.10    # €/minuto di penale sosta
}

# --- 2. MINI-CATALOGO EV ---
EV_CATALOG = [
    {"modello": "Tesla Model Y", "batt_kwh": 75.0, "max_kw": 11.0, "peso": 0.3},
    {"modello": "Fiat 500e", "batt_kwh": 37.3, "max_kw": 11.0, "peso": 0.3},
    {"modello": "Jeep Compass PHEV", "batt_kwh": 11.4, "max_kw": 7.4, "peso": 0.2},
    {"modello": "Smart EQ", "batt_kwh": 16.7, "max_kw": 22.0, "peso": 0.2}
]

class StationState:
    AVAILABLE = "AVAILABLE"
    CHARGING = "CHARGING"
    IDLE = "IDLE"

class ChargingPoint:
    def __init__(self, id_colonnina, max_power_kw):
        self.id = id_colonnina
        self.max_power_kw = max_power_kw
        self.state = StationState.AVAILABLE
        self.minutes_remaining = 0
        
        # Tracking sessione corrente
        self.session_start = None
        self.session_type = None
        self.current_car_name = "N/A"
        self.current_soc_start = 0
        self.session_kwh = 0.0
        self.session_revenue = 0.0
        
        self.history_log = []

    def update_tick(self, current_time, tick_minutes=15):
        if self.state == StationState.CHARGING:
            self.minutes_remaining -= tick_minutes
            
            # Recuperiamo la potenza max dell'auto dal nome (per simulare il collo di bottiglia)
            car_info = next(car for car in EV_CATALOG if car["modello"] == self.current_car_name)
            potenza_effettiva = min(self.max_power_kw, car_info["max_kw"])
            
            kwh_erogati = potenza_effettiva * (tick_minutes / 60)
            self.session_kwh += kwh_erogati
            self.session_revenue += kwh_erogati * SIM_VARS["tariffa_kwh"]
            
            if self.minutes_remaining <= 0:
                self._save_session_log(current_time)
                
                # Transizione in Idle o Libera?
                if random.random() < SIM_VARS["prob_sosta_abusiva"]: 
                    self.state = StationState.IDLE
                    self.session_type = StationState.IDLE
                    self.session_start = current_time
                    self.minutes_remaining = random.randint(15, 60)
                    self.session_kwh = 0.0
                    self.session_revenue = 0.0
                else:
                    self._reset_station()

        elif self.state == StationState.IDLE:
            self.minutes_remaining -= tick_minutes
            self.session_revenue += tick_minutes * SIM_VARS["tariffa_idle_min"]
            
            if self.minutes_remaining <= 0:
                self._save_session_log(current_time)
                self._reset_station()

    def start_charging(self, current_time, car_model, soc_start, duration_min):
        self.state = StationState.CHARGING
        self.session_type = StationState.CHARGING
        self.session_start = current_time
        self.current_car_name = car_model
        self.current_soc_start = soc_start
        self.minutes_remaining = duration_min
        self.session_kwh = 0.0
        self.session_revenue = 0.0

    def _reset_station(self):
        self.state = StationState.AVAILABLE
        self.current_car_name = "N/A"
        self.current_soc_start = 0

    def _save_session_log(self, current_time):
        self.history_log.append({
            "ID_Colonnina": self.id,
            "Tipo_Evento": self.session_type,
            "Inizio": self.session_start.strftime("%Y-%m-%d %H:%M"),
            "Fine": current_time.strftime("%Y-%m-%d %H:%M"),
            "Durata_Min": int((current_time - self.session_start).total_seconds() / 60),
            "Modello_Auto": self.current_car_name,
            "SOC_Iniziale_%": self.current_soc_start if self.session_type == "CHARGING" else "N/A",
            "Energia_kWh": round(self.session_kwh, 2),
            "Ricavo_Euro": round(self.session_revenue, 2),
            "Assunzione_Prob_Arrivo": SIM_VARS["prob_arrivo_15min"],
            "Assunzione_Prob_Idle": SIM_VARS["prob_sosta_abusiva"]
        })

def run_simulation(days=7, tick_minutes=15):
    colonnina = ChargingPoint(id_colonnina="MI-DUOMO-01", max_power_kw=22.0)
    current_time = datetime(2025, 1, 1, 8, 0)
    total_ticks = int((days * 24 * 60) / tick_minutes)
    
    modelli = [c["modello"] for c in EV_CATALOG]
    pesi = [c["peso"] for c in EV_CATALOG]
    
    logging.info("🚀 Avvio Simulazione ({days} giorni). Variabili attive:")
    for k, v in SIM_VARS.items():
        logging.info(f"   - {k}: {v}")
    
    for _ in range(total_ticks):
        current_time += timedelta(minutes=tick_minutes)
        colonnina.update_tick(current_time, tick_minutes)
        
        if colonnina.state == StationState.AVAILABLE:
            if random.random() < SIM_VARS["prob_arrivo_15min"]:
                # 1. Pesca l'auto
                auto_scelta = random.choices(modelli, weights=pesi, k=1)[0]
                car_info = next(c for c in EV_CATALOG if c["modello"] == auto_scelta)
                
                # 2. Calcola stato batteria e tempo necessario
                soc_iniziale = random.randint(10, 60) # Arriva col 10-60% di batteria
                soc_target = 90 # Carica fino al 90%
                kwh_necessari = car_info["batt_kwh"] * ((soc_target - soc_iniziale) / 100)
                
                potenza_effettiva = min(colonnina.max_power_kw, car_info["max_kw"])
                durata_ore = kwh_necessari / potenza_effettiva
                durata_minuti = int(durata_ore * 60)
                
                colonnina.start_charging(current_time, auto_scelta, soc_iniziale, durata_minuti)

    # --- EXPORT E ANALISI ---
    if len(colonnina.history_log) > 0:
        df = pd.DataFrame(colonnina.history_log)
        df.to_csv("report_avanzato_DUOMO.csv", index=False, sep=";")
        
        # Mostriamo il conteggio delle macchine selezionate!
        conteggio_auto = df[df['Tipo_Evento'] == 'CHARGING']['Modello_Auto'].value_counts()
        
        logging.info("\n📊 --- ANALISI PARCO AUTO SIMULATO ---")
        logging.info("Quante e quali auto si sono fermate a ricaricare?")
        for auto, conteggio in conteggio_auto.items():
            logging.info(f"   - {auto}: {conteggio} sessioni")
            
        logging.info(f"\n✅ Report salvato. Contiene {len(df)} eventi, incluse le variabili di simulazione in ogni riga.")

if __name__ == "__main__":
    run_simulation(days=7)