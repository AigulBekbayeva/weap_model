#!/usr/bin/env python3
"""
Парсинг KML/KMZ экспорта WEAP.

Читает СТРУКТУРУ ПАПОК KML (Demand Sites, Rivers, Diversions,
Streamflow Gauges, Reservoirs, Transmission Links, ...) — поэтому
ни один элемент не теряется, даже если имя нестандартное.

Всё, что не распознано, попадает в other_points / other_lines.
"""

import os
import re
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
KML_DIR = os.path.join(BASE_DIR, 'kml')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

# ---- Сопоставление имени папки WEAP → ключ в наших данных -------------
FOLDER_MAP = [
    # (ключевые слова в названии папки, ключ для точек, ключ для линий)
    (['demand site', 'demand'],            'demand_sites',       None),
    (['streamflow gauge', 'gauge'],        'gauges',             None),
    (['reservoir'],                        'reservoirs',         None),
    (['groundwater', 'ground water'],      'groundwater',        None),
    (['flow requirement', 'eflow',
      'instream', 'streamflow requirement'],'eflow_requirements', None),
    (['withdrawal', 'diversion outflow'],  'withdrawals',        None),
    (['wastewater', 'treatment'],          'wastewater',         None),
    (['catchment', 'headflow'],            'catchments',         None),
    (['river', 'reach'],                   None,                 'rivers'),
    (['diversion', 'canal', 'channel'],    'withdrawals',        'channels'),
    (['transmission link', 'transmission',
      'return flow', 'link'],              None,                 'transmission_links'),
    (['runoff', 'infiltration'],           None,                 'transmission_links'),
]

POINT_KEYS = ['demand_sites', 'gauges', 'reservoirs', 'groundwater',
              'eflow_requirements', 'withdrawals', 'wastewater',
              'catchments', 'other_points']
LINE_KEYS = ['rivers', 'channels', 'transmission_links', 'other_lines']


def strip_ns(tag):
    """Убирает namespace: '{http://...}Placemark' → 'Placemark'"""
    return tag.split('}')[-1] if '}' in tag else tag


def find_child(elem, name):
    for ch in elem:
        if strip_ns(ch.tag) == name:
            return ch
    return None


def find_all_deep(elem, name):
    out = []
    for ch in elem.iter():
        if strip_ns(ch.tag) == name:
            out.append(ch)
    return out


def classify_folder(folder_name):
    """Возвращает (point_key, line_key) по названию папки"""
    n = (folder_name or '').lower()
    for keywords, pkey, lkey in FOLDER_MAP:
        for kw in keywords:
            if kw in n:
                return pkey, lkey
    return None, None


def classify_by_name(name):
    """Запасной вариант: классификация по имени элемента"""
    n = (name or '').lower()
    if any(k in n for k in ['agricultur', 'domestic', 'industry', 'fish',
                            'landscape', 'nalivn', 'others', 'demand']):
        return 'demand_sites', None
    if 'gauge' in n or 'post' in n:
        return 'gauges', None
    if 'reservoir' in n or 'shardara' in n or 'vdhr' in n:
        return 'reservoirs', None
    if 'eflow' in n or 'flow req' in n or 'ecolog' in n or 'экост' in n:
        return 'eflow_requirements', None
    if 'groundwater' in n or 'gw_' in n or 'подзем' in n:
        return 'groundwater', None
    if 'withdraw' in n or 'забор' in n:
        return 'withdrawals', None
    if any(k in n for k in ['syrdarya', 'keles', 'arys', 'river', 'река']):
        return None, 'rivers'
    if any(k in n for k in ['dostyk', 'bkmk', 'kyzylkum', 'canal',
                            'channel', 'diversion', 'канал']):
        return None, 'channels'
    if 'link' in n or 'transmission' in n or 'return' in n:
        return None, 'transmission_links'
    return None, None


def parse_coords(text):
    """KML: 'lon,lat[,alt] lon,lat[,alt] ...' → [[lat,lon], ...] для Leaflet"""
    out = []
    if not text:
        return out
    for token in re.split(r'\s+', text.strip()):
        if not token:
            continue
        parts = token.split(',')
        if len(parts) >= 2:
            try:
                lon, lat = float(parts[0]), float(parts[1])
                out.append([round(lat, 6), round(lon, 6)])
            except ValueError:
                continue
    return out


def clean_description(text):
    """Убирает HTML-теги из описания"""
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:300]


def extract_kmz(kmz_path):
    """Распаковывает KMZ, возвращает список путей к .kml"""
    extract_dir = os.path.join(KML_DIR, '_extracted')
    os.makedirs(extract_dir, exist_ok=True)
    try:
        with zipfile.ZipFile(kmz_path, 'r') as z:
            z.extractall(extract_dir)
    except zipfile.BadZipFile:
        # Иногда KMZ на самом деле обычный KML с другим расширением
        print('   ⚠️  Не ZIP-архив — пробую читать как обычный KML…')
        try:
            with open(kmz_path, 'rb') as f:
                head = f.read(200).lstrip()
            if head.startswith(b'<?xml') or b'<kml' in head:
                return [kmz_path]
        except Exception:
            pass
        print('   ❌ Файл повреждён или не является KMZ/KML')
        return []
    return [str(p) for p in Path(extract_dir).glob('**/*.kml')]


