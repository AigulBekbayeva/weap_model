# WEAP Syrdarya

An interactive map and charts for a WEAP model. Drop your files into the folders,
run one script, open the result in a browser - https://aigulbekbayeva.github.io/weap_model/.

## Getting started

Put your files where they belong (see below), then run `run.bat` on Windows or
`./run.sh` on Mac and Linux. The map opens by itself — it lives at `output/index.html`.

Python 3 is the only requirement; the script installs the libraries it needs on
the first run.

## What goes where

**shapefiles/** — your `.shp` files: water management zones, basin boundaries, any
polygons you want on the map. Copy the whole set together (`.shp`, `.shx`, `.dbf`,
`.prj`), not just the one file. Each shapefile becomes its own layer with a
checkbox, named after the file.

**kml/** — the `.kmz` you export from WEAP (Schematic → Export to Google Earth).
Demand sites, rivers, canals, transmission links, gauges, reservoirs, groundwater
and flow requirements are all read out of it.

**csv/** — tables of values over time. The file name decides what the data is:
`demand_consumption.csv`, `gauge_modeled.csv`, `reservoir_volume.csv`, and so on.


**docs/** — the result. `index.html` is the map, `weap-data.js` holds everything
the scripts collected, and `lib/` keeps Leaflet and Chart.js locally so the page
works without an internet connection.

**scripts/** — the processing itself. Nothing here needs touching.

## Worth knowing

Shapefiles are reprojected to WGS84 automatically, so whatever projection yours
are in will work.

CSV tables are read in either orientation — objects in rows or time in rows — so
a WEAP export needs no reshaping. Dates can be `2020`, `2020-01`, `01.2020` or
`Jan-2020`; the separator and decimal mark are detected too.

Names in the CSV are matched against names in the KMZ by the WEAP zone code and
category.

Everything in `docs/` is self-contained — to publish on GitHub Pages, copy that
folder and nothing else.

---

Developed by A. Bekbayeva · [LinkedIn](https://www.linkedin.com/in/aigulbekbayeva/)