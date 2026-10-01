#!/usr/bin/env python3
"""
Конвертация Shapefiles (.shp) → GeoJSON для карты.

ВАЖНО: автоматически перепроецирует в WGS84 (EPSG:4326),
потому что Leaflet понимает только широту/долготу.
Казахстанские шейпы часто в Pulkovo 1942 / UTM — без
перепроецирования полигоны не появятся на карте.
"""

import os
import json
from pathlib import Path

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SHAPEFILE_DIR = os.path.join(BASE_DIR, 'shapefiles')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')


def convert_one(shp_path):
    import geopandas as gpd

    name = Path(shp_path).stem
    print(f'📂 {Path(shp_path).name}')

    gdf = gpd.read_file(shp_path)
    print(f'   Объектов: {len(gdf)}')
    print(f'   Геометрия: {gdf.geom_type.value_counts().to_dict()}')

    # --- Проекция ---
    if gdf.crs is None:
        print('   ⚠️  CRS не задан в файле (.prj отсутствует)')
        print('      Предполагаю WGS84. Если полигоны не на месте —')
        print('      задайте CRS вручную, напр.: gdf.set_crs(epsg=32642)')
        gdf = gdf.set_crs(epsg=4326, allow_override=True)
    else:
        print(f'   CRS: {gdf.crs.name if hasattr(gdf.crs, "name") else gdf.crs}')
        if gdf.crs.to_epsg() != 4326:
            print('   🔄 Перепроецирую → WGS84 (EPSG:4326)')
            gdf = gdf.to_crs(epsg=4326)

    # --- Упрощение для веба (если очень много точек) ---
    try:
        total_pts = sum(len(g.exterior.coords) if g.geom_type == 'Polygon' else 0
                        for g in gdf.geometry if g is not None)
        if total_pts > 50000:
            print(f'   ✂️  Упрощаю геометрию ({total_pts} точек → для скорости)')
            gdf['geometry'] = gdf.geometry.simplify(0.001, preserve_topology=True)
    except Exception:
        pass

    # --- Сохранение ---
    out_path = os.path.join(OUTPUT_DIR, f'{name}.geojson')
    geojson = json.loads(gdf.to_json())

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False)

    size_kb = os.path.getsize(out_path) / 1024
    print(f'   ✅ {name}.geojson ({size_kb:.0f} KB)')

    # Показываем поля атрибутов — пригодится для подписей
    cols = [c for c in gdf.columns if c != 'geometry']
    if cols:
        print(f'   Поля: {", ".join(cols[:10])}')
        first = gdf.iloc[0]
        for c in cols[:3]:
            print(f'      {c} = {first[c]}')

    # Границы — проверка, что координаты разумные
    b = gdf.total_bounds  # minx, miny, maxx, maxy
    print(f'   Охват: {b[1]:.2f}–{b[3]:.2f}°N, {b[0]:.2f}–{b[2]:.2f}°E')
    if not (35 < b[1] < 60 and 50 < b[0] < 85):
        print('   ⚠️  Координаты вне Средней Азии — проверьте проекцию!')

    return out_path


def main():
    print('=' * 60)
    print('🗺️  КОНВЕРТАЦИЯ SHAPEFILES → GeoJSON')
    print('=' * 60 + '\n')

    os.makedirs(SHAPEFILE_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    try:
        import geopandas  # noqa
    except ImportError:
        print('❌ geopandas не установлен.')
        print('   Установите:  pip install geopandas')
        print('   (или запустите run.sh / run.bat — установит само)\n')
        return

    shp_files = sorted(Path(SHAPEFILE_DIR).glob('*.shp'))

    if not shp_files:
        print(f'⚠️  Нет .shp файлов в {SHAPEFILE_DIR}\n')
        print('   Положите туда ВСЕ файлы шейпа вместе:')
        print('     zones.shp   ← геометрия')
        print('     zones.shx   ← индекс      (обязательно)')
        print('     zones.dbf   ← атрибуты    (обязательно)')
        print('     zones.prj   ← проекция    (очень желательно)')
        print('     zones.cpg   ← кодировка   (для русских названий)\n')
        return

    ok = 0
    for shp in shp_files:
        try:
            convert_one(str(shp))
            ok += 1
        except Exception as e:
            print(f'   ❌ Ошибка: {e}')
        print()

    print('=' * 60)
    print(f'✅ Конвертировано: {ok} из {len(shp_files)}')
    print('=' * 60 + '\n')


if __name__ == '__main__':
    main()
