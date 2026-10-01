#!/usr/bin/env python3
"""
Парсинг CSV с временными рядами (входные данные и результаты WEAP).

Понимает ОБЕ ориентации таблицы — определяет автоматически:

  A) Объекты в строках, время в столбцах
     name,2020-01,2020-02,...
     AgricultureBKMK,1.2,1.3,...

  B) Время в строках, объекты в столбцах  ← так экспортирует WEAP
     Month,AgricultureBKMK,Domestic_BKMK
     2020-01,1.2,0.3

Понимает форматы дат: 2020 | 2020-01 | 01.2020 | Jan-2020 | Янв 2020 |
2020/1 | 2020 Jan | 1/2020 и т.п.

Тип данных определяется по ИМЕНИ ФАЙЛА (см. FILE_KINDS ниже).
"""

import os
import re
import csv
import json
import glob
from pathlib import Path

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
CSV_DIR = os.path.join(BASE_DIR, 'csv')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

# --- Тип данных по ключевым словам в имени файла -----------------------
# (ключевые слова, код, подпись, единица, к какому слою карты привязывать)
FILE_KINDS = [
    (['gauge_model', 'modeled', 'model_flow', 'смодел', 'модел'],
     'gauge_modeled', 'Смоделированный расход', 'м³/с', 'gauges'),
    (['gauge_obs', 'observed', 'факт', 'наблюд'],
     'gauge_observed', 'Наблюдённый расход', 'м³/с', 'gauges'),
    (['unmet', 'дефицит', 'неудовл'],
     'unmet_demand', 'Неудовлетворённый спрос', 'млн м³', 'demand_sites'),
    (['coverage', 'покрыт', 'обеспеч'],
     'coverage', 'Покрытие спроса', '%', 'demand_sites'),
    (['delivered', 'supply', 'подача'],
     'supply_delivered', 'Фактическая подача', 'млн м³', 'demand_sites'),
    (['consumption', 'demand', 'потребл', 'спрос'],
     'demand_consumption', 'Потребление', 'млн м³', 'demand_sites'),
    (['groundwater', 'подземн', 'gw_'],
     'groundwater_volume', 'Объём подземных вод', 'млн м³', 'groundwater'),
    (['reservoir_vol', 'storage', 'объем_вдхр', 'объём_вдхр'],
     'reservoir_volume', 'Объём водохранилища', 'млн м³', 'reservoirs'),
    (['reservoir_in', 'приток'],
     'reservoir_inflow', 'Приток в водохранилище', 'м³/с', 'reservoirs'),
    (['reservoir_out', 'сброс', 'release'],
     'reservoir_outflow', 'Сброс из водохранилища', 'м³/с', 'reservoirs'),
    (['evap', 'испарен'],
     'reservoir_evaporation', 'Испарение', 'млн м³', 'reservoirs'),
    (['eflow', 'экосток', 'ecolog', 'instream', 'flow_req'],
     'eflow_requirement', 'Требование экостока', 'м³/с', 'eflow_requirements'),
    (['headflow', 'river', 'реки', 'расход_рек'],
     'river_headflow', 'Расход реки (вход)', 'м³/с', 'rivers'),
    (['diversion', 'canal', 'отвод', 'канал'],
     'canal_diversion', 'Процент отвода', '%', 'channels'),
    (['link_flow', 'transmission'],
     'link_flow', 'Расход по связи', 'м³/с', 'transmission_links'),
]

MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'мая': 5, 'июн': 6,
    'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12,
}


def classify_file(filename):
    n = Path(filename).stem.lower()
    for keywords, code, label, unit, layer in FILE_KINDS:
        for kw in keywords:
            if kw in n:
                return code, label, unit, layer
    return Path(filename).stem, Path(filename).stem, '', None


def parse_time(s):
    """
    Разбирает метку времени → ('2020-01', 2020, 1) или ('2020', 2020, None).
    Возвращает None, если это не время.
    """
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None

    # Чистый год: 2020
    if re.fullmatch(r'(19|20)\d{2}(\.0)?', s):
        y = int(float(s))
        return (f'{y}', y, None)

    low = s.lower()

    # Название месяца + год: Jan-2020, Янв 2020, 2020 Jan, January 2020
    mmatch = None
    for name, num in MONTHS.items():
        if name in low:
            mmatch = num
            break
    if mmatch:
        ym = re.search(r'(19|20)\d{2}', s)
        if ym:
            y = int(ym.group(0))
            return (f'{y}-{mmatch:02d}', y, mmatch)
        return None

    # Числовые: 2020-01, 2020/1, 01.2020, 1/2020, 2020.01
    m = re.fullmatch(r'(19|20)(\d{2})[-/.](\d{1,2})', s)
    if m:
        y, mo = int(m.group(1) + m.group(2)), int(m.group(3))
        if 1 <= mo <= 12:
            return (f'{y}-{mo:02d}', y, mo)
        return None

    m = re.fullmatch(r'(\d{1,2})[-/.](19|20)(\d{2})', s)
    if m:
        mo, y = int(m.group(1)), int(m.group(2) + m.group(3))
        if 1 <= mo <= 12:
            return (f'{y}-{mo:02d}', y, mo)
        return None

    return None


def to_number(s):
    if s is None:
        return None
    s = str(s).strip().replace('\xa0', '').replace(' ', '')
    if not s or s.lower() in ('na', 'n/a', 'nan', '-', '—', 'null'):
        return None
    s = s.replace(',', '.')          # десятичная запятая
    try:
        return float(s)
    except ValueError:
        return None


