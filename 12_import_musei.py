from neo4j import GraphDatabase
import database
import config
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class CustomPoiImporter:
    def __init__(self):
        self.driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
        self.mongo_client = database.get_db_client()
        self.mongo_db = self.mongo_client[config.DB_NAME]

    def close(self):
        self.driver.close()
        self.mongo_client.close()

    def importa_collezione_geojson(self, nome_collezione, tipo_poi, campo_nome, raggio_max_mt=1000):
        # 1. Recuperiamo il documento unico da MongoDB
        documento_geojson = self.mongo_db[nome_collezione].find_one({})
        
        if not documento_geojson or 'features' not in documento_geojson:
            logging.error(f"❌ Nessun array 'features' trovato nella collezione {nome_collezione}.")
            return

        features = documento_geojson['features']
        logging.info(f"📥 Trovati {len(features)} {tipo_poi} in MongoDB. Avvio importazione su Neo4j...")

        cypher_query = """
        // Crea o aggiorna il POI
        MERGE (p:POI {nome: $nome})
        ON CREATE SET p.tipo = $tipo, p.location = point({longitude: $lon, latitude: $lat})
        
        WITH p
        // Trova tutte le colonnine
        MATCH (c:Colonnina)
        
        // Calcola la distanza
        WITH p, c, point.distance(c.location, p.location) AS dist_metri
        
        // Filtra entro il raggio massimo desiderato (es. 1000 metri)
        WHERE dist_metri <= $raggio_max
        
        // Crea la relazione salvando la distanza
        MERGE (c)-[r:VICINA_A]->(p)
        SET r.distanza_mt = round(dist_metri)
        """

        with self.driver.session() as session:
            for feature in features:
                props = feature.get('properties', {})
                geom = feature.get('geometry', {})
                coords = geom.get('coordinates', [0, 0])
                
                # Estraiamo il nome dinamicamente in base a come si chiama nella tua collection
                nome_entita = props.get(campo_nome, f'{tipo_poi} Sconosciuto')
                
                session.run(cypher_query,
                    nome=nome_entita,
                    tipo=tipo_poi,
                    lon=coords[0],
                    lat=coords[1],
                    raggio_max=raggio_max_mt
                )
        logging.info(f"✅ Importazione di {tipo_poi} completata con successo!")

if __name__ == "__main__":
    importer = CustomPoiImporter()
    try:
        # --- ESECUZIONE PER I MUSEI ---
        # Dallo screenshot, il campo col nome si chiama "nome museo"
        importer.importa_collezione_geojson(
            nome_collezione="musei", 
            tipo_poi="Museo", 
            campo_nome="nome museo", 
            raggio_max_mt=500 # I musei sono rari, cerchiamo colonnine fino a 500
        )
        
        # --- ESECUZIONE PER I SUPERMERCATI ---
        # Decommenta le righe sotto e metti il nome del campo corretto per i supermercati
        # importer.importa_collezione_geojson(
        #     nome_collezione="media_grande_distrib", 
        #     tipo_poi="Supermercato", 
        #     campo_nome="INSERISCI_IL_CAMPO_NOME_DELLA_GDO", 
        #     raggio_max_mt=500 # Per la spesa si cammina meno, massimo 500mt
        # )
        
    finally:
        importer.close()