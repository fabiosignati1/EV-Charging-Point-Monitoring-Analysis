from neo4j import GraphDatabase
import database
import config
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class TransactionsImporter:
    def __init__(self):
        self.driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
        self.mongo_client = database.get_db_client()
        self.mongo_db = self.mongo_client[config.DB_NAME]

    def close(self):
        self.driver.close()
        self.mongo_client.close()

    def importa_eventi_simulazione(self, batch_size=10000):
        # Usiamo un cursore per NON caricare tutti gli 894.000 eventi in RAM (evitiamo il crash del PC)
        cursor = self.mongo_db['charging_sessions_log'].find({})
        
        logging.info(f"💸 Inizio estrazione eventi da MongoDB. Elaborazione in streaming a blocchi di {batch_size}...")

        # Query Cypher batch con UNWIND
        cypher_batch = """
        UNWIND $batch AS row

        // 1. Trova la colonnina
        MATCH (c:Colonnina {id_colonnina: row.id_colonnina})

        // 2. Crea l'Evento
        CREATE (e:Evento {
            id_mongo: row.id_mongo,
            tipo: row.tipo_evento,
            inizio: row.inizio,
            fine: row.fine,
            energia_kwh: row.kwh,
            ricavo_euro: row.euro,
            presa_index: row.presa_index,
            numero_pdr: row.numero_pdr,
            nome_colonnina: row.nome_colonnina,
            id_nil: row.id_nil,
            nome_nil: row.nome_nil
        })
        CREATE (c)-[:HA_REGISTRATO]->(e)

        // 3. SE esiste il modello auto, crea il nodo ModelloAuto e collegalo
        FOREACH (ignoreMe IN CASE WHEN row.modello_auto IS NOT NULL THEN [1] ELSE [] END |
            MERGE (m:ModelloAuto {nome: row.modello_auto})
            CREATE (m)-[:COINVOLTO_IN]->(e)
        )
        """

        records = []
        batch_counter = 0

        with self.driver.session() as session:
            for log in cursor:
                ts_inizio = log.get('timestamp_inizio', {})
                inizio_str = ts_inizio.get('$date') if isinstance(ts_inizio, dict) else str(ts_inizio)

                ts_fine = log.get('timestamp_fine', {})
                fine_str = ts_fine.get('$date') if isinstance(ts_fine, dict) else str(ts_fine)

                records.append({
                    "id_colonnina": log.get('id_colonnina', ''),
                    "id_mongo": str(log.get('_id')),
                    "tipo_evento": log.get('tipo_evento', 'SCONOSCIUTO'),
                    "inizio": inizio_str,
                    "fine": fine_str,
                    "kwh": float(log.get('energia_kwh', 0.0)),
                    "euro": float(log.get('ricavo_euro', 0.0)),
                    "modello_auto": log.get('modello_auto'),
                    "presa_index": log.get('presa_index', 0),
                    "numero_pdr": log.get('numero_pdr', 1),
                    "nome_colonnina": log.get('nome_colonnina', ''),
                    "id_nil": log.get('id_nil'),
                    "nome_nil": log.get('nome_nil', '')
                })

                if len(records) >= batch_size:
                    session.run(cypher_batch, batch=records)
                    batch_counter += 1
                    logging.info(f"  ✔ Inseriti {batch_counter * batch_size} eventi in Neo4j...")
                    records = [] # Svuota la RAM
            
            # Inserisce gli eventuali resti
            if records:
                session.run(cypher_batch, batch=records)
                logging.info(f"  ✔ Inseriti gli ultimi {len(records)} eventi.")

        logging.info("✅ EVENTI E VEICOLI IMPORTATI CON SUCCESSO!")

if __name__ == "__main__":
    importer = TransactionsImporter()
    try:
        importer.importa_eventi_simulazione()
    finally:
        importer.close()