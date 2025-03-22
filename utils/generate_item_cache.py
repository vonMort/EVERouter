import yaml
import json
from tqdm import tqdm

TYPEIDS_PATH = "../eve_metadata/sde/fsd/types.yaml"

# <<< OPTIONAL: true = nur Marktitems, false = alle Typen
ONLY_PUBLISHED = True
LANGUAGE = "de"

def load_typeids(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_item_cache(typeids_data):
    by_id = {}
    by_name = {}

    keys = list(typeids_data.keys())
    print(f"🔎 Verarbeite {len(keys)} Items...")

    for type_id in tqdm(keys, desc="📦 Verarbeite Items"):
        item = typeids_data[type_id]

        if ONLY_PUBLISHED and not item.get("published", False):
            continue

        name = item.get("name", {}).get(LANGUAGE)
        volume = item.get("volume")

        if not name or volume is None:
            continue

        name_lc = name.strip().lower()

        by_id[type_id] = {
            "name": name_lc,
            "volume": volume
        }

        by_name[name_lc] = {
            "type_id": type_id,
            "volume": volume
        }

    return {
        "by_id": by_id,
        "by_name": by_name
    }


def save_to_json(data, filepath="../cache/item_cache.json"):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"💾 Itemdaten gespeichert in {filepath}")


if __name__ == "__main__":
    print("🚀 Starte Verarbeitung der Itemdaten...")
    typeids = load_typeids(TYPEIDS_PATH)
    item_cache = build_item_cache(typeids)
    save_to_json(item_cache)
    print("🎉 Alle Items erfolgreich verarbeitet und gespeichert!")