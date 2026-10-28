from __future__ import annotations

import json
from datetime import datetime

import folium
from folium.plugins import Draw
import geopandas as gpd
import pandas as pd
import streamlit as st
from shapely.geometry import shape, mapping
from streamlit_folium import st_folium

from data_sources import AUTO_LAYERS, CONSTRAINT_CATEGORIES, REFERENCE_CHECKLIST, REQUIRED_DATA_CHECKS, SEVERITIES, SEVERITY_HELP
from reporting import build_markdown_report, results_to_csv
from screening import (
    buffer_geometry_miles,
    geometry_area_acres,
    read_geodata_from_bytes,
    result_table,
    run_local_check,
    run_online_check,
    site_geometry_from_gdf,
)

st.set_page_config(page_title="Site Feasibility & Fatal Flaw | Sunstripe", page_icon="🧭", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
    :root { --sun-red:#E23B3B; --sun-navy:#13233D; --sun-ink:#142033; --sun-muted:#667085; }
    .stApp { background:#F7F8FA; color:var(--sun-ink); }
    [data-testid="stSidebar"] { background:#13233D; }
    [data-testid="stSidebar"] * { color:#F8FAFC !important; }
    [data-testid="stSidebar"] .stButton button { background:#E23B3B; border:0; color:white !important; font-weight:700; }
    .hero { background:#FFFFFF; padding:1.2rem 1.5rem; border-radius:16px; border-left:5px solid #E23B3B; margin-bottom:1rem; box-shadow:0 3px 18px rgba(19,35,61,.06); }
    .hero-eyebrow { color:#E23B3B; font-size:.76rem; letter-spacing:.13em; font-weight:800; text-transform:uppercase; }
    .hero h1 { color:#13233D; font-size:2rem; margin:.25rem 0 .35rem 0; }
    .hero p { color:#475467; margin:0; font-size:1rem; }
    .small-note { font-size:.82rem; color:#667085; }
    .kpi { background:#FFFFFF; border:1px solid #EAECF0; border-radius:12px; padding:15px 17px; min-height:95px; }
    .kpi-label { font-size:.78rem; color:#667085; }
    .kpi-value { font-size:1.6rem; font-weight:800; color:#13233D; }
    div[data-testid="stMetric"] { background:#fff; border:1px solid #EAECF0; border-radius:12px; padding:12px 14px; }
    div[data-testid="stMetricLabel"] { color:#667085; }
    .stTabs [data-baseweb="tab-list"] { gap:8px; }
    .stTabs [data-baseweb="tab"] { background:#EFF2F6; border-radius:8px 8px 0 0; padding:10px 16px; }
    .stTabs [aria-selected="true"] { background:#13233D !important; color:white !important; }
    .pill { display:inline-block; border-radius:999px; padding:3px 9px; background:#FEE4E2; color:#B42318; font-size:.76rem; font-weight:700; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
      <div class="hero-eyebrow">SUNSTRIPE · DEVELOPMENT INTELLIGENCE</div>
      <h1>Site Feasibility & Fatal-Flaw Screening</h1>
      <p>Know where to build. Screen land, environmental, permitting and infrastructure constraints before committing development capital.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if "manual_site_geojson" not in st.session_state:
    st.session_state.manual_site_geojson = None
if "screening_results" not in st.session_state:
    st.session_state.screening_results = None
if "screened_site_signature" not in st.session_state:
    st.session_state.screened_site_signature = None

with st.sidebar:
    st.markdown("## Site setup")
    site_name = st.text_input("Project / site name", value="Candidate Site 01")
    technology = st.selectbox("Asset type", ["Solar PV", "Wind", "BESS", "Solar + BESS", "Data Center / Large Load", "Other"])
    location_label = st.text_input("State / County / Market (optional)", placeholder="e.g., Taylor County, Texas")
    source_mode = st.radio("Site boundary input", ["Upload boundary", "Draw on map"], index=0)
    site_file = None
    if source_mode == "Upload boundary":
        site_file = st.file_uploader("Site boundary GIS file", type=["geojson", "json", "zip", "gpkg", "kml"], help="GeoJSON, KML, GPKG, or a zipped shapefile including its .prj file.")
    buffer_miles = st.slider("Nearby screening buffer (miles)", min_value=0.0, max_value=5.0, value=1.0, step=0.25, help="Screens buffered areas around the site for proximity issues. Features intersecting the site are reported separately from buffer-only features.")
    run_online = st.checkbox("Query default public GIS services", value=True, help="Queries FEMA flood zones, USFWS National Wetlands Inventory, and USFWS final/proposed critical habitat services. Requires internet access from the Streamlit app.")
    run_clicked = st.button("Run fatal-flaw screen", type="primary", use_container_width=True)
    st.caption("Preliminary screen only. A data gap is never treated as a pass.")

site_geom = None
site_gdf = None
site_error = None

if source_mode == "Upload boundary" and site_file is not None:
    try:
        site_gdf = read_geodata_from_bytes(site_file.getvalue(), site_file.name)
        site_geom = site_geometry_from_gdf(site_gdf)
        st.session_state.manual_site_geojson = None
    except Exception as exc:
        site_error = str(exc)
elif source_mode == "Draw on map" and st.session_state.manual_site_geojson:
    try:
        drawn = shape(st.session_state.manual_site_geojson)
        site_gdf = gpd.GeoDataFrame({"site": [site_name]}, geometry=[drawn], crs="EPSG:4326")
        site_geom = site_geometry_from_gdf(site_gdf)
    except Exception as exc:
        site_error = f"Could not use the drawn boundary: {exc}"

# Input boundary, supplementary layers, and references.
setup_tab, data_tab, results_tab, method_tab = st.tabs(["1 · Site boundary", "2 · Data layers", "3 · Results & map", "4 · Methodology & sources"])

with setup_tab:
    st.subheader("Define the candidate site")
    if source_mode == "Draw on map":
        st.write("Use the polygon tool on the map to draw the site perimeter. Finish the polygon to save it in this session.")
        if site_geom is not None:
            minx, miny, maxx, maxy = site_geom.bounds
            center = [(miny + maxy) / 2, (minx + maxx) / 2]
            zoom = 12
        else:
            center, zoom = [39.0, -98.0], 4
        draw_map = folium.Map(location=center, zoom_start=zoom, tiles="CartoDB positron", control_scale=True)
        if site_geom is not None:
            folium.GeoJson(mapping(site_geom), name="Candidate site", style_function=lambda _: {"color": "#E23B3B", "weight": 3, "fillColor": "#E23B3B", "fillOpacity": 0.18}).add_to(draw_map)
        Draw(
            export=False,
            draw_options={"polyline": False, "rectangle": True, "circle": False, "circlemarker": False, "marker": False, "polygon": {"allowIntersection": False, "showArea": True}},
            edit_options={"edit": True, "remove": True},
        ).add_to(draw_map)
        drawn_result = st_folium(draw_map, height=560, use_container_width=True, key="site_boundary_draw", returned_objects=["all_drawings"])
        drawings = drawn_result.get("all_drawings") or []
        if drawings:
            # Keep the most recently returned polygon/rectangle; circles are disabled.
            candidate = next((d for d in reversed(drawings) if d.get("geometry", {}).get("type") in ("Polygon", "MultiPolygon")), None)
            if candidate:
                st.session_state.manual_site_geojson = candidate["geometry"]
                try:
                    site_geom = site_geometry_from_gdf(gpd.GeoDataFrame(geometry=[shape(candidate["geometry"])], crs="EPSG:4326"))
                    site_gdf = gpd.GeoDataFrame({"site": [site_name]}, geometry=[site_geom], crs="EPSG:4326")
                except Exception as exc:
                    site_error = str(exc)
        if site_geom is None:
            st.info("No site polygon saved yet. Draw a polygon on the map, then use the sidebar button to run the screen.")
        else:
            st.success("Site boundary is ready for screening.")
    elif site_file is None:
        st.info("Upload a site boundary file in the left sidebar, or change the input mode to draw a polygon on the map.")
        # A demo map is included to make the map panel useful before a real site is uploaded.
        preview = folium.Map(location=[39.0, -98.0], zoom_start=4, tiles="CartoDB positron", control_scale=True)
        folium.LayerControl().add_to(preview)
        st_folium(preview, height=500, use_container_width=True, key="empty_preview", returned_objects=[])
    elif site_geom is not None:
        minx, miny, maxx, maxy = site_geom.bounds
        area = geometry_area_acres(site_geom)
        st.success("Boundary loaded and validated.")
        col1, col2, col3 = st.columns(3)
        col1.metric("Estimated site area", f"{area:,.2f} acres")
        col2.metric("Boundary type", site_geom.geom_type)
        col3.metric("Screening buffer", f"{buffer_miles:g} mi")
        m = folium.Map(location=[(miny + maxy) / 2, (minx + maxx) / 2], zoom_start=12, tiles="CartoDB positron", control_scale=True)
        folium.GeoJson(mapping(site_geom), name="Candidate site", style_function=lambda _: {"color": "#E23B3B", "weight": 3, "fillColor": "#E23B3B", "fillOpacity": 0.2}, tooltip=site_name).add_to(m)
        if buffer_miles > 0:
            buf = buffer_geometry_miles(site_geom, buffer_miles)
            folium.GeoJson(mapping(buf), name=f"{buffer_miles:g}-mile screening buffer", style_function=lambda _: {"color": "#13233D", "weight": 1, "dashArray": "5, 5", "fillOpacity": 0.03}).add_to(m)
        folium.LayerControl().add_to(m)
        st_folium(m, height=500, use_container_width=True, key="site_preview_map", returned_objects=[])
    if site_error:
        st.error(site_error)

with data_tab:
    st.subheader("Screening data")
    st.markdown("The reference bibliography includes many subject areas. The app queries four default public layers; the other topics must be supplied as GIS layers or reviewed manually. Upload constraint layers here to add them to the analysis.")
    with st.expander("Default online services", expanded=True):
        for layer in AUTO_LAYERS:
            st.markdown(f"**{layer['name']}** · {layer['category']} · {layer['severity']}  ")
            st.markdown(f"<span class='small-note'>{layer['description']}</span>  ", unsafe_allow_html=True)
            st.markdown(f"[Open source / data service]({layer['source_url']}) · [REST layer endpoint]({layer['url']})")
            st.caption(layer["limitation"])
    st.markdown("#### Add supplemental local constraint layers")
    local_uploads = st.file_uploader(
        "Upload constraint GIS files (multiple allowed)",
        type=["geojson", "json", "zip", "gpkg", "kml"],
        accept_multiple_files=True,
        key="supplemental_layers",
        help="One upload per constraint dataset. Include a CRS; zipped shapefiles must include .shp, .shx, .dbf, and .prj. Examples: PAD-US, transmission, substations, tribal lands, local zoning, parcels, roads, karst, landslides, FAA/military, cultural resources.",
    )
    local_layers = []
    if local_uploads:
        st.caption("Choose the best-fit category and severity for each uploaded layer.")
        for idx, uploaded in enumerate(local_uploads):
            col_file, col_category, col_severity = st.columns([1.6, 1.8, 1.0])
            with col_file:
                st.write(f"**{uploaded.name}**")
                st.caption(f"{uploaded.size / 1024:,.0f} KB")
            with col_category:
                category = st.selectbox("Category", CONSTRAINT_CATEGORIES, index=CONSTRAINT_CATEGORIES.index("Other constraint layer"), key=f"cat_{idx}_{uploaded.name}")
            with col_severity:
                severity = st.selectbox("Severity", SEVERITIES, index=1, key=f"sev_{idx}_{uploaded.name}")
            try:
                layer_gdf = read_geodata_from_bytes(uploaded.getvalue(), uploaded.name)
                local_layers.append({"name": uploaded.name, "category": category, "severity": severity, "gdf": layer_gdf})
                st.caption(f"Loaded {len(layer_gdf):,} features · CRS normalized to WGS84")
            except Exception as exc:
                st.error(f"{uploaded.name}: {exc}")
    else:
        st.info("No supplemental layers uploaded. These checks will remain unassessed unless a default online service covers the topic.")
    st.markdown("#### Reference checklist")
    for heading, description in REFERENCE_CHECKLIST:
        with st.expander(heading):
            st.write(description)

# Run after local uploads have been parsed so every submitted layer is included.
if run_clicked:
    if site_geom is None:
        st.error("Upload or draw a valid polygonal site boundary before running the screen.")
    else:
        results = []
        current_area = geometry_area_acres(site_geom)
        buffer_geom = buffer_geometry_miles(site_geom, buffer_miles)
        with st.status("Running the preliminary GIS screen…", expanded=True) as status_box:
            if run_online:
                for layer in AUTO_LAYERS:
                    st.write(f"Querying {layer['name']}…")
                    results.append(run_online_check(layer, site_geom, buffer_geom))
            else:
                st.write("Online public layer checks are disabled; default online checks will be recorded as not assessed.")
                for layer in AUTO_LAYERS:
                    results.append({
                        "key": layer["key"], "name": layer["name"], "category": layer["category"], "severity": layer["severity"],
                        "source": layer["source_url"], "service_url": layer["url"], "description": layer["description"], "limitation": layer["limitation"],
                        "site_count": None, "buffer_count": None, "nearby_count": None, "status": "Not assessed",
                        "explanation": "Online public layer queries were disabled in Site setup.", "overlap_acres": None, "overlap_pct": None,
                        "features_geojson": None, "sample_truncated": False, "data_status": "Disabled by user",
                    })
            for layer in local_layers:
                st.write(f"Intersecting {layer['name']}…")
                try:
                    results.append(run_local_check(layer["name"], layer["category"], layer["severity"], layer["name"], layer["gdf"], site_geom, buffer_geom))
                except Exception as exc:
                    results.append({
                        "key": f"local_error_{layer['name']}", "name": layer["name"], "category": layer["category"], "severity": layer["severity"],
                        "source": layer["name"], "service_url": "", "description": "User-provided GIS constraint layer.",
                        "limitation": "Review the uploaded file and coordinate system.", "site_count": None, "buffer_count": None, "nearby_count": None,
                        "status": "Not assessed", "explanation": f"Spatial analysis failed: {exc}", "overlap_acres": None, "overlap_pct": None,
                        "features_geojson": None, "sample_truncated": False, "data_status": "Layer error",
                    })
            covered_categories = {str(r.get("category", "")) for r in results}
            for gap_category, gap_message in REQUIRED_DATA_CHECKS:
                # Do not imply that an item is covered merely because an unrelated layer exists.
                if gap_category not in covered_categories:
                    results.append({
                        "key": f"gap_{gap_category}", "name": f"{gap_category} — data / review required",
                        "category": gap_category, "severity": "Moderate", "source": "", "service_url": "",
                        "description": gap_message, "limitation": "No automatic pass/fail decision is available for this item in the current configuration.",
                        "site_count": None, "buffer_count": None, "nearby_count": None, "status": "Not assessed",
                        "explanation": gap_message, "overlap_acres": None, "overlap_pct": None, "features_geojson": None,
                        "sample_truncated": False, "data_status": "No layer / evidence supplied",
                    })
            status_box.update(label="Screening run complete", state="complete", expanded=False)
        st.session_state.screening_results = results
        st.session_state.screened_site_signature = {
            "site_name": site_name,
            "technology": technology,
            "location_label": location_label,
            "site_area_acres": current_area,
            "buffer_miles": buffer_miles,
            "online_enabled": run_online,
            "site_geojson": json.dumps(mapping(site_geom)),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        st.success("Screening results saved in this session. Open the Results & map tab.")

with results_tab:
    st.subheader("Screening results")
    results = st.session_state.screening_results
    signature = st.session_state.screened_site_signature
    if not results or not signature:
        st.info("No results yet. Add a site boundary, review the data inputs, then select **Run fatal-flaw screen** in the sidebar.")
    else:
        critical = sum(r.get("status") == "Potential fatal flaw" for r in results)
        major = sum(r.get("status") == "Major constraint" for r in results)
        nearby = sum(r.get("status") == "Nearby constraint" for r in results)
        not_assessed = sum(r.get("status") == "Not assessed" for r in results)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Site area", f"{signature['site_area_acres']:,.1f} ac")
        c2.metric("Potential fatal flags", critical)
        c3.metric("Major constraints", major)
        c4.metric("Nearby constraints", nearby)
        c5.metric("Not assessed", not_assessed)
        st.caption(f"**{signature['site_name']}** · {signature['technology']} · {signature['location_label'] or 'Location not provided'} · Buffer: {signature['buffer_miles']:g} mi · Run: {signature['created_at']}")
        table_df = result_table(results)
        try:
            st.dataframe(table_df, use_container_width=True, hide_index=True, column_config={
                "Mapped overlap (acres)": st.column_config.NumberColumn(format="%.2f"),
                "Site overlap (%)": st.column_config.NumberColumn(format="%.1f%%"),
            })
        except Exception:
            st.dataframe(table_df, use_container_width=True, hide_index=True)
        st.markdown("#### Constraint map")
        site_for_map = shape(json.loads(signature["site_geojson"]))
        minx, miny, maxx, maxy = site_for_map.bounds
        site_map = folium.Map(location=[(miny + maxy) / 2, (minx + maxx) / 2], zoom_start=12, tiles="CartoDB positron", control_scale=True)
        if signature["buffer_miles"] > 0:
            buf = buffer_geometry_miles(site_for_map, signature["buffer_miles"])
            folium.GeoJson(mapping(buf), name="Screening buffer", style_function=lambda _: {"color": "#13233D", "weight": 1, "dashArray": "5, 5", "fillOpacity": 0.02}).add_to(site_map)
        folium.GeoJson(mapping(site_for_map), name="Candidate site", style_function=lambda _: {"color": "#E23B3B", "weight": 3, "fillColor": "#E23B3B", "fillOpacity": 0.18}, tooltip=signature["site_name"]).add_to(site_map)
        layer_colors = {"Critical": "#B42318", "High": "#D92D20", "Moderate": "#F79009", "Low": "#1570EF", "Informational": "#667085"}
        visible_layers = 0
        for idx, result in enumerate(results):
            geojson_text = result.get("features_geojson")
            if not geojson_text:
                continue
            try:
                geojson_obj = json.loads(geojson_text)
                if not geojson_obj.get("features"):
                    continue
                fg = folium.FeatureGroup(name=result["name"], show=True)
                color = layer_colors.get(result.get("severity"), "#667085")
                folium.GeoJson(geojson_obj, name=result["name"], style_function=lambda _feature, col=color: {"color": col, "weight": 2, "fillColor": col, "fillOpacity": 0.22}, tooltip=folium.GeoJsonTooltip(fields=[f for f in (geojson_obj.get("features", [{}])[0].get("properties", {}) or {}).keys()][:3]) if (geojson_obj.get("features", [{}])[0].get("properties") or {}) else None).add_to(fg)
                fg.add_to(site_map)
                visible_layers += 1
            except Exception:
                pass
        folium.LayerControl(collapsed=False).add_to(site_map)
        st_folium(site_map, height=620, use_container_width=True, key=f"results_map_{signature['created_at']}", returned_objects=[])
        st.caption(f"Map shows the candidate site and returned constraint features for {visible_layers} layer(s). Some public services cap the number of geometries returned for display; feature counts are queried separately.")
        st.markdown("#### Detailed findings")
        for result in results:
            with st.expander(f"{result.get('status', 'Result')} · {result.get('name', 'Unnamed layer')}"):
                st.write(result.get("explanation", ""))
                if result.get("overlap_acres") is not None:
                    st.write(f"Estimated mapped overlap: **{result['overlap_acres']:,.2f} acres** ({result.get('overlap_pct') or 0:.1f}% of site)." if result.get("site_count", 0) else "No site overlap estimated.")
                if result.get("sample_truncated"):
                    st.warning("The map overlay is a capped sample; use the source service for a complete feature-by-feature review.")
                if result.get("limitation"):
                    st.caption(result["limitation"])
                if result.get("source"):
                    st.markdown(f"[Source / metadata]({result['source']})")
        report_md = build_markdown_report(signature["site_name"], signature["technology"], signature["location_label"], signature["site_area_acres"], signature["buffer_miles"], results, signature["online_enabled"])
        report_col1, report_col2 = st.columns(2)
        with report_col1:
            st.download_button("Download screening report (.md)", data=report_md.encode("utf-8"), file_name="fatal_flaw_screening_report.md", mime="text/markdown", use_container_width=True)
        with report_col2:
            st.download_button("Download results table (.csv)", data=results_to_csv(results), file_name="fatal_flaw_screening_results.csv", mime="text/csv", use_container_width=True)
        st.warning("A negative screen is not a development approval. Verify source coverage and dates, obtain local jurisdictional data, and complete professional environmental, legal, land, aviation and interconnection diligence before making an investment decision.")

with method_tab:
    st.subheader("What this version checks")
    st.markdown("The supplied reference file is a bibliography of datasets and references (pages 47–54), not a set of numeric pass/fail criteria. The platform therefore reports spatial evidence and screening flags rather than silently converting every overlap into a legal fatal flaw.")
    st.markdown("#### Automated public checks")
    st.dataframe(pd.DataFrame([{"Check": l["name"], "Category": l["category"], "Default severity": l["severity"], "Service": l["url"]} for l in AUTO_LAYERS]), hide_index=True, use_container_width=True)
    st.markdown("#### Checks intentionally left open until data is supplied")
    st.markdown("The following reference-driven topics are surfaced as **Not assessed** when a matching layer or review evidence has not been provided:")
    for gap_category, gap_message in REQUIRED_DATA_CHECKS:
        st.markdown(f"- **{gap_category}:** {gap_message}")
    st.markdown("#### Interpretation of results")
    meanings = [
        ("Potential fatal flaw", "A mapped overlap configured as Critical. Escalate promptly to project-specific legal/technical review; not an automatic legal prohibition."),
        ("Major constraint / Review required / Minor constraint", "A mapped overlap based on the layer's configured screening severity."),
        ("Nearby constraint", "One or more mapped features lie within the selected buffer but not inside the actual site polygon."),
        ("No mapped overlap", "No feature was returned by the queried layer for that geometry. This is not proof of absence or a data-coverage guarantee."),
        ("Not assessed", "The service failed, could not be queried, or a needed data layer was not uploaded. Never interpret this as clear."),
    ]
    for label, desc in meanings:
        st.markdown(f"**{label}.** {desc}")
    st.markdown("#### Source inventory based on the provided reference")
    for heading, desc in REFERENCE_CHECKLIST:
        st.markdown(f"**{heading}:** {desc}")
    st.markdown("#### Official starting points")
    official_sources = [
        ("FEMA National Flood Hazard Layer", "https://www.fema.gov/flood-maps/national-flood-hazard-layer"),
        ("USFWS National Wetlands Inventory web mapping services", "https://www.fws.gov/program/national-wetlands-inventory/web-mapping-services"),
        ("USFWS ECOS data services / critical habitat", "https://fis.fws.gov/ecp/services"),
        ("USGS Protected Areas Database (PAD-US) overview and downloads", "https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview"),
        ("USGS National Map web services", "https://apps.nationalmap.gov/services/"),
    ]
    for name, url in official_sources:
        st.markdown(f"- [{name}]({url})")
    st.info("Next production step: add jurisdiction-specific zoning, parcel/title, wetlands/USACE, cultural resources, FAA/DoD, slope, utility/transmission, and interconnection datasets. These are deliberately shown as data requirements, not assumed cleared.")

st.markdown("---")
st.caption("Sunstripe · Site Feasibility & Fatal-Flaw Screening · Preliminary diligence only · GIS results are only as complete and current as their source data.")
