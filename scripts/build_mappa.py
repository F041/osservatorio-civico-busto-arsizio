"""Mappa della sezione Sicurezza: confine, vie e quadrati di Busto Arsizio, da OpenStreetMap.

Uso: python scripts/build_mappa.py data/mappa.json   (serve shapely; si rilancia solo se cambiano vie o griglia)

La mappa del sito è disegnata da questo file, senza tessere da server esterni: chi segnala non manda
a nessuno la zona che sta guardando. Le segnalazioni salvano solo il codice del quadrato (rRRcCC, riga
da sud e colonna da ovest), mai la via. La griglia deve coincidere con firestore.rules
e scripts/build_sicurezza.py.
Dati © OpenStreetMap contributors, licenza ODbL.
"""
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict

from shapely.geometry import LineString, MultiLineString, Point, box
from shapely.ops import linemerge, polygonize, unary_union

# Il server principale risponde spesso 502/504 sotto carico: si riprova, anche sul secondo server
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
AREA = 'area["boundary"="administrative"]["admin_level"="8"]["name"="Busto Arsizio"]->.a;'

# Griglia: quadrati di circa 250 x 250 m (a 45,6° di latitudine 0,0032° di longitudine sono 249 m)
LAT0, LON0 = 45.568, 8.804
DLAT, DLON = 0.00225, 0.0032
RIGHE, COLONNE = 34, 25

SCALA = 100000  # coordinate salvate come interi: (lat - LAT0) * SCALA, circa 1 m
SEMPLIFICA = 0.00003  # tolleranza di semplificazione delle linee, circa 3 m

# Rango di disegno: 0 strade principali, 1 secondarie, 2 di quartiere, 3 pedonali e sterrate
RANGO = {"motorway": 0, "trunk": 0, "trunk_link": 0, "primary": 0, "secondary": 0, "secondary_link": 0,
         "tertiary": 1, "tertiary_link": 1, "pedestrian": 3, "footway": 3, "path": 3, "track": 3}


def overpass(query):
    for tentativo in range(6):
        url = OVERPASS[tentativo % len(OVERPASS)]
        req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": query}).encode(),
                                     headers={"User-Agent": "osservatorio-civico-busto-arsizio"})
        try:
            return json.load(urllib.request.urlopen(req, timeout=300))["elements"]
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"Overpass {url}: {e}, riprovo")
            time.sleep(10)
    sys.exit("Overpass non risponde")


def cella(row, col):
    return f"r{row:02d}c{col:02d}"


def cella_box(row, col):
    return box(LON0 + col * DLON, LAT0 + row * DLAT, LON0 + (col + 1) * DLON, LAT0 + (row + 1) * DLAT)


def cella_di(lon, lat):
    row, col = math.floor((lat - LAT0) / DLAT), math.floor((lon - LON0) / DLON)
    return cella(row, col) if 0 <= row < RIGHE and 0 <= col < COLONNE else None


def flat(coords):
    """[(lon, lat), ...] -> [lat, lon, lat, lon, ...] interi relativi all'origine della griglia."""
    out = []
    for lon, lat in coords:
        out += [round((lat - LAT0) * SCALA), round((lon - LON0) * SCALA)]
    return out


def lines_of(geom):
    if geom.is_empty:
        return []
    return list(geom.geoms) if isinstance(geom, MultiLineString) else [geom]


def main(out_path):
    els = overpass(f"[out:json][timeout:180];{AREA}rel(pivot.a);out geom;"
                   '(way(area.a)["highway"]["name"];way(area.a)["place"="square"]["name"];);out geom;'
                   'way(area.a)["railway"="rail"];out geom;')
    luoghi_els = overpass(f"[out:json][timeout:180];{AREA}"
                          '(nwr(area.a)["railway"~"^(station|halt)$"]["name"];nwr(area.a)["leisure"="park"]["name"];'
                          'nwr(area.a)["amenity"="hospital"]["name"];nwr(area.a)["shop"="mall"]["name"];);out center;')

    rel = next(e for e in els if e["type"] == "relation")
    outer = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]]) for m in rel["members"]
             if m["type"] == "way" and m["role"] == "outer"]
    confine = max(polygonize(linemerge(outer)), key=lambda p: p.area)

    celle = [(r, c) for r in range(RIGHE) for c in range(COLONNE) if cella_box(r, c).intersects(confine)]
    valide = {cella(r, c) for r, c in celle}

    # Vie unite per nome: lo stesso nome può essere spezzato in molti tratti
    tratti, rango = defaultdict(list), {}
    ferrovie = []
    for w in els:
        if w["type"] != "way":
            continue
        line = LineString([(p["lon"], p["lat"]) for p in w["geometry"]])
        tags = w["tags"]
        if tags.get("railway") == "rail":
            ferrovie.append(line)
            continue
        name = tags["name"]
        tratti[name].append(line)
        rango[name] = min(rango.get(name, 2), RANGO.get(tags.get("highway"), 2))

    vie, lunghezze = [], defaultdict(dict)  # lunghezze[cella][via] = metri (circa) della via nel quadrato
    for name in sorted(tratti):
        geom = unary_union(tratti[name])
        if isinstance(geom, MultiLineString):
            geom = linemerge(geom)
        geom = geom.intersection(confine.buffer(0.0005))
        geom = geom.simplify(SEMPLIFICA)
        linee = [l for l in lines_of(geom) if l.length > 0]
        if not linee:
            continue
        sue = []
        for r, c in celle:
            pezzo = geom.intersection(cella_box(r, c))
            if not pezzo.is_empty:
                lunghezze[cella(r, c)][name] = pezzo.length * 111000
                sue.append(cella(r, c))
        if sue:
            vie.append({"n": name, "r": rango[name], "c": sue, "g": [flat(l.coords) for l in linee]})

    def vie_principali(id_cella, quante=3):
        dentro = sorted(((m, v) for v, m in lunghezze[id_cella].items()), reverse=True)
        return [v for _, v in dentro[:quante]]

    luoghi = []
    for e in luoghi_els:
        lat, lon = (e["lat"], e["lon"]) if e["type"] == "node" else (e["center"]["lat"], e["center"]["lon"])
        id_cella = cella_di(lon, lat)
        if id_cella in valide and confine.contains(Point(lon, lat)):
            luoghi.append({"n": e["tags"]["name"], "c": id_cella, "p": flat([(lon, lat)])})
    luoghi.sort(key=lambda l: l["n"])

    data = {
        "fonte": "© OpenStreetMap contributors (ODbL)",
        "griglia": {"lat0": LAT0, "lon0": LON0, "dlat": DLAT, "dlon": DLON, "righe": RIGHE, "colonne": COLONNE, "scala": SCALA},
        "confine": flat(confine.simplify(SEMPLIFICA).exterior.coords),
        # Per ogni quadrato le tre vie più lunghe al suo interno: servono a descriverlo a parole
        "celle": {cella(r, c): vie_principali(cella(r, c)) for r, c in celle},
        "vie": vie,
        "ferrovie": [flat(l.coords) for line in ferrovie for l in lines_of(line.intersection(confine).simplify(SEMPLIFICA))],
        "luoghi": luoghi,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Scritto {out_path}: {len(celle)} quadrati, {len(vie)} vie, {len(luoghi)} luoghi")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python scripts/build_mappa.py <output.json>")
    main(sys.argv[1])
