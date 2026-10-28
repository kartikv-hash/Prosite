"""Exportable site screening report builders."""
from __future__ import annotations

from datetime import datetime, timezone
import pandas as pd


def build_markdown_report(site_name: str, technology: str, location: str, site_acres: float, buffer_miles: float, results: list[dict], online_enabled: bool) -> str:
    created = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    critical = sum(1 for r in results if r.get("status") == "Potential fatal flaw")
    major = sum(1 for r in results if r.get("status") == "Major constraint")
    nearby = sum(1 for r in results if r.get("status") == "Nearby constraint")
    not_assessed = sum(1 for r in results if r.get("status") == "Not assessed")
    lines = [
        f"# Preliminary Site Feasibility & Fatal-Flaw Screen: {site_name}",
        "",
        f"**Generated:** {created}  ",
        f"**Technology:** {technology}  ",
        f"**Location supplied:** {location or 'Not supplied'}  ",
        f"**Mapped site area:** {site_acres:,.2f} acres  ",
        f"**Screening buffer:** {buffer_miles:g} mile(s)  ",
        f"**Online public layer queries:** {'Enabled' if online_enabled else 'Disabled'}",
        "",
        "## Executive summary",
        "",
        f"- Potential fatal-flaw flags: **{critical}**",
        f"- Major constraints: **{major}**",
        f"- Nearby constraints (within buffer only): **{nearby}**",
        f"- Checks not assessed: **{not_assessed}**",
        "",
        "> **Important:** This is an early-stage GIS screen, not a permitting determination, title opinion, wetland delineation, interconnection study, or legal conclusion. A mapped overlap is a diligence trigger, not automatically a fatal flaw. A result of 'No mapped overlap' means no feature was returned by the queried data source; it does not prove the constraint is absent.",
        "",
        "## Check-by-check results",
        "",
        "| Category | Check | Severity | Result | Site features | Buffer-only | Overlap (acres) | Data status |",
        "|---|---|---:|---|---:|---:|---:|---|",
    ]
    for r in results:
        overlap = r.get("overlap_acres")
        overlap_text = "—" if overlap is None else f"{overlap:,.2f}"
        site_count = "—" if r.get("site_count") is None else str(r.get("site_count"))
        near_count = "—" if r.get("nearby_count") is None else str(r.get("nearby_count"))
        fields = [r.get("category", ""), r.get("name", ""), r.get("severity", ""), r.get("status", ""), site_count, near_count, overlap_text, r.get("data_status", "")]
        fields = [str(v).replace("|", "\\|").replace("\n", " ") for v in fields]
        lines.append("| " + " | ".join(fields) + " |")
    lines += ["", "## Findings and data limitations", ""]
    for r in results:
        lines.append(f"### {r.get('name', 'Unnamed check')}")
        lines.append("")
        lines.append(str(r.get("explanation", "")))
        if r.get("description"):
            lines.append(f"\n**Purpose:** {r['description']}")
        if r.get("limitation"):
            lines.append(f"\n**Limitation:** {r['limitation']}")
        if r.get("source"):
            lines.append(f"\n**Source:** {r['source']}")
        lines.append("")
    lines += [
        "## Recommended next steps",
        "",
        "1. Review every 'Potential fatal flaw', 'Major constraint', and 'Nearby constraint' with the relevant environmental, land, planning, aviation, or grid specialist.",
        "2. Obtain current county/state datasets for zoning, parcels/title, access/easements, local wetlands, cultural resources, floodplain ordinances, and permitting triggers.",
        "3. Obtain utility / ISO / interconnection evidence for substation capacity, queue position, transmission access, study scope, and upgrade cost. Proximity to a line is not proof of available capacity.",
        "4. Record the source date, coverage, coordinate reference system, and reviewer decision for every uploaded layer. Re-run the screen with the final site boundary and a documented buffer.",
        "",
        "## Interpretation guide",
        "",
        "- **Potential fatal flaw:** a high-consequence mapped overlap that needs prompt project-specific review; not an automatic legal conclusion.",
        "- **Major constraint / Review required / Minor constraint:** overlap detected based on the configured severity.",
        "- **Nearby constraint:** mapped feature lies within the selected buffer but did not intersect the actual site polygon.",
        "- **No mapped overlap:** no intersecting feature returned by that layer; source coverage and completeness still matter.",
        "- **Not assessed:** source service failed or data was not supplied. Do not interpret as cleared.",
        "",
        "---",
        "Prepared by the Site Feasibility & Fatal-Flaw Screening app. Use the report as a preliminary diligence aid only.",
    ]
    return "\n".join(lines)


def results_to_csv(results: list[dict]) -> bytes:
    df = pd.DataFrame(results)
    if df.empty:
        return b""
    for col in ("features_geojson",):
        if col in df.columns:
            df = df.drop(columns=[col])
    return df.to_csv(index=False).encode("utf-8")
