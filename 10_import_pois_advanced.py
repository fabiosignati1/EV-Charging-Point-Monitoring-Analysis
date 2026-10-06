import requests
import database
import config
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def estrai_e_salva_poi_multipli():
    logging.info("🌐 Connessione a OpenStreetMap (Overpass API)...")
    
    overpass_url = "https://overpass-api.de/api/interpreter"
    # Query pulita, senza commenti, per evitare errori di parsing sul server
    overpass_query = """
    [out:json][timeout:25];
    area["name"="Milano"]["admin_level"="8"]->.searchArea;
    (
      node["shop"="mall"](area.searchArea);
      way["shop"="mall"](area.searchArea);
      node["tourism"="museum"](area.searchArea);
      way["tourism"="museum"](area.searchArea);
    );
    out center;
    """
    
    try:
        response = requests.post(overpass_url, data={'data': overpass_query})
        
        # Se il server risponde con 200 (OK), processiamo i dati
        if response.status_code == 200:
            data = response.json()
            elements = data.get('elements', [])
            logging.info(f"📥 Ricevuti {len(elements)} nuovi Punti di Interesse da OpenStreetMap.")
            
            client = database.get_db_client()
            db = client[config.DB_NAME]
            poi_collection = db['points_of_interest']
            
            buffer_pois = []
            for el in elements:
                lat = el.get('lat') or el.get('center', {}).get('lat')
                lon = el.get('lon') or el.get('center', {}).get('lon')
                
                if not lat or not lon:
                    continue
                    
                tags = el.get('tags', {})
                
                if tags.get('shop') == 'mall':
                    tipo_poi = "Centro Commerciale"
                elif tags.get('tourism') == 'museum':
                    tipo_poi = "Museo"
                else:
                    tipo_poi = "Altro"
                
                poi_document = {
                    "osm_id": el.get('id'),
                    "nome": tags.get('name', f'{tipo_poi} Senza Nome'),
                    "brand": tags.get('brand', 'Indipendente'),
                    "tipo": tipo_poi,
                    "location": {
                        "type": "Point",
                        "coordinates": [float(lon), float(lat)]
                    }
                }
                buffer_pois.append(poi_document)
            
            if buffer_pois:
                poi_collection.insert_many(buffer_pois)
                logging.info(f"💾 Salvati con successo {len(buffer_pois)} nuovi POI su MongoDB.")
                totale = poi_collection.count_documents({})
                logging.info(f"📊 Totale Punti di Interesse attualmente nel database: {totale}")
            
            client.close()
            
        else:
            # Se il server ci dà errore (es. 429 Too Many Requests o 400 Bad Request)
            logging.error(f"❌ Errore dal server OpenStreetMap. Codice: {response.status_code}")
            logging.error(f"Messaggio del server: {response.text}")
            
    except Exception as e:
        logging.error(f"⚠️ Errore di connessione o esecuzione: {e}")

if __name__ == "__main__":
    estrai_e_salva_poi_multipli()