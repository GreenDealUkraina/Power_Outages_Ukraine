#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import geopandas as gpd
import yaml


DATE_FMT = "%d.%m.%Y"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build two synced Leaflet maps (scheduled vs actual outages)."
    )
    parser.add_argument(
        "--data",
        default="data/clean_outages.csv",
        help="Cleaned outages CSV.",
    )
    parser.add_argument(
        "--adm1",
        default="shapefiles/UA_adm1.shp",
        help="ADM1 shapefile path.",
    )
    parser.add_argument(
        "--occupied",
        default="shapefiles/occupied_territory.shp",
        help="Occupied territory shapefile path.",
    )
    parser.add_argument(
        "--out",
        default="docs/maps/outage_maps.html",
        help="Output HTML path.",
    )
    parser.add_argument(
        "--yaml",
        default="templates/dashboard.yaml",
        help="Dashboard YAML for tooltip text.",
    )
    return parser.parse_args()


def parse_float(value: str) -> float | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def load_clean_data(path: Path) -> Tuple[List[str], Dict[str, Dict[str, Dict[str, float]]]]:
    data: Dict[str, Dict[str, Dict[str, float]]] = {}
    dates: List[datetime] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = (row.get("Date") or "").strip()
            gid = (row.get("GID_1") or "").strip()
            if not date or not gid:
                continue
            scheduled = parse_float(row.get("Scheduled_outages", ""))
            actual = parse_float(row.get("Actual_outages", ""))
            data.setdefault(date, {})
            subqueues = (row.get("Subqueues") or "").strip()
            data[date][gid] = {
                "scheduled": scheduled,
                "actual": actual,
                "subqueues": subqueues,
            }
            try:
                dates.append(datetime.strptime(date, DATE_FMT))
            except ValueError:
                continue
    unique_dates = sorted({d for d in dates})
    date_strings = [d.strftime(DATE_FMT) for d in unique_dates]
    return date_strings, data


def load_geojson(path: Path) -> Dict:
    gdf = gpd.read_file(path)
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    return json.loads(gdf.to_json())


