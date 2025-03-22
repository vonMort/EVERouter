import json
import heapq
import logging

ONLY_HIGHSEC = True

def build_graph(universe_data):
    graph = {}
    security = {}
    name_to_id = {}
    id_to_name = {}

    print("🔧 Baue Graph auf Basis von 'connections'...")

    for region in universe_data.values():
        for constellation in region["constellations"].values():
            for sys_name, sys_data in constellation["systems"].items():
                sys_id = sys_data.get("solarSystemID")
                sys_name_lc = sys_name.lower()

                name_to_id[sys_name_lc] = sys_id
                id_to_name[sys_id] = sys_name
                security[sys_id] = sys_data.get("security", 0.0)

                graph.setdefault(sys_id, set())

                for neighbor_id in sys_data.get("connections", []):
                    graph[sys_id].add(neighbor_id)

    print(f"✅ {len(name_to_id)} Systeme verarbeitet.")
    return graph, security, name_to_id, id_to_name



def find_shortest_path(universe_data, start_name, end_name, only_highsec=True):
    print(f"🚀 Suche Route von '{start_name}' nach '{end_name}' (nur Highsec: {only_highsec})")

    graph, security, name_to_id, id_to_name = build_graph(universe_data)

    start_id = name_to_id.get(start_name.lower())
    end_id = name_to_id.get(end_name.lower())

    if start_id is None:
        print(f"❌ Startsystem '{start_name}' nicht gefunden.")
        return []
    if end_id is None:
        print(f"❌ Zielsystem '{end_name}' nicht gefunden.")
        return []

    visited = set()
    heap = [(0, start_id, [])]  # (cost, current_node, path)

    while heap:
        cost, current, path = heapq.heappop(heap)

        if current in visited:
            continue
        visited.add(current)

        path = path + [current]

        if current == end_id:
            print(f"✅ Route gefunden mit {len(path)-1} Sprüngen.")
            return [id_to_name.get(pid, str(pid)) for pid in path]

        for neighbor in graph.get(current, []):
            if neighbor in visited:
                continue
            sec = security.get(neighbor, 0.0)
            if only_highsec and sec < 0.5:
                print(f"⛔ System {id_to_name.get(neighbor, neighbor)} hat Sicherheitsstatus {sec:.1f} < 0.5 – übersprungen")
                continue
            heapq.heappush(heap, (cost + 1, neighbor, path))

    print("⚠️ Keine Route gefunden.")
    return []

def get_route_between(universe_path, start_system, end_system, only_highsec=True):
    try:
        with open(universe_path, "r", encoding="utf-8") as f:
            universe = json.load(f)
    except Exception as e:
        print(f"❌ Fehler beim Laden der Universe-Datei: {e}")
        return []

    return find_shortest_path(universe, start_system, end_system, only_highsec=only_highsec)
