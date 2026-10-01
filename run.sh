#!/bin/bash
# ЗАПУСК: обрабатывает все ваши файлы и собирает карту
# Использование:  ./run.sh    (Mac/Linux)

cd "$(dirname "$0")"

echo "============================================================"
echo "🌊 WEAP SYRDARYA — СБОРКА ПРОЕКТА"
echo "============================================================"
echo

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 не найден. Установите: https://python.org"
    exit 1
fi

# Проверка библиотек
python3 -c "import geopandas" 2>/dev/null || {
    echo "📦 Устанавливаю библиотеки (один раз)…"
    pip3 install -r requirements.txt || pip3 install --break-system-packages -r requirements.txt
    echo
}

echo "── Шаг 1/3: Конвертация shapefiles → GeoJSON ──"
python3 scripts/convert_shapefiles.py
echo

echo "── Шаг 2/3: Парсинг KML/KMZ ──"
python3 scripts/parse_kml.py
echo

echo "── Шаг 3/3: Сборка данных для карты ──"
python3 scripts/build_data.py
echo

echo "============================================================"
echo "✅ ГОТОВО!"
echo "============================================================"
echo
echo "Откройте карту:  output/index.html"
echo

# Автооткрытие
if command -v open &> /dev/null; then
    open output/index.html            # macOS
elif command -v xdg-open &> /dev/null; then
    xdg-open output/index.html        # Linux
fi
