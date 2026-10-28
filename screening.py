"""Core geospatial loading, spatial screening, and ArcGIS REST query helpers."""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, mapping
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

ACRES_PER_SQM = 4046.8564224
MAX_QUERY_FEATURES = 250


def _repair_geometry(geom):
    if geom is None or geom.is_empty:
        return None
    try:
        if not geom.is_valid:
            geom = geom.make_valid()
    except Exception:
        try:
            geom = geom.buffer(0)
        except Exception:
            return None
    if geom is None or geom.is_empty:
        return None
    return geom


def read_geodata_from_bytes(file_bytes: bytes, filename: str) -> gpd.GeoDataFrame:
    """Read a GIS upload into WGS84. Zip files are treated as zipped shapefiles."""
    safe_name = os.path.basename(filename or "upload.geojson")
    suffix = os.path.splitext(safe_name)[1].lower()
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, safe_name)
        with open(path, "wb") as stream:
            stream.write(file_bytes)
        if suffix == ".zip":
            source = f"zip://{path}"
        else:
            source = path
        gdf = gpd.read_file(source)
    if gdf.empty:
        raise ValueError("The uploaded file contains no features.")
    if gdf.geometry is None:
        raise ValueError("The uploaded dataset does not contain a geometry column.")
    if gdf.crs is None:
        if suffix in {".geojson", ".json", ".kml"}:
            gdf = gdf.set_crs("EPSG:4326")
        else:
            raise ValueError("The uploaded layer has no coordinate reference system. Include its .prj file or re-export it with a CRS.")
    gdf = gdf.to_crs("EPSG:4326")
    gdf = gdf[gdf.geometry.notna()].copy()
    gdf["geometry"] = gdf.geometry.apply(_repair_geometry)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    if gdf.empty:
        raise ValueError("No usable geometries were found in the uploaded file.")
    return gdf


def site_geometry_from_gdf(gdf: gpd.GeoDataFrame):
    """Union polygonal geometries and reject points/lines as site boundaries."""
    parts = []
    for geom in gdf.geometry:
        geom = _repair_geometry(geom)
        if geom is None:
            continue
        if isinstance(geom, Polygon):
            parts.append(geom)
        elif isinstance(geom, MultiPolygon):
            parts.extend(list(geom.geoms))
        elif isinstance(geom, GeometryCollection):
            for sub in geom.geoms:
                if isinstance(sub, Polygon):
                    parts.append(sub)
                elif isinstance(sub, MultiPolygon):
                    parts.extend(list(sub.geoms))
    if not parts:
        raise ValueError("The site boundary must contain at least one Polygon or MultiPolygon.")
    geom = _repair_geometry(unary_union(parts))
    if geom is None or geom.is_empty:
        raise ValueError("The site boundary could not be repaired. Re-export the boundary from a GIS application.")
    return geom


def geometry_area_acres(geom) -> float:
    """Compute area in an estimated local UTM CRS to avoid degree-based area math."""
    if geom is None or geom.is_empty:
        return 0.0
    series = gpd.GeoSeries([geom], crs="EPSG:4326")
    projected_crs = series.estimate_utm_crs()
    if projected_crs is None:
        projected_crs = "EPSG:5070"
    return float(series.to_crs(projected_crs).area.iloc[0] / ACRES_PER_SQM)


def buffer_geometry_miles(geom, miles: float):
    if not miles or miles <= 0:
        return geom
    series = gpd.GeoSeries([geom], crs="EPSG:4326")
    projected_crs = series.estimate_utm_crs() or "EPSG:5070"
    projected = series.to_crs(projected_crs).iloc[0]
    buffered = projected.buffer(float(miles) * 1609.344)
    return gpd.GeoSeries([buffered], crs=projected_crs).to_crs("EPSG:4326").iloc[0]


def _as_polygons(geom):
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    if isinstance(geom, GeometryCollection):
        polygons = []
        for g in geom.geoms:
            polygons.extend(_as_polygons(g))
        return polygons
    raise ValueError("ArcGIS spatial queries require polygonal site geometry.")


def to_esri_polygon(geom) -> dict[str, Any]:
    """Convert a WGS84 Shapely polygon to the Esri JSON polygon schema."""
    rings = []
    for poly in _as_polygons(geom):
        # Esri rings convention: outer ring clockwise, holes counter-clockwise.
        poly = orient(poly, sign=-1.0)
        rings.append([[float(x), float(y)] for x, y in poly.exterior.coords])
        for ring in poly.interiors:
            rings.append([[float(x), float(y)] for x, y in ring.coords])
    return {"rings": rings, "spatialReference": {"wkid": 4326}}


