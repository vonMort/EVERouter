import yaml
import json
import os
from tqdm import tqdm

SDE_BASE_PATH = "../eve_metadata/sde/bsd/staStations.yaml"


def generate_station_cache():
    print("\n🚀 Starte Verarbeitung der Stationsdaten...")

    if not os.path.exists(SDE_BASE_PATH):
        print(f"❌ Datei nicht gefunden: {SDE_BASE_PATH}")
        return

    with open(SDE_BASE_PATH, "r", encoding="utf-8") as file:
        stations_raw = yaml.safe_load(file)

    station_cache = {"by_id": {}, "by_name": {}}

    print(f"📦 Verarbeite {len(stations_raw)} Stationen...")
    for station in tqdm(stations_raw):
        station_id = station.get("stationID")
        station_name = station.get("stationName", "").strip()
        system_id = station.get("solarSystemID")
        region_id = station.get("regionID")
        constellation_id = station.get("constellationID")

        entry = {
            "name": station_name,
            "solarSystemID": system_id,
            "regionID": region_id,
            "constellationID": constellation_id,
            "security": station.get("security"),
            "reprocessingEfficiency": station.get("reprocessingEfficiency"),
            "reprocessingStationsTake": station.get("reprocessingStationsTake"),
            "operationID": station.get("operationID"),
            "typeID": station.get("stationTypeID")
        }

        station_cache["by_id"][str(station_id)] = entry
        station_cache["by_name"][station_name.strip().lower()] = station_id

    with open("../cache/station_cache.json", "w", encoding="utf-8") as f:
        json.dump(station_cache, f, indent=2, ensure_ascii=False)

    print("✅ Stationen erfolgreich verarbeitet und gespeichert in station_cache.json")


if __name__ == "__main__":
    generate_station_cache()
