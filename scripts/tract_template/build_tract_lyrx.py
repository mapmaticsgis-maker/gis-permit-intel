import json
import os

OUT_PATH = r"C:\GIS\TEMPLATES\TRACT\TRACT_TEMPLATE.lyrx"

# (status value, RGB) -- values are the real vocabulary found across
# DLS/RROG/DOXA STATUS fields (survey done 2026-09-23), normalized to Title
# Case since casing was inconsistent across projects (e.g. "NEGOTIATING" vs
# "Negotiating"). Order = light/early -> dark/late in the leasing lifecycle.
CATEGORIES = [
    ("Open", (211, 211, 211)),
    ("Attempting to Contact", (255, 255, 190)),
    ("Contact Made", (255, 230, 140)),
    ("Negotiating", (255, 170, 0)),
    ("Committed", (170, 220, 140)),
    ("Signed", (100, 190, 100)),
    ("Leased", (30, 140, 30)),
    ("Partial HBP", (100, 180, 220)),
    ("Competitor", (230, 120, 120)),
    ("Rejected", (180, 30, 30)),
]


def color(rgb):
    r, g, b = rgb
    return {"type": "CIMRGBColor", "values": [r, g, b, 100]}


def polygon_symbol(rgb):
    return {
        "type": "CIMSymbolReference",
        "symbol": {
            "type": "CIMPolygonSymbol",
            "symbolLayers": [
                {
                    "type": "CIMSolidStroke",
                    "enable": True,
                    "capStyle": "Round",
                    "joinStyle": "Round",
                    "lineStyle3D": "Strip",
                    "miterLimit": 10,
                    "width": 0.8,
                    "color": {"type": "CIMRGBColor", "values": [60, 60, 60, 100]},
                },
                {
                    "type": "CIMSolidFill",
                    "enable": True,
                    "color": color(rgb),
                },
            ],
        },
    }


def build_unique_value_classes():
    classes = []
    for value, rgb in CATEGORIES:
        classes.append({
            "type": "CIMUniqueValueClass",
            "label": value,
            "patch": "Default",
            "symbol": polygon_symbol(rgb),
            "values": [{"type": "CIMUniqueValue", "fieldValues": [value]}],
        })
    return classes


def build_renderer():
    return {
        "type": "CIMUniqueValueRenderer",
        "field1": "STATUS",
        "colorRamp": None,
        "useDefaultSymbol": True,
        "defaultLabel": "<Other / Not Set>",
        "defaultSymbol": polygon_symbol((255, 255, 255)),
        "groups": [
            {
                "type": "CIMUniqueValueGroup",
                "heading": "STATUS",
                "classes": build_unique_value_classes(),
            }
        ],
        "fields": ["STATUS"],
    }


def build_layer_document():
    feature_layer = {
        "type": "CIMFeatureLayer",
        "name": "TRACT_TEMPLATE",
        "uRI": "CIMPATH=map/tract_template.xml",
        "sourceModifiedTime": {"type": "TimeInstant"},
        "useSourceMetadata": True,
        "description": "TRACT_TEMPLATE",
        "layerElevation": {"type": "CIMLayerElevationSurface", "mapElevationID": "{DEFAULT}"},
        "expanded": True,
        "layerType": "Operational",
        "showLegends": True,
        "visibility": True,
        "displayCacheType": "Permanent",
        "maxDisplayCacheAge": 5,
        "showPopups": True,
        "serviceLayerID": -1,
        "refreshRate": -1,
        "refreshRateUnit": "esriTimeUnitSeconds",
        "blendingMode": "Alpha",
        "allowDrapingOnIntegratedMesh": True,
        "featureTable": {
            "type": "CIMFeatureTable",
            "displayField": "TRACT_NO",
            "editable": True,
            "dataConnection": {
                "type": "CIMStandardDataConnection",
                "workspaceConnectionString": r"DATABASE=.",
                "workspaceFactory": "Shapefile",
                "dataset": "TRACT_TEMPLATE.shp",
                "datasetType": "esriDTFeatureClass",
            },
            "studyAreaSpatialRel": "esriSpatialRelUndefined",
            "searchOrder": "esriSearchOrderSpatial",
        },
        "htmlPopupEnabled": True,
        "selectable": True,
        "featureCacheType": "Session",
        "displayFiltersType": "ByScale",
        "featureBlendingMode": "Alpha",
        "renderer": build_renderer(),
        "scaleSymbols": True,
        "snappable": True,
    }

    return {
        "type": "CIMLayerDocument",
        "version": "2.9.0",
        "build": 32739,
        "layers": ["CIMPATH=map/tract_template.xml"],
        "layerDefinitions": [feature_layer],
        "binaryReferences": [],
        "elevationSurfaceLayerURIs": [],
    }


def main():
    out_dir = os.path.dirname(OUT_PATH)
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    with open(OUT_PATH, "w") as f:
        json.dump(build_layer_document(), f, indent=2)
    print("Wrote {0} categories to {1}".format(len(CATEGORIES), OUT_PATH))


if __name__ == "__main__":
    main()