def _arcgis_query(service_layer_url: str, geom, params_extra: dict[str, Any] | None = None, timeout: int = 25) -> dict[str, Any]:
    endpoint = service_layer_url.rstrip("/")
    if not endpoint.endswith("/query"):
        endpoint = endpoint + "/query"
    params: dict[str, Any] = {
        "where": "1=1",
        "geometry": json.dumps(to_esri_polygon(geom), separators=(",", ":")),
        "geometryType": "esriGeometryPolygon",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "f": "json",
    }
    if params_extra:
        params.update(params_extra)
    response = requests.post(endpoint, data=params, timeout=timeout, headers={"User-Agent": "Sunstripe-FatalFlaw-Screening/1.0"})
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and payload.get("error"):
        error = payload["error"]
        message = error.get("message", "ArcGIS query failed") if isinstance(error, dict) else str(error)
        details = error.get("details", []) if isinstance(error, dict) else []
        raise RuntimeError(f"{message} {'; '.join(map(str, details))}".strip())
    return payload


def query_arcgis_count(service_layer_url: str, geom, timeout: int = 25) -> int:
    payload = _arcgis_query(service_layer_url, geom, {"returnCountOnly": "true", "returnGeometry": "false"}, timeout=timeout)
    if "count" not in payload:
        raise RuntimeError("The service did not return a feature count.")
    return int(payload["count"])


def query_arcgis_features(service_layer_url: str, geom, max_features: int = MAX_QUERY_FEATURES, timeout: int = 25) -> tuple[gpd.GeoDataFrame, bool]:
    payload = _arcgis_query(
        service_layer_url,
        geom,
        {
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": 4326,
            "resultRecordCount": int(max_features),
            "resultOffset": 0,
            "f": "geojson",
        },
        timeout=timeout,
    )
    features = payload.get("features", [])
    truncated = bool(payload.get("exceededTransferLimit", False)) or len(features) >= max_features
    if not features:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"), truncated
    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    gdf = gdf[gdf.geometry.notna()].copy()
    return gdf, truncated


def _area_overlap(site_geom, layer_gdf: gpd.GeoDataFrame, full_feature_set: bool) -> tuple[float | None, float | None]:
    """Return overlap acres and site percent for polygonal layers, if meaningful."""
    if layer_gdf is None or layer_gdf.empty or not full_feature_set:
        return None, None
    polygon_types = {"Polygon", "MultiPolygon"}
    if not set(layer_gdf.geometry.geom_type.dropna()).intersection(polygon_types):
        return None, None
    try:
        series = gpd.GeoSeries([site_geom], crs="EPSG:4326")
        area_crs = series.estimate_utm_crs() or "EPSG:5070"
        site_area_geom = series.to_crs(area_crs).iloc[0]
        layer = layer_gdf.to_crs(area_crs)
        layer_union = unary_union([g for g in layer.geometry if g is not None and not g.is_empty])
        overlap_area_m2 = site_area_geom.intersection(layer_union).area
        site_area_m2 = site_area_geom.area
        acres = float(overlap_area_m2 / ACRES_PER_SQM)
        pct = float(100.0 * overlap_area_m2 / site_area_m2) if site_area_m2 else 0.0
        return acres, pct
    except Exception:
        return None, None


def _status(site_count: int, buffer_count: int, severity: str) -> tuple[str, str]:
    if site_count > 0:
        status_map = {
            "Critical": "Potential fatal flaw",
            "High": "Major constraint",
            "Moderate": "Review required",
            "Low": "Minor constraint",
            "Informational": "Informational overlap",
        }
        return status_map.get(severity, "Review required"), "Mapped feature intersects the site boundary."
    if buffer_count > 0:
        return "Nearby constraint", "Mapped feature is within the selected screening buffer but outside the site boundary."
    return "No mapped overlap", "No intersecting feature was returned by this layer for the queried area. This is not proof that the subject is absent on the ground."