def walk(elem, folder_path, results, stats):
    """Рекурсивно обходит Document/Folder/Placemark"""
    for child in elem:
        tag = strip_ns(child.tag)

        if tag in ('Document', 'Folder'):
            nm = find_child(child, 'name')
            fname = nm.text.strip() if (nm is not None and nm.text) else ''
            walk(child, folder_path + [fname] if fname else folder_path,
                 results, stats)

        elif tag == 'Placemark':
            handle_placemark(child, folder_path, results, stats)


def handle_placemark(pm, folder_path, results, stats):
    nm = find_child(pm, 'name')
    name = nm.text.strip() if (nm is not None and nm.text) else 'Unnamed'

    dsc = find_child(pm, 'description')
    description = clean_description(dsc.text if dsc is not None else '')

    folder = ' / '.join(folder_path) if folder_path else ''

    # Классификация: сначала по папке, затем по имени
    pkey, lkey = (None, None)
    for f in reversed(folder_path):          # ближайшая папка важнее
        pkey, lkey = classify_folder(f)
        if pkey or lkey:
            break
    if not pkey and not lkey:
        pkey, lkey = classify_by_name(name)

    # --- ТОЧКИ ---
    for pt in find_all_deep(pm, 'Point'):
        c = find_child(pt, 'coordinates')
        coords = parse_coords(c.text if c is not None else '')
        if coords:
            lat, lon = coords[0]
            results.setdefault(pkey or 'other_points', []).append({
                'name': name, 'lat': lat, 'lon': lon,
                'folder': folder, 'description': description
            })
            stats['points'] += 1

    # --- ЛИНИИ ---
    for ls in find_all_deep(pm, 'LineString'):
        c = find_child(ls, 'coordinates')
        coords = parse_coords(c.text if c is not None else '')
        if len(coords) >= 2:
            results.setdefault(lkey or 'other_lines', []).append({
                'name': name, 'coords': coords,
                'folder': folder, 'description': description
            })
            stats['lines'] += 1

    # --- ПОЛИГОНЫ (если есть прямо в KML) ---
    for poly in find_all_deep(pm, 'Polygon'):
        ring = None
        for ch in poly.iter():
            if strip_ns(ch.tag) == 'coordinates':
                ring = ch
                break
        coords = parse_coords(ring.text if ring is not None else '')
        if len(coords) >= 3:
            results.setdefault('polygons', []).append({
                'name': name, 'coords': coords,
                'folder': folder, 'description': description
            })
            stats['polygons'] += 1


def parse_kml_file(kml_path, results, stats):
    print(f'📄 Читаю: {os.path.basename(kml_path)}')
    try:
        tree = ET.parse(kml_path)
    except Exception as e:
        print(f'   ❌ Ошибка XML: {e}')
        return
    walk(tree.getroot(), [], results, stats)


def main():
    print('=' * 60)
    print('📦 ПАРСИНГ KML / KMZ (экспорт WEAP)')
    print('=' * 60 + '\n')

    os.makedirs(KML_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    files = sorted(Path(KML_DIR).glob('*.kmz')) + sorted(Path(KML_DIR).glob('*.kml'))
    if not files:
        print(f'⚠️  Нет файлов в {KML_DIR}')
        print('   Положите туда export.kmz (Экспорт из WEAP → Google Earth)\n')
        return

    results = {}
    stats = {'points': 0, 'lines': 0, 'polygons': 0}

    for f in files:
        if f.suffix.lower() == '.kmz':
            print(f'📦 KMZ: {f.name}')
            for kml in extract_kmz(str(f)):
                parse_kml_file(kml, results, stats)
        else:
            parse_kml_file(str(f), results, stats)
        print()

    # Гарантируем наличие всех ключей
    for k in POINT_KEYS + LINE_KEYS:
        results.setdefault(k, [])

    out = os.path.join(OUTPUT_DIR, 'kml_extracted.json')
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)

    print('=' * 60)
    print('📊 ИЗВЛЕЧЕНО:')
    print('=' * 60)
    for k in sorted(results.keys()):
        if results[k]:
            print(f'   {k:22s} : {len(results[k])}')
    print(f'\n   ИТОГО: {stats["points"]} точек, '
          f'{stats["lines"]} линий, {stats["polygons"]} полигонов')

    # Показываем, какие папки нашлись — чтобы проверить классификацию
    folders = {}
    for items in results.values():
        for it in items:
            f = it.get('folder', '')
            if f:
                folders[f] = folders.get(f, 0) + 1
    if folders:
        print('\n📁 Папки в KML:')
        for f, n in sorted(folders.items(), key=lambda x: -x[1]):
            print(f'   {n:4d}  {f}')

    print(f'\n✅ Сохранено: {out}\n')


if __name__ == '__main__':
    main()
