@echo off
REM ЗАПУСК: обрабатывает все ваши файлы и собирает карту
REM Использование: двойной клик по run.bat (Windows)

cd /d "%~dp0"

echo ============================================================
echo  WEAP SYRDARYA - СБОРКА ПРОЕКТА
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [X] Python не найден. Установите: https://python.org
    echo     ВАЖНО: отметьте "Add Python to PATH" при установке
    pause
    exit /b 1
)

python -c "import geopandas" 2>nul
if errorlevel 1 (
    echo [*] Устанавливаю библиотеки ^(один раз^)...
    pip install -r requirements.txt
    echo.
)

echo -- Шаг 1/3: Конвертация shapefiles в GeoJSON --
python scripts\convert_shapefiles.py
echo.

echo -- Шаг 2/3: Парсинг KML/KMZ --
python scripts\parse_kml.py
echo.

echo -- Шаг 3/3: Сборка данных для карты --
python scripts\build_data.py
echo.

echo ============================================================
echo  ГОТОВО!
echo ============================================================
echo.
echo Открываю карту: output\index.html
echo.

start "" "output\index.html"
pause
