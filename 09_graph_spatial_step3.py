from neo4j import GraphDatabase
import database
import config
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class GraphSpatialUpgrade:
    def __init__(self):
        self.driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
        self.mongo_client = database.get_db_client()
        self.mongo_db = self.mongo_client[config.DB_NAME]

    def close(self):
        self.driver.close()
        self.mongo_client.close()

    def aggiorna_distanze_spaziali(self):
        stazioni_mongo = list(self.mongo_db['stations_registry'].find({}))
        
        # Query Cypher con funzioni Spaziali Native
        cypher_query = """
        // 1. Trova i nodi già esistenti
        MATCH (c:Colonnina {id_colonnina: $id_colonnina})
        MATCH (q:Quartiere {id_nil: $id_nil})
        
        // 2. Imposta le coordinate come oggetti 'Point' nativi di Neo4j
        SET c.location = point({longitude: $lon_c, latitude: $lat_c})
        SET q.centroide = point({longitude: $lon_q, latitude: $lat_q})
        
        // 3. Trova la relazione che li unisce e calcola la distanza in metri
        MATCH (c)-[r:POSIZIONATA_IN]->(q)
        SET r.distanza_dal_centro_mt = round(point.distance(c.location, q.centroide))
        """
        
        with self.driver.session() as session:
            logging.info("🌍 Upgrade Spaziale in corso: calcolo delle distanze in metri...")
            for s in stazioni_mongo:
                # Estrazione sicura delle coordinate da MongoDB
                coords_c = s.get('location', {}).get('coordinates', [0, 0])
                coords_q = s.get('centroide_nil', {}).get('coordinates', [0, 0])
                
                # Evitiamo di calcolare se le coordinate sono assenti (0,0)
                if coords_c != [0, 0] and coords_q != [0, 0]:
                    session.run(cypher_query,
                        id_colonnina=str(s.get('_id')),
                        id_nil=s.get('id_nil', 0),
                        lon_c=coords_c[0], lat_c=coords_c[1],
                        lon_q=coords_q[0], lat_q=coords_q[1]
                    )
            logging.info("✅ UPGRADE COMPLETATO: Distanze aggiunte agli archi [:POSIZIONATA_IN].")

if __name__ == "__main__":
    spaziale = GraphSpatialUpgrade()
    try:
        spaziale.aggiorna_distanze_spaziali()
    finally:
        spaziale.close()