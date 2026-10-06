from neo4j import GraphDatabase
import database
import config
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class GraphStepOne:
    def __init__(self):
        self.driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
        self.mongo_client = database.get_db_client()
        self.mongo_db = self.mongo_client[config.DB_NAME]

    def close(self):
        self.driver.close()
        self.mongo_client.close()

    def carica_infrastruttura_e_quartieri(self):
        # Estraiamo i dati grezzi da MongoDB
        stazioni_mongo = list(self.mongo_db['stations_registry'].find({}))
        
        # Query Cypher per creare i nodi e la prima relazione
        cypher_query = """
        // 1. Crea o aggiorna il Nodo Quartiere
        MERGE (q:Quartiere {id_nil: $id_nil})
        ON CREATE SET q.nome_nil = $nome_nil, q.densita = $densita
        
        // 2. Crea o aggiorna il Nodo Colonnina
        MERGE (c:Colonnina {id_colonnina: $id_colonnina})
        SET c.indirizzo = $indirizzo, c.tecnologia = $corrente, c.operatore = $operatore,
            c.numero_col = $numero_col, c.numero_pdr = $numero_pdr
        
        // 3. Crea la prima relazione spaziale
        MERGE (c)-[:POSIZIONATA_IN]->(q)
        """
        
        with self.driver.session() as session:
            logging.info(f"🌐 Ingestione in corso: creazione nodi e relazioni [:POSIZIONATA_IN]...")
            for s in stazioni_mongo:
                session.run(cypher_query,
                    id_nil=s.get('id_nil', 0),
                    nome_nil=s.get('nome_nil', 'Quartiere Sconosciuto'),
                    densita=s.get('densita_ab_km2', 0),
                    id_colonnina=str(s.get('_id')),
                    indirizzo=s.get('details', {}).get('localita', 'Indirizzo Sconosciuto'),
                    corrente=s.get('tipo_corrente', 'AC'),
                    operatore=s.get('details', {}).get('titolare', 'Sconosciuto'),
                    numero_col=s.get('numero_col', 1),
                    numero_pdr=s.get('numero_pdr', 1)
                )
            logging.info("✅ PASSO 1 COMPLETATO: Nodi strutturali e relazioni geografiche inseriti.")

if __name__ == "__main__":
    passo1 = GraphStepOne()
    try:
        passo1.carica_infrastruttura_e_quartieri()
    finally:
        passo1.close()