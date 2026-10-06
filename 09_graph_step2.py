from neo4j import GraphDatabase
import database
import config
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class GraphStepTwo:
    def __init__(self):
        self.driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
        self.mongo_client = database.get_db_client()
        self.mongo_db = self.mongo_client[config.DB_NAME]

    def close(self):
        self.driver.close()
        self.mongo_client.close()

    def arricchisci_con_proprieta(self):
        stazioni_mongo = list(self.mongo_db['stations_registry'].find({}))
        
        # Query Cypher aggiornata per il Passo 2
        cypher_query = """
        // 1. Recupera o crea la Colonnina (identificata dal suo ID)
        MERGE (c:Colonnina {id_colonnina: $id_colonnina})
        
        // 2. NUOVO: Crea o aggiorna il Nodo Titolare (Azienda)
        MERGE (t:Titolare {nome: $titolare})
        
        // 3. NUOVO: Crea la relazione di proprietà aziendale
        MERGE (c)-[:PROPRIETÀ_DI]->(t)
        """
        
        with self.driver.session() as session:
            logging.info(f"🏢 Ingestione in corso: collegamento colonnine ai rispettivi Titolari...")
            for s in stazioni_mongo:
                session.run(cypher_query,
                    id_colonnina=str(s.get('_id')),
                    titolare=s.get('details', {}).get('titolare', 'Sconosciuto')
                )
            logging.info("✅ PASSO 2 COMPLETATO: Mappatura della proprietà degli asset conclusa.")

if __name__ == "__main__":
    passo2 = GraphStepTwo()
    try:
        passo2.arricchisci_con_proprieta()
    finally:
        passo2.close()