def build_html(
    adm1_geojson: Dict,
    occupied_geojson: Dict,
    date_strings: List[str],
    data: Dict[str, Dict[str, Dict[str, float]]],
    scheduled_tip: str,
    actual_tip: str,
) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Ukraine Outage Maps</title>
  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    crossorigin=""
  />
  <style>
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", "Source Sans 3", "Segoe UI", sans-serif;
      color: #1f2a34;
      background: #f7f5f1;
    }}
    .wrapper {{
      max-width: 1300px;
      margin: 0 auto;
      padding: 18px 18px 26px;
    }}
    .toolbar {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;
      position: sticky;
      top: 0;
      z-index: 500;
      background: #f7f5f1;
      padding: 6px 8px;
      border-radius: 8px;
      box-shadow: 0 6px 16px rgba(0,0,0,0.06);
    }}
    select {{
      padding: 6px 10px;
      border-radius: 8px;
      border: 1px solid #d8d2c8;
      background: #fff;
      font-size: 14px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }}
    .map-card {{
      background: #fff;
      border: 1px solid #d8d2c8;
      box-shadow: 0 8px 24px rgba(0,0,0,0.08);
      border-radius: 10px;
      padding: 10px;
      position: relative;
    }}
    .expand-btn {{
      position: absolute;
      top: 10px;
      right: 10px;
      background: #f0ece4;
      border: 1px solid #d8d2c8;
      border-radius: 6px;
      padding: 4px 8px;
      font-size: 12px;
      cursor: pointer;
      color: #1f2a34;
    }}
    .expand-btn:hover {{
      background: #e8e2d8;
    }}
    .modal {{
      position: fixed;
      inset: 0;
      background: rgba(20, 24, 28, 0.7);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 9999;
    }}
    .modal.open {{
      display: flex;
    }}
    .modal-content {{
      width: min(94vw, 1400px);
      height: min(90vh, 900px);
      background: #fff;
      border-radius: 12px;
      box-shadow: 0 18px 50px rgba(0, 0, 0, 0.2);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .modal-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 16px;
      border-bottom: 1px solid #e0e0e0;
      background: #f7f4ee;
    }}
    .modal-title {{
      font-size: 14px;
      font-weight: 600;
      margin: 0;
    }}
    .close-btn {{
      background: transparent;
      border: none;
      font-size: 18px;
      cursor: pointer;
      color: #1f2a34;
    }}
    .modal-map {{
      flex: 1;
    }}
    .map-title {{
      margin: 4px 0 8px;
      font-size: 16px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .info {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 18px;
      height: 18px;
      border-radius: 999px;
      background: #e9f3f5;
      color: #0f6f7a;
      font-size: 12px;
      font-weight: 700;
      cursor: help;
      position: relative;
    }}
    .info::after {{
      content: attr(data-tooltip);
      position: absolute;
      left: 24px;
      top: 50%;
      transform: translateY(-50%);
      background: #1f2a34;
      color: #fff;
      padding: 6px 8px;
      border-radius: 6px;
      font-size: 11px;
      line-height: 1.3;
      white-space: normal;
      width: 220px;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.15s ease;
      z-index: 10;
    }}
    .info:hover::after {{
      opacity: 1;
    }}
    .map {{
      height: 420px;
      border-radius: 8px;
    }}
    .legend {{
      background: white;
      padding: 8px 10px;
      border-radius: 8px;
      border: 1px solid #d8d2c8;
      font-size: 12px;
      line-height: 1.4;
    }}
    .legend .row {{
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 4px;
    }}
    .leaflet-bar a[data-tooltip] {{
      position: relative;
    }}
    .leaflet-bar a[data-tooltip]::after {{
      content: attr(data-tooltip);
      position: absolute;
      left: 36px;
      top: 50%;
      transform: translateY(-50%);
      background: #1f2a34;
      color: #fff;
      padding: 4px 6px;
      border-radius: 4px;
      font-size: 11px;
      white-space: nowrap;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.15s ease;
    }}
    .leaflet-bar a[data-tooltip]:hover::after {{
      opacity: 1;
    }}
    .leaflet-interactive:focus {{
      outline: none;
    }}
    .swatch {{
      width: 14px;
      height: 14px;
      border: 1px solid #999;
    }}
    @media (max-width: 960px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .map {{ height: 360px; }}
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="toolbar">
      <label for="date-select"><strong>Date:</strong></label>
      <select id="date-select"></select>
    </div>
    <div class="grid">
      <div class="map-card">
        <div class="map-title">
          Scheduled outages
          <span class="info" data-tooltip="{scheduled_tip}">i</span>
        </div>
        <button class="expand-btn" data-expand="scheduled">Expand</button>
        <div id="map-scheduled" class="map"></div>
      </div>
      <div class="map-card">
        <div class="map-title">
          Actual outages
          <span class="info" data-tooltip="{actual_tip}">i</span>
        </div>
        <button class="expand-btn" data-expand="actual">Expand</button>
        <div id="map-actual" class="map"></div>
      </div>
    </div>
  </div>
  <div class="modal" id="map-modal">
    <div class="modal-content">
      <div class="modal-header">
        <div class="modal-title" id="modal-title">Expanded map</div>
        <button class="close-btn" id="modal-close" aria-label="Close">×</button>
      </div>
      <div id="modal-map" class="modal-map"></div>
    </div>
  </div>
  <script
    src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    crossorigin=""
  ></script>
  <script src="https://unpkg.com/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
  <script>
    const adminGeo = {json.dumps(adm1_geojson)};
    const occupiedGeo = {json.dumps(occupied_geojson)};
    const outageData = {json.dumps(data)};
    const dates = {json.dumps(date_strings)};

    const palette = [
      {{ label: "0", color: "#2f9e44" }},
      {{ label: "1-4", color: "#f2e86d" }},
      {{ label: "5-8", color: "#f5c76b" }},
      {{ label: "9-12", color: "#f19a6b" }},
      {{ label: "13-16", color: "#e76b5a" }},
      {{ label: "17-20", color: "#c7433c" }},
      {{ label: "21-24", color: "#8f1d1d" }},
    ];

    function getColor(value) {{
      if (value === null || value === undefined || value === "") return "#cfcfcf";
      const rounded = Math.round(value);
      if (rounded <= 0) return palette[0].color;
      if (rounded >= 1 && rounded <= 4) return palette[1].color;
      if (rounded >= 5 && rounded <= 8) return palette[2].color;
      if (rounded >= 9 && rounded <= 12) return palette[3].color;
      if (rounded >= 13 && rounded <= 16) return palette[4].color;
      if (rounded >= 17 && rounded <= 20) return palette[5].color;
      return palette[6].color;
    }}

    const mapScheduled = L.map("map-scheduled", {{
      zoomControl: true,
      scrollWheelZoom: true,
      keyboard: false,
      wheelPxPerZoomLevel: 120,
      preferCanvas: true
    }});
    const mapActual = L.map("map-actual", {{
      zoomControl: true,
      scrollWheelZoom: true,
      keyboard: false,
      wheelPxPerZoomLevel: 120,
      preferCanvas: true
    }});

    const baseScheduled = L.tileLayer(
      "https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png",
      {{ attribution: "&copy; OpenStreetMap &copy; CARTO", crossOrigin: true }}
    );
    const baseActual = L.tileLayer(
      "https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png",
      {{ attribution: "&copy; OpenStreetMap &copy; CARTO", crossOrigin: true }}
    );
    baseScheduled.addTo(mapScheduled);
    baseActual.addTo(mapActual);

    const occupiedStyle = {{
      color: "#444",
      weight: 1,
      fillColor: "#6f6f6f",
      fillOpacity: 0.35,
      dashArray: "4 4",
    }};

    let layerScheduled = null;
    let layerActual = null;
    let modalMap = null;
    let modalLayer = null;

    function addLegend(map) {{
      const legend = L.control({{ position: "bottomright" }});
      legend.onAdd = function () {{
        const div = L.DomUtil.create("div", "legend");
        div.innerHTML = "<strong>Outage hours (per day)</strong>";
        palette.forEach(p => {{
          const row = document.createElement("div");
          row.className = "row";
          const swatch = document.createElement("span");
          swatch.className = "swatch";
          swatch.style.background = p.color;
          const label = document.createElement("span");
          label.textContent = p.label;
          row.appendChild(swatch);
          row.appendChild(label);
          div.appendChild(row);
        }});
        const naRow = document.createElement("div");
        naRow.className = "row";
        const naSwatch = document.createElement("span");
        naSwatch.className = "swatch";
        naSwatch.style.background = "#cfcfcf";
        const naLabel = document.createElement("span");
        naLabel.textContent = "No data";
        naRow.appendChild(naSwatch);
        naRow.appendChild(naLabel);
        div.appendChild(naRow);

        const occRow = document.createElement("div");
        occRow.className = "row";
        const occSwatch = document.createElement("span");
        occSwatch.className = "swatch";
        occSwatch.style.background = occupiedStyle.fillColor;
        occSwatch.style.border = "1px dashed #444";
        const occLabel = document.createElement("span");
        occLabel.textContent = "Occupied territory";
        occRow.appendChild(occSwatch);
        occRow.appendChild(occLabel);
        div.appendChild(occRow);
        return div;
      }};
      legend.addTo(map);
    }}

    function addControls(map, label, resetBounds) {{
      const Control = L.Control.extend({{
        onAdd: function() {{
          const container = L.DomUtil.create("div", "leaflet-bar");
          container.style.background = "#fff";
          container.style.border = "1px solid #d8d2c8";
          container.style.borderRadius = "6px";
          container.style.overflow = "hidden";

          const resetBtn = L.DomUtil.create("a", "", container);
          resetBtn.href = "#";
          resetBtn.title = "Reset view";
          resetBtn.setAttribute("data-tooltip", "Reset view");
          resetBtn.innerHTML = "⟲";
          resetBtn.style.display = "block";
          resetBtn.style.width = "30px";
          resetBtn.style.height = "30px";
          resetBtn.style.lineHeight = "30px";
          resetBtn.style.textAlign = "center";
          resetBtn.style.color = "#1f2a34";

          const downloadBtn = L.DomUtil.create("a", "", container);
          downloadBtn.href = "#";
          downloadBtn.title = "Download current view";
          downloadBtn.setAttribute("data-tooltip", "Download current view");
          downloadBtn.innerHTML = "⭳";
          downloadBtn.style.display = "block";
          downloadBtn.style.width = "30px";
          downloadBtn.style.height = "30px";
          downloadBtn.style.lineHeight = "30px";
          downloadBtn.style.textAlign = "center";
          downloadBtn.style.color = "#1f2a34";

          L.DomEvent.on(resetBtn, "click", (e) => {{
            L.DomEvent.stop(e);
            map.fitBounds(resetBounds);
          }});
          L.DomEvent.on(downloadBtn, "click", (e) => {{
            L.DomEvent.stop(e);
            html2canvas(map.getContainer(), {{
              useCORS: true,
              backgroundColor: null
            }}).then((canvas) => {{
              const link = document.createElement("a");
              link.download = `${{label}}_${{dateSelect.value}}.png`;
              link.href = canvas.toDataURL("image/png");
              link.click();
            }});
          }});
          return container;
        }}
      }});
      map.addControl(new Control({{ position: "topleft" }}));
    }}

    function renderLayers(selectedDate) {{
      if (layerScheduled) mapScheduled.removeLayer(layerScheduled);
      if (layerActual) mapActual.removeLayer(layerActual);

      const dayData = outageData[selectedDate] || {{}};

      layerScheduled = L.geoJSON(adminGeo, {{
        style: feature => {{
          const gid = feature.properties.GID_1;
          const val = dayData[gid] ? dayData[gid].scheduled : null;
          return {{
            color: "#666",
            weight: 0.7,
            fillColor: getColor(val),
            fillOpacity: 0.85
          }};
        }},
        onEachFeature: (feature, layer) => {{
          const gid = feature.properties.GID_1;
          const name = feature.properties.NAME_1 || gid;
          const val = dayData[gid] ? dayData[gid].scheduled : null;
          const valueText = (val === null || val === undefined || val === "") ? "No data" : `${{val}} hours`;
          const subqueues = dayData[gid] ? dayData[gid].subqueues : "";
          const subqueueLine = subqueues ? `<br>Sub-queues: ${{subqueues}}` : "";
          const html = `<strong>${{name}}</strong><br>Region ID: ${{gid}}<br>Scheduled: ${{valueText}}${{subqueueLine}}`;
          layer.bindTooltip(html, {{ sticky: true }});
        }}
      }}).addTo(mapScheduled);

      layerActual = L.geoJSON(adminGeo, {{
        style: feature => {{
          const gid = feature.properties.GID_1;
          const val = dayData[gid] ? dayData[gid].actual : null;
          return {{
            color: "#666",
            weight: 0.7,
            fillColor: getColor(val),
            fillOpacity: 0.85
          }};
        }},
        onEachFeature: (feature, layer) => {{
          const gid = feature.properties.GID_1;
          const name = feature.properties.NAME_1 || gid;
          const val = dayData[gid] ? dayData[gid].actual : null;
          const valueText = (val === null || val === undefined || val === "") ? "No data" : `${{val}} hours`;
          const subqueues = dayData[gid] ? dayData[gid].subqueues : "";
          const subqueueLine = subqueues ? `<br>Sub-queues: ${{subqueues}}` : "";
          const html = `<strong>${{name}}</strong><br>Region ID: ${{gid}}<br>Actual: ${{valueText}}${{subqueueLine}}`;
          layer.bindTooltip(html, {{ sticky: true }});
        }}
      }}).addTo(mapActual);

      L.geoJSON(occupiedGeo, {{ style: occupiedStyle }}).addTo(mapScheduled);
      L.geoJSON(occupiedGeo, {{ style: occupiedStyle }}).addTo(mapActual);
    }}

    function fitBoth() {{
      const bounds = L.geoJSON(adminGeo).getBounds();
      mapScheduled.fitBounds(bounds);
      mapActual.fitBounds(bounds);
      return bounds;
    }}

    function createModalMap(kind) {{
      const modalEl = document.getElementById("map-modal");
      const modalTitle = document.getElementById("modal-title");
      const modalMapEl = document.getElementById("modal-map");
      modalTitle.textContent = kind === "scheduled" ? "Scheduled outages" : "Actual outages";
      modalEl.classList.add("open");

      if (modalMap) {{
        modalMap.remove();
        modalMap = null;
      }}
      modalMapEl.innerHTML = "";
      modalMap = L.map("modal-map", {{
        zoomControl: true,
        scrollWheelZoom: true,
        keyboard: false,
        wheelPxPerZoomLevel: 120,
        preferCanvas: true
      }});
      const baseModal = L.tileLayer(
        "https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png",
        {{ attribution: "&copy; OpenStreetMap &copy; CARTO", crossOrigin: true }}
      );
      baseModal.addTo(modalMap);

      const selectedDate = dateSelect.value;
      const dayData = outageData[selectedDate] || {{}};

      if (modalLayer) {{
        modalMap.removeLayer(modalLayer);
      }}

      modalLayer = L.geoJSON(adminGeo, {{
        style: feature => {{
          const gid = feature.properties.GID_1;
          const val = dayData[gid] ? dayData[gid][kind] : null;
          return {{
            color: "#666",
            weight: 0.7,
            fillColor: getColor(val),
            fillOpacity: 0.85
          }};
        }},
        onEachFeature: (feature, layer) => {{
          const gid = feature.properties.GID_1;
          const name = feature.properties.NAME_1 || gid;
          const val = dayData[gid] ? dayData[gid][kind] : null;
          const valueText = (val === null || val === undefined || val === "") ? "No data" : `${{val}} hours`;
          const subqueues = dayData[gid] ? dayData[gid].subqueues : "";
          const subqueueLine = subqueues ? `<br>Sub-queues: ${{subqueues}}` : "";
          const label = kind === "scheduled" ? "Scheduled" : "Actual";
          const html = `<strong>${{name}}</strong><br>Region ID: ${{gid}}<br>${{label}}: ${{valueText}}${{subqueueLine}}`;
          layer.bindTooltip(html, {{ sticky: true }});
        }}
      }}).addTo(modalMap);
      L.geoJSON(occupiedGeo, {{ style: occupiedStyle }}).addTo(modalMap);
      modalMap.fitBounds(L.geoJSON(adminGeo).getBounds());
      addLegend(modalMap);
    }}

    const dateSelect = document.getElementById("date-select");
    dates.forEach(date => {{
      const opt = document.createElement("option");
      opt.value = date;
      opt.textContent = date;
      dateSelect.appendChild(opt);
    }});
    const initialDate = dates[dates.length - 1];
    dateSelect.value = initialDate;

    dateSelect.addEventListener("change", (e) => {{
      renderLayers(e.target.value);
    }});

    addLegend(mapScheduled);
    addLegend(mapActual);
    renderLayers(initialDate);
    const bounds = fitBoth();
    addControls(mapScheduled, "scheduled_outages", bounds);
    addControls(mapActual, "actual_outages", bounds);

    document.querySelectorAll("[data-expand]").forEach((btn) => {{
      btn.addEventListener("click", () => {{
        createModalMap(btn.getAttribute("data-expand"));
      }});
    }});
    document.getElementById("modal-close").addEventListener("click", () => {{
      document.getElementById("map-modal").classList.remove("open");
    }});
    document.getElementById("map-modal").addEventListener("click", (e) => {{
      if (e.target.id === "map-modal") {{
        document.getElementById("map-modal").classList.remove("open");
      }}
    }});
  </script>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    data_path = Path(args.data)
    adm1_path = Path(args.adm1)
    occupied_path = Path(args.occupied)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    date_strings, data = load_clean_data(data_path)
    adm1_geojson = load_geojson(adm1_path)
    occupied_geojson = load_geojson(occupied_path)

    yaml_path = Path(args.yaml)
    scheduled_tip = "Planned outages announced by authorities for each day."
    actual_tip = "Observed outages reported by households for each day."
    if yaml_path.exists():
        config = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        maps_cfg = config.get("maps", {}).get("combined", {})
        scheduled_tip = maps_cfg.get("scheduled_tooltip", scheduled_tip)
        actual_tip = maps_cfg.get("actual_tooltip", actual_tip)

    html = build_html(
        adm1_geojson, occupied_geojson, date_strings, data, scheduled_tip, actual_tip
    )
    out_path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
