# Sunstripe Site Feasibility & Fatal-Flaw Screening

A Streamlit-based early-stage GIS screening app for renewable-energy sites and large loads. The user can upload or draw a site boundary, query default public GIS services, overlay project-specific constraint layers, inspect spatial hits on a map, and export a Markdown report plus CSV results.

> **Important use limitation:** This is a preliminary diligence aid, not a legal or permitting determination. Mapped overlap is a trigger for professional review, not automatically a fatal flaw. “No mapped overlap” does not prove a constraint is absent. A missing or failed layer remains **Not assessed**.

## What the reference file informed

The provided reference text is a bibliography/source inventory (pages 47–54), with references to species and critical habitat, wetlands, karst, FAA/airports, military areas, landfills/mines, population/EJScreen, parcels, conservation lands, transmission/substations, pipelines, landslides, flood maps, USGS topography/hydrography, energy-community layers, historic resources and related subjects. It does not provide universal legal thresholds or pass/fail rules. The app therefore uses a transparent screening severity and tracks data gaps instead of asserting definitive eligibility.

## Features

- Upload a site boundary as GeoJSON, JSON, KML, GeoPackage, or zipped shapefile (the shapefile ZIP must include its `.prj` file).
- Or draw a Polygon/Rectangle on the interactive map.
- Calculate a site-area estimate in acres and select a 0–5 mile proximity buffer.
- Query four public ArcGIS REST layers by spatial intersection:
  - FEMA National Flood Hazard Layer — flood hazard zones.
  - USFWS National Wetlands Inventory.
  - USFWS final critical habitat.
  - USFWS proposed critical habitat.
- Upload extra GIS constraints such as PAD-US protected areas, parcels, local zoning, transmission/substations, tribal lands, cultural resources, FAA/military layers, karst, landslide, pipeline, road/rail, landfill/mine, or environmental justice datasets.
- Distinguish site-intersection features from buffer-only features; return **Not assessed** when a service fails or a layer is unusable.
- View the site and sampled hit geometries on a Folium map, inspect per-layer findings, and download report Markdown and results CSV.
- Includes a demo GeoJSON boundary and basic geometry tests.

## Run locally

Use Python 3.11 if possible.

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

Open the local URL displayed by Streamlit. To test, upload `sample_data/sample_site.geojson` as the candidate boundary. It is only a demo polygon; do not treat its result as project diligence.

## Deploy from GitHub to Streamlit Community Cloud

1. Create a new GitHub repository, for example `sunstripe-site-fatal-flaw`.
2. Upload/push the contents of this folder to the repository root (`app.py` must be at the root).
3. Open Streamlit Community Cloud and choose **Create app**.
4. Select your repository and branch, set the main file path to `app.py`, and deploy.
5. Keep `requirements.txt`, `.streamlit/config.toml`, `data_sources.py`, `screening.py`, `reporting.py`, `sample_data/`, and `tests/` in the repository.

The app needs outbound internet access to query the default public REST layers. If a service is unavailable, its row is reported as **Not assessed** rather than being treated as clear. Large GIS uploads can exceed hosting memory/time limits; simplify or clip local datasets to the site region before uploading.

## Data upload notes

- **Candidate site:** Polygon/MultiPolygon boundary only. Use a valid spatial reference and include `.prj` for shapefiles.
- **Supplemental constraints:** Upload one GIS file per layer and choose a category/severity. Spatial operations assume the upload is georeferenced; it is reprojected to WGS84 before analysis.
- **Line and point layers:** useful for distance/proximity screening; the app reports feature counts, but area overlap is only calculated for polygonal layers.
- **National data services:** the four built-in services are only a starting set. They do not replace local/state permitting portals, USACE wetland jurisdiction, title/ownership review, zoning confirmation, FAA determinations, environmental surveys, or a utility/interconnection study.

## Default public data source notes

- FEMA National Flood Hazard Layer: <https://www.fema.gov/flood-maps/national-flood-hazard-layer> and REST endpoint <https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28>
- USFWS National Wetlands Inventory mapping services: <https://www.fws.gov/program/national-wetlands-inventory/web-mapping-services>; REST endpoint <https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer/0>
- USFWS ECOS data services / species critical habitat: <https://fis.fws.gov/ecp/services>; FeatureServer <https://services.arcgis.com/QVENGdaPbd4LUkLV/arcgis/rest/services/USFWS_Critical_Habitat/FeatureServer>
- USGS Protected Areas Database (PAD-US) overview and downloads: <https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview>
- USGS National Map web services: <https://apps.nationalmap.gov/services/>

## Screening logic

| Output | Logic |
|---|---|
| Potential fatal flaw | Site intersects a layer configured as `Critical`; urgent specialist review is recommended. |
| Major constraint | Site intersects a layer configured as `High`. |
| Review required / Minor constraint | Site intersects a layer configured as `Moderate` / `Low`. |
| Nearby constraint | No site intersection, but at least one returned feature intersects the selected buffer. |
| No mapped overlap | No features are returned from that source for the queried geometry. |
| Not assessed | Online layer failure or an unusable supplemental dataset. |

Severity is a screening setting, not a legal conclusion. Tune layer severity to match a documented, jurisdiction-specific fatal-flaw matrix before using this for investment decisions.

## Recommended next build-out

1. Add parcel ownership/title, local zoning, conservation easements, PAD-US, tribal/cultural resources, protected species, karst/landslide, airport/military, and utility/transmission datasets with documented source dates.
2. Add configurable, asset-specific threshold rules for Solar PV, Wind, BESS, and Data Center/Large Load, approved by the development and environmental teams.
3. Add source-coverage checks, layer timestamps, saved project runs, user authentication, and reviewer sign-off.
4. Add parcel-level site-control and interconnection diligence with explicit evidence links. Distance to a line or substation must never be interpreted as available interconnection capacity.

## Tests

```bash
pip install pytest
pytest -q
```
