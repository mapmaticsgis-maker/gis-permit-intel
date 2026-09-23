# Worker: scans a single mxd and prints one JSON line to stdout.
# Run with: C:\Python27\ArcGIS10.8\python.exe scan_one_mxd.py <client> <mxd_path>
# Isolated in its own process because arcpy/COM can crash the interpreter on
# some mxds -- one bad file should not take down the whole batch scan.
import arcpy
import json
import os
import sys


def existence_check_path(data_source):
    lower = data_source.lower()
    idx = lower.find(".gdb\\")
    if idx != -1:
        return data_source[:idx + 4]
    return data_source


def main():
    client = sys.argv[1]
    mxd_path = sys.argv[2]

    layer_records = []
    mxd = arcpy.mapping.MapDocument(mxd_path)
    for df in arcpy.mapping.ListDataFrames(mxd):
        for lyr in arcpy.mapping.ListLayers(mxd, "", df):
            if not lyr.supports("DATASOURCE"):
                continue
            data_source = lyr.dataSource
            source_exists = os.path.exists(existence_check_path(data_source))
            layer_records.append({
                "client": client,
                "mxd_path": mxd_path,
                "layer_name": lyr.name,
                "data_source": data_source,
                "source_exists": source_exists,
            })
    del mxd

    print(json.dumps({"mxd_path": mxd_path, "records": layer_records}))


if __name__ == "__main__":
    main()
