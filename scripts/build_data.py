#!/usr/bin/env python3
"""
ГЛАВНЫЙ СКРИПТ: собирает всё в output/weap-data.js для карты.

Читает:
  output/*.geojson        ← от convert_shapefiles.py (участки)
  output/kml_extracted.json ← от parse_kml.py (точки и линии)
  output/timeseries.json  ← от parse_timeseries.py (данные по годам/месяцам)
"""

import os
import json
import glob
from pathlib import Path
from datetime import datetime

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')


def load_geojson_files():
    zones = {}
    files = sorted(glob.glob(os.path.join(OUTPUT_DIR, '*.geojson')))
    print(f'📂 GeoJSON (участки): {len(files)}')
    for gj in files:
        name = Path(gj).stem
        try:
            with open(gj, 'r', encoding='utf-8') as f:
                data = json.load(f)
            zones[name] = data
            print(f'   ✓ {name}: {len(data.get("features", []))} объектов')
        except Exception as e:
            print(f'   ✗ {name}: {e}')
    return zones


def load_json(fname, title):
    path = os.path.join(OUTPUT_DIR, fname)
    if not os.path.exists(path):
        print(f'\n⚠️  {title}: нет файла {fname}')
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f'\n❌ {title}: {e}')
        return {}


def main():
    print('=' * 60)
    print('🔧 СБОРКА ДАННЫХ ДЛЯ КАРТЫ')
    print('=' * 60 + '\n')

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    zones = load_geojson_files()

    kml = load_json('kml_extracted.json', 'Геометрия KML')
    if kml:
        print('\n📄 Геометрия из KML:')
        for k in sorted(kml):
            if kml[k]:
                print(f'   {k:22s} : {len(kml[k])}')

    ts = load_json('timeseries.json', 'Временные ряды')
    if ts:
        print('\n📊 Данные во времени:')
        for k, d in ts.items():
            print(f'   {k:24s} : {len(d.get("series", {})):4d} объектов'
                  f'  [{d.get("resolution")}]  {d.get("unit", "")}')

    payload = {
        'generated': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'zones': zones,
        'kml': kml,
        'data': ts,
    }

    out = os.path.join(OUTPUT_DIR, 'weap-data.js')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('// Сгенерировано build_data.py — не редактировать вручную\n')
        f.write('const WEAP_DATA = ')
        json.dump(payload, f, ensure_ascii=False)
        f.write(';\n')

    size = os.path.getsize(out) / 1024
    print('\n' + '=' * 60)
    print(f'✅ ГОТОВО — {out}  ({size:.0f} KB)')
    print('=' * 60)
    print('\nОткройте:  output/index.html\n')


if __name__ == '__main__':
    main()