def sniff_read(path):
    """Читает CSV с автоопределением разделителя и кодировки"""
    for enc in ('utf-8-sig', 'utf-8', 'cp1251'):
        try:
            with open(path, 'r', encoding=enc, newline='') as f:
                sample = f.read(8192)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
                    delim = dialect.delimiter
                except csv.Error:
                    delim = ';' if sample.count(';') > sample.count(',') else ','
                rows = [r for r in csv.reader(f, delimiter=delim) if any(
                    (c or '').strip() for c in r)]
            if rows:
                return rows, enc, delim
        except (UnicodeDecodeError, LookupError):
            continue
    return [], None, None


def parse_file(path):
    """Возвращает dict {имя_объекта: {метка_времени: значение}}"""
    rows, enc, delim = sniff_read(path)
    if len(rows) < 2:
        print('   ⚠️  Файл пуст или только заголовок')
        return {}, 'unknown'

    header = rows[0]
    body = rows[1:]

    # --- Определяем ориентацию ---
    hdr_times = [parse_time(c) for c in header[1:]]
    hdr_time_ratio = sum(1 for t in hdr_times if t) / max(1, len(hdr_times))

    col0_times = [parse_time(r[0]) for r in body if r]
    col0_time_ratio = sum(1 for t in col0_times if t) / max(1, len(col0_times))

    series = {}

    if hdr_time_ratio >= 0.5 and hdr_time_ratio >= col0_time_ratio:
        # ФОРМА A: объекты в строках, время в столбцах
        orient = 'objects_in_rows'
        for r in body:
            if not r or not r[0].strip():
                continue
            name = r[0].strip()
            pts = {}
            for i, t in enumerate(hdr_times):
                if not t:
                    continue
                v = to_number(r[i + 1]) if i + 1 < len(r) else None
                if v is not None:
                    pts[t[0]] = v
            if pts:
                series[name] = pts

    elif col0_time_ratio >= 0.5:
        # ФОРМА B: время в строках, объекты в столбцах (экспорт WEAP)
        orient = 'time_in_rows'
        names = [c.strip() for c in header[1:]]
        for name in names:
            if name:
                series[name] = {}
        for r in body:
            if not r:
                continue
            t = parse_time(r[0])
            if not t:
                continue
            for i, name in enumerate(names):
                if not name or i + 1 >= len(r):
                    continue
                v = to_number(r[i + 1])
                if v is not None:
                    series[name][t[0]] = v
        series = {k: v for k, v in series.items() if v}

    else:
        # Нет времени вообще — считаем, что это одно значение на объект
        # (например: канал → процент отвода)
        orient = 'single_value'
        # берём первый числовой столбец
        for r in body:
            if not r or not r[0].strip():
                continue
            name = r[0].strip()
            for cell in r[1:]:
                v = to_number(cell)
                if v is not None:
                    series[name] = {'const': v}
                    break

    return series, orient


def main():
    print('=' * 60)
    print('📊 ПАРСИНГ CSV — ВРЕМЕННЫЕ РЯДЫ')
    print('=' * 60 + '\n')

    os.makedirs(CSV_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    files = sorted(glob.glob(os.path.join(CSV_DIR, '*.csv')))
    if not files:
        print(f'⚠️  Нет .csv файлов в {CSV_DIR}')
        print('   Положите туда таблицы — см. csv/ПОЛОЖИТЕ_СЮДА_ДАННЫЕ.txt\n')
        json.dump({}, open(os.path.join(OUTPUT_DIR, 'timeseries.json'),
                           'w', encoding='utf-8'))
        return

    datasets = {}
    for path in files:
        fname = os.path.basename(path)
        code, label, unit, layer = classify_file(fname)
        print(f'📄 {fname}')
        print(f'   Тип: {label}' + (f' [{unit}]' if unit else ''))

        try:
            series, orient = parse_file(path)
        except Exception as e:
            print(f'   ❌ Ошибка: {e}\n')
            continue

        if not series:
            print('   ⚠️  Не удалось распознать данные\n')
            continue

        # Статистика
        all_times = sorted({t for pts in series.values() for t in pts})
        monthly = any('-' in t for t in all_times)
        n_pts = sum(len(p) for p in series.values())

        orient_ru = {'objects_in_rows': 'объекты в строках',
                     'time_in_rows': 'время в строках',
                     'single_value': 'одно значение на объект'}[orient]
        print(f'   Ориентация: {orient_ru}')
        print(f'   Объектов: {len(series)}, значений: {n_pts}')
        if all_times and orient != 'single_value':
            print(f'   Период: {all_times[0]} … {all_times[-1]}'
                  f' ({"месячно" if monthly else "годично"})')
        print(f'   Примеры: {", ".join(list(series)[:3])}')
        print()

        datasets[code] = {
            'label': label,
            'unit': unit,
            'layer': layer,
            'file': fname,
            'resolution': 'monthly' if monthly else (
                'const' if orient == 'single_value' else 'annual'),
            'times': all_times,
            'series': series,
        }

    out = os.path.join(OUTPUT_DIR, 'timeseries.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(datasets, f, ensure_ascii=False)

    print('=' * 60)
    print(f'✅ Наборов данных: {len(datasets)}')
    for code, d in datasets.items():
        print(f'   {code:24s} {len(d["series"]):4d} объектов  [{d["resolution"]}]')
    print(f'\n   Сохранено: {out}')
    print('=' * 60 + '\n')


if __name__ == '__main__':
    main()