def run_online_check(layer_config: dict[str, Any], site_geom, buffer_geom) -> dict[str, Any]:
    """Run a public ArcGIS REST screen and return a report-ready result record."""
    try:
        site_count = query_arcgis_count(layer_config["url"], site_geom)
        buffer_count = site_count if buffer_geom.equals(site_geom) else query_arcgis_count(layer_config["url"], buffer_geom)
        query_geom = site_geom if site_count > 0 else buffer_geom
        query_count = site_count if site_count > 0 else buffer_count
        features_gdf, truncated = query_arcgis_features(layer_config["url"], query_geom) if query_count > 0 else (gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"), False)
        overlap_acres, overlap_pct = _area_overlap(site_geom, features_gdf, not truncated and (site_count <= len(features_gdf))) if site_count > 0 else (0.0, 0.0)
        status, explanation = _status(site_count, buffer_count, layer_config["severity"])
        if truncated:
            explanation += f" The map/sample is capped at {MAX_QUERY_FEATURES} features; the service count is separate and may be higher."
        return {
            "key": layer_config["key"],
            "name": layer_config["name"],
            "category": layer_config["category"],
            "severity": layer_config["severity"],
            "source": layer_config["source_url"],
            "service_url": layer_config["url"],
            "description": layer_config["description"],
            "limitation": layer_config["limitation"],
            "site_count": site_count,
            "buffer_count": buffer_count,
            "nearby_count": max(0, buffer_count - site_count),
            "status": status,
            "explanation": explanation,
            "overlap_acres": overlap_acres,
            "overlap_pct": overlap_pct,
            "features_geojson": features_gdf.to_json(drop_id=True) if not features_gdf.empty else None,
            "sample_truncated": truncated,
            "data_status": "Assessed",
        }
    except Exception as exc:
        return {
            "key": layer_config.get("key", "online_layer"),
            "name": layer_config.get("name", "Online GIS layer"),
            "category": layer_config.get("category", "Other constraint layer"),
            "severity": layer_config.get("severity", "Moderate"),
            "source": layer_config.get("source_url", ""),
            "service_url": layer_config.get("url", ""),
            "description": layer_config.get("description", ""),
            "limitation": layer_config.get("limitation", ""),
            "site_count": None,
            "buffer_count": None,
            "nearby_count": None,
            "status": "Not assessed",
            "explanation": f"The online service could not be queried: {type(exc).__name__}: {exc}",
            "overlap_acres": None,
            "overlap_pct": None,
            "features_geojson": None,
            "sample_truncated": False,
            "data_status": "Service error",
        }


def run_local_check(layer_name: str, category: str, severity: str, source_name: str, layer_gdf: gpd.GeoDataFrame, site_geom, buffer_geom) -> dict[str, Any]:
    """Spatially screen a locally uploaded constraint layer against the site/buffer."""
    layer_gdf = layer_gdf.to_crs("EPSG:4326") if layer_gdf.crs is not None else layer_gdf.set_crs("EPSG:4326")
    safe_geom = layer_gdf.geometry.notna() & ~layer_gdf.geometry.is_empty
    layer_gdf = layer_gdf.loc[safe_geom].copy()
    try:
        buffer_mask = layer_gdf.geometry.intersects(buffer_geom)
        nearby_gdf = layer_gdf.loc[buffer_mask].copy()
        site_mask = layer_gdf.geometry.intersects(site_geom)
        site_gdf = layer_gdf.loc[site_mask].copy()
    except Exception as exc:
        raise ValueError(f"Could not intersect {source_name} with the site boundary: {exc}") from exc
    site_count, buffer_count = int(len(site_gdf)), int(len(nearby_gdf))
    status, explanation = _status(site_count, buffer_count, severity)
    if site_count == 0 and buffer_count == 0:
        features_to_map = nearby_gdf
    elif site_count > 0:
        features_to_map = site_gdf
    else:
        features_to_map = nearby_gdf
    overlap_acres, overlap_pct = _area_overlap(site_geom, site_gdf, True) if site_count > 0 else (0.0, 0.0)
    return {
        "key": f"local_{source_name}",
        "name": layer_name,
        "category": category,
        "severity": severity,
        "source": source_name,
        "service_url": "",
        "description": f"User-provided GIS layer: {source_name}",
        "limitation": "User-provided data; confirm source, publication date, accuracy, coverage, and applicable rights/metadata.",
        "site_count": site_count,
        "buffer_count": buffer_count,
        "nearby_count": max(0, buffer_count - site_count),
        "status": status,
        "explanation": explanation,
        "overlap_acres": overlap_acres,
        "overlap_pct": overlap_pct,
        "features_geojson": features_to_map.to_json(drop_id=True) if not features_to_map.empty else None,
        "sample_truncated": False,
        "data_status": "User layer assessed",
    }


def result_table(results: list[dict[str, Any]]) -> pd.DataFrame:
    columns = ["category", "name", "severity", "status", "site_count", "nearby_count", "overlap_acres", "overlap_pct", "data_status", "source"]
    df = pd.DataFrame(results)
    if df.empty:
        return pd.DataFrame(columns=columns)
    for col in columns:
        if col not in df.columns:
            df[col] = None
    df = df[columns].copy()
    df.rename(columns={
        "category": "Constraint category",
        "name": "Check",
        "severity": "Screening severity",
        "status": "Screening result",
        "site_count": "Features intersecting site",
        "nearby_count": "Features in buffer only",
        "overlap_acres": "Mapped overlap (acres)",
        "overlap_pct": "Site overlap (%)",
        "data_status": "Data status",
        "source": "Source",
    }, inplace=True)
    return df
