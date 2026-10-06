from neo4j import GraphDatabase
import database
import config
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class SupermercatiImporter:
    def __init__(self):
        self.driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
        self.mongo_client = database.get_db_client()
        self.mongo_db = self.mongo_client[config.DB_NAME]

    def close(self):
        self.driver.close()
        self.mongo_client.close()

    def importa_supermercati(self):
        documento = self.mongo_db['media_grande_distrib'].find_one({})
        
        if not documento or 'features' not in documento:
            logging.error("❌ Collezione non trovata o formato errato.")
            return

        features = documento['features']
        logging.info(f"📥 Trovate {len(features)} strutture GDO in MongoDB. Avvio importazione...")

        cypher_query = """
        // 1. Crea il nodo del Supermercato (GDO)
        MERGE (p:POI {id_struttura: $codice})
        SET 
            p.nome = $nome, 
            p.tipo = "Supermercato",
            p.settore = $settore,
            p.indirizzo = $indirizzo,
            p.location = point({longitude: $lon, latitude: $lat})
        
        WITH p
        // 2. Trova le colonnine
        MATCH (c:Colonnina)
        
        // 3. Calcola la distanza
        WITH p, c, point.distance(c.location, p.location) AS dist_metri
        
        // 4. IMPONIAMO IL RAGGIO A 500 METRI
        WHERE dist_metri <= 500
        
        // 5. Crea la relazione
        MERGE (c)-[r:VICINA_A]->(p)
        SET r.distanza_mt = round(dist_metri)
        """

        
        with self.driver.session() as session:
            for feature in features:
                props = feature.get('properties', {})
                geom = feature.get('geometry')
                
                # Se la geometria è null o non ha le coordinate, saltiamo questo record
                if not geom or not geom.get('coordinates'):
                    continue
                    
                coords = geom.get('coordinates')
                
                # GESTIONE DEI CAMPI NULLI VISTI NELLO SCREENSHOT
                insegna = props.get('insegna')
                ubicazione = props.get('Ubicazione', 'Indirizzo Sconosciuto')
                
                # Se l'insegna è null, usiamo "GDO - Via..." come nome nel grafo
                nome_struttura = insegna if insegna else f"GDO - {ubicazione}"
                
                codice = props.get('Codice', str(coords[0]))
                settore = str(props.get('settore_merceologico', 'Sconosciuto')).lower()

                # --- FILTRO SUPERMERCATI REALI ---
                # Importiamo solo se vende alimentari. 
                # Scartiamo mobili (solo 'non alimentare'), farmacie, e benzinai.
                if 'alimentare' not in settore or settore == 'non alimentare':
                    continue

                session.run(cypher_query,
                    codice=codice,
                    nome=nome_struttura,
                    settore=settore.title(),
                    indirizzo=ubicazione,
                    lon=coords[0],
                    lat=coords[1]
                )
                
        logging.info("✅ Supermercati importati e collegati alle colonnine (raggio 500m) con successo!")

if __name__ == "__main__":
    importer = SupermercatiImporter()
    try:
        importer.importa_supermercati()
    finally:
        importer.close()