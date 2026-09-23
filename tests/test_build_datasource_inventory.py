from scripts.mxd_inventory.build_datasource_inventory import (
    classify_source,
    group_shared_sources,
    build_workbook,
)

CLIENT_ROOTS = {
    "RROG": r"C:\GIS\CLIENT\RROG",
    "DOXA": r"C:\GIS\CLIENT\DOXA",
}


def test_classify_source_broken_takes_priority():
    assert classify_source("RROG", r"C:\GIS\CLIENT\DOXA\missing.shp", False, CLIENT_ROOTS) == "Broken"


def test_classify_source_cross_client():
    assert classify_source("RROG", r"C:\GIS\CLIENT\DOXA\ZADECK\STICKS.shp", True, CLIENT_ROOTS) == "Cross-Client"


def test_classify_source_outside_gis():
    assert classify_source("RROG", r"C:\0-CLIENTS\DOXA\ZADECK\STICKS.shp", True, CLIENT_ROOTS) == "Outside C:\\GIS"


def test_classify_source_shared_boundary_not_flagged():
    assert classify_source("RROG", r"C:\GIS\BOUNDARY\COUNTY\tl_2024_us_county.shp", True, CLIENT_ROOTS) is None


def test_classify_source_own_folder_not_flagged():
    assert classify_source("RROG", r"C:\GIS\CLIENT\RROG\LINE2.shp", True, CLIENT_ROOTS) is None


RECORDS = [
    {"client": "RROG", "mxd_path": r"C:\GIS\CLIENT\RROG\a.mxd", "layer_name": "COUNTY",
     "data_source": r"C:\GIS\BOUNDARY\COUNTY\tl_2024_us_county.shp", "source_exists": True},
    {"client": "RROG", "mxd_path": r"C:\GIS\CLIENT\RROG\b.mxd", "layer_name": "COUNTY",
     "data_source": r"C:\GIS\BOUNDARY\COUNTY\tl_2024_us_county.shp", "source_exists": True},
    {"client": "RROG", "mxd_path": r"C:\GIS\CLIENT\RROG\a.mxd", "layer_name": "UNIQUE",
     "data_source": r"C:\GIS\CLIENT\RROG\a_only.shp", "source_exists": True},
]


def test_group_shared_sources_only_includes_multi_reference_sources():
    grouped = group_shared_sources(RECORDS)
    assert len(grouped) == 1
    assert grouped[0]["data_source"] == r"C:\GIS\BOUNDARY\COUNTY\tl_2024_us_county.shp"
    assert grouped[0]["reference_count"] == 2
    assert set(grouped[0]["referencing_mxds"]) == {r"C:\GIS\CLIENT\RROG\a.mxd", r"C:\GIS\CLIENT\RROG\b.mxd"}


SURVEY = {
    "generated_date": "2026-09-23",
    "client_roots": CLIENT_ROOTS,
    "records": RECORDS
    + [
        {"client": "RROG", "mxd_path": r"C:\GIS\CLIENT\RROG\c.mxd", "layer_name": "STICKS",
         "data_source": r"C:\0-CLIENTS\DOXA\ZADECK\STICKS.shp", "source_exists": True},
    ],
    "errors": [],
}


def test_build_workbook_has_three_sheets():
    wb = build_workbook(SURVEY)
    assert wb.sheetnames == ["Raw", "Shared Sources", "Flags"]


def test_build_workbook_raw_sheet_row_count():
    wb = build_workbook(SURVEY)
    # header + 4 records
    assert wb["Raw"].max_row == 5


def test_build_workbook_flags_sheet_has_outside_gis_row():
    wb = build_workbook(SURVEY)
    flags = wb["Flags"]
    rows = list(flags.iter_rows(min_row=2, values_only=True))
    assert any(row[4] == "Outside C:\\GIS" and row[3] == r"C:\0-CLIENTS\DOXA\ZADECK\STICKS.shp" for row in rows)
