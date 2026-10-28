"""Authoritative public map services used for the default U.S. screening checks."""

AUTO_LAYERS = [
    {
        "key": "fema_nfhl",
        "name": "FEMA flood hazard zones",
        "category": "Flood risk",
        "severity": "High",
        "url": "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28",
        "source_url": "https://www.fema.gov/flood-maps/national-flood-hazard-layer",
        "description": "Screens the candidate site against mapped FEMA National Flood Hazard Layer flood zones.",
        "limitation": "Flood mapping may be incomplete or preliminary in some locations; verify against the current FEMA Flood Map Service Center and local floodplain administrator.",
    },
    {
        "key": "nwi_wetlands",
        "name": "National Wetlands Inventory",
        "category": "Wetlands and waters",
        "severity": "High",
        "url": "https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer/0",
        "source_url": "https://www.fws.gov/program/national-wetlands-inventory/web-mapping-services",
        "description": "Screens against mapped National Wetlands Inventory wetland polygons.",
        "limitation": "NWI is a screening inventory, not a jurisdictional wetland delineation or a USACE jurisdictional determination.",
    },
    {
        "key": "critical_habitat_final",
        "name": "USFWS final critical habitat",
        "category": "Protected species and habitat",
        "severity": "Critical",
        "url": "https://services.arcgis.com/QVENGdaPbd4LUkLV/arcgis/rest/services/USFWS_Critical_Habitat/FeatureServer/0",
        "source_url": "https://fis.fws.gov/ecp/services",
        "description": "Screens against mapped final ESA critical habitat polygons.",
        "limitation": "An overlap triggers species / permitting review; it does not by itself determine project eligibility or establish an automatic legal prohibition.",
    },
    {
        "key": "critical_habitat_proposed",
        "name": "USFWS proposed critical habitat",
        "category": "Protected species and habitat",
        "severity": "High",
        "url": "https://services.arcgis.com/QVENGdaPbd4LUkLV/arcgis/rest/services/USFWS_Critical_Habitat/FeatureServer/2",
        "source_url": "https://fis.fws.gov/ecp/services",
        "description": "Screens against mapped proposed ESA critical habitat polygons.",
        "limitation": "Proposed boundaries may change. Confirm the current status and project-specific implications with USFWS.",
    },
]

# Categories supported for user-provided GIS layers. These reflect themes in the
# reference bibliography; they do not imply that each layer is automatically queried.
CONSTRAINT_CATEGORIES = [
    "Flood risk",
    "Wetlands and waters",
    "Protected species and habitat",
    "Protected lands and conservation easements",
    "Land use, zoning and agricultural land",
    "Parcels, ownership and access",
    "Transmission lines and substations",
    "Airports, FAA and aviation",
    "Military and defense areas",
    "Tribal lands and cultural resources",
    "Historic sites and battlefields",
    "Karst, sinkholes and geology",
    "Slope, soils and landslides",
    "Wildfire, storms and natural hazards",
    "Landfills, mines and contamination",
    "Pipelines, gas facilities and industrial sites",
    "Roads, rail and transport access",
    "Community, population and environmental justice",
    "Energy communities and incentives",
    "Other constraint layer",
]

SEVERITIES = ["Critical", "High", "Moderate", "Low", "Informational"]

SEVERITY_HELP = {
    "Critical": "Potential fatal flaw — requires project-specific legal, technical, and permitting review.",
    "High": "Major constraint — may materially affect layout, permits, cost, schedule, or viability.",
    "Moderate": "Review required — possible avoidance, mitigation, or design response.",
    "Low": "Informational — track during diligence.",
    "Informational": "Context only — not scored as a fatal flaw.",
}

# Supplemental screening topics drawn from the supplied bibliography and intended
# to make missing data visible instead of implying these subjects have been cleared.
REFERENCE_CHECKLIST = [
    ("Environmental / ecological", "Wetlands and waterways; protected areas; listed species and critical habitat; conservation easements; karst; scenic rivers/trails; coastal/marine resources; land cover and soils."),
    ("Flooding / natural hazards", "FEMA flood hazard zones; floodway; landslide susceptibility; slope; wildfire and severe-weather exposure; levees; coastal barriers."),
    ("Land / permits / local controls", "Parcel ownership and access; county/city zoning; agricultural restrictions; state/local environmental resources; USACE permitting context; historic/cultural resources; tribal lands."),
    ("Aviation / defense / safety", "FAA aeronautical constraints; airports; military installations and training areas; wind-specific eagle and wildlife review."),
    ("Infrastructure / constructability", "Transmission lines and substations; utility service territories; roads and rail; pipelines; gas/electric facilities; landfills, mines and wastewater facilities."),
    ("Community / policy / economics", "Population density; EPA environmental-justice indicators; IRA energy-community / low-income bonus areas; land values and parcel comparables."),
]


# High-value items from the reference bibliography that require local / project
# data or specialist review and are not implied to be assessed by the default layers.
REQUIRED_DATA_CHECKS = [
    ("Protected lands and conservation easements", "PAD-US / conservation easements / agency land overlays were not uploaded or connected."),
    ("Land use, zoning and agricultural land", "Confirm county and municipal zoning, comprehensive plans, agricultural restrictions, and local siting rules."),
    ("Parcels, ownership and access", "Confirm parcel boundaries, title, easements, access rights, and site control."),
    ("Transmission lines and substations", "Upload a current transmission / substation layer; proximity is not proof of available capacity."),
    ("Interconnection capacity and cost", "Not resolved by a map overlay. Obtain utility/ISO queue, available capacity, study scope, upgrade cost and schedule evidence."),
    ("Airports, FAA and aviation", "Confirm airport influence areas, FAA review triggers, and wind turbine lighting / obstruction requirements where relevant."),
    ("Military and defense areas", "Check military installations, training areas, radar or mission constraints where relevant."),
    ("Tribal lands and cultural resources", "Confirm tribal interests, consultation requirements, and cultural-resource sensitivity using appropriate authorities."),
    ("Historic sites and battlefields", "Check applicable historic registers, battlefield inventories, and state/local review requirements."),
    ("Karst, sinkholes and geology", "Use site-specific geology / karst data and geotechnical review where relevant."),
    ("Slope, soils and landslides", "Check DEM-derived slope, soils, landslide susceptibility, and geotechnical constraints."),
    ("Wildfire, storms and natural hazards", "Check current wildfire, hail, storm, coastal, levee, and other hazard layers relevant to the site."),
    ("Landfills, mines and contamination", "Check permitted facilities, abandoned mines, solid-waste sites, contaminated lands, and required buffers."),
    ("Pipelines, gas facilities and industrial sites", "Check current pipeline / gas facility / industrial land-use layers and required safety setbacks."),
    ("Roads, rail and transport access", "Check legal access, road capacity, rail/haul routes, construction logistics, and permit limits."),
    ("Community, population and environmental justice", "Review current population and environmental-justice datasets plus local engagement context."),
    ("Energy communities and incentives", "Verify current eligibility maps and tax-credit requirements independently before relying on incentives."),
]
