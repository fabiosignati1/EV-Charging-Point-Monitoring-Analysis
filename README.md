# EV-Monitoring and Profitability Analysis
### Monitoring EV charger station in Milan City

Questo progetto sviluppa una pipeline di Data Engineering finalizzata all'analisi dell'efficienza, dell'utilizzo e della redditività della rete di ricarica per veicoli elettrici (EV) nel Comune di Milano.

L'obiettivo principale è l'architettura di un sistema integrato per il monitoraggio continuo dello stato delle infrastrutture e il calcolo di metriche di rendimento a supporto delle decisioni d'investimento.

---

## Architettura del Sistema

Il sistema si articola nelle seguenti fasi operative:

1. **Censimento Geografico (Dati Statici):** Estrazione delle coordinate e delle specifiche tecniche dell'infrastruttura di ricarica tramite OpenStreetMap (Overpass API).
2. **Gemello Digitale (Dati Dinamici):** Simulazione stocastica e probabilistica dei flussi di traffico e delle variazioni di stato dei punti di ricarica (*Available*, *Charging*, *Out of Service*), modellata sulle fasce orarie e sui comportamenti di mobilità urbana, secondo "pesi probabilistici" decisi insieme al gruppo di lavoro.
3. **Data Ingestion e Persistence:** Memorizzazione ad alte prestazioni degli eventi all'interno di una collezione *Time Series* ottimizzata su MongoDB Atlas.
4. **Data Analytics:** Pipeline analitica per l'elaborazione dei tassi di occupazione medi, della stima dei consumi energetici e della valutazione economica generati dalla rete.

---

## Tecnologie Utilizzate

- **Linguaggio di programmazione:** Python (Pandas, Numpy, PyMongo, Requests, Python-dotenv)
- **Database:** MongoDB Atlas (Time Series Collections)
- **Sorgenti Dati:** OpenStreetMap API (Overpass QL)
- **Version Control:** Git / GitHub
