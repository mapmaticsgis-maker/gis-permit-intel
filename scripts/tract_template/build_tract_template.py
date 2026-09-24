import os
import shapefile

OUT_DIR = r"C:\GIS\TEMPLATES\TRACT"
OUT_PATH = os.path.join(OUT_DIR, "TRACT_TEMPLATE.shp")
PRJ_TEXT = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)

# (name, type, length, decimal) -- name capped at 10 chars (shapefile DBF limit,
# matches the convention already used in DLS_MASTER_JOIN / RROG tract shapefiles)
FIELDS = [
    # -- identification --
    ("TRACT_NO", "C", 20, 0),
    ("UNIT_NO", "C", 20, 0),
    ("PROSPECT", "C", 30, 0),
    ("STATE", "C", 2, 0),
    ("COUNTY", "C", 30, 0),
    ("SEC", "C", 6, 0),
    ("TWP", "C", 6, 0),
    ("RNG", "C", 6, 0),
    ("SURVEY", "C", 30, 0),
    # -- ownership --
    ("OWNER_NAME", "C", 75, 0),
    ("MAIL_ADDR", "C", 100, 0),
    ("CONTACT", "C", 50, 0),
    ("MIN_OWN", "N", 9, 4),
    # -- acreage --
    ("GROSS_AC", "N", 12, 4),
    ("NET_AC", "N", 12, 4),
    ("MIN_INT", "N", 9, 6),
    ("UNIT_PCT", "N", 9, 6),
    # -- lease --
    ("LESSOR", "C", 75, 0),
    ("LESSEE", "C", 75, 0),
    ("LSE_DATE", "D", 8, 0),
    ("EXP_DATE", "D", 8, 0),
    ("ROYALTY", "N", 6, 4),
    ("BONUS", "N", 12, 2),
    ("INST_NO", "C", 20, 0),
    ("VOL_PG", "C", 20, 0),
    ("DEPTH", "C", 30, 0),
    ("PUGH", "C", 50, 0),
    # -- title / status --
    ("STATUS", "C", 30, 0),
    ("TITLE_ST", "C", 30, 0),
    ("ABS_NO", "C", 15, 0),
    ("ATTY", "C", 50, 0),
    ("LANDMAN", "C", 50, 0),
    # -- admin / metadata --
    ("SOURCE", "C", 50, 0),
    ("SRC_DATE", "D", 8, 0),
    ("DATE_ADD", "D", 8, 0),
    ("DATE_EDIT", "D", 8, 0),
    ("COMMENTS", "C", 254, 0),
]

assert all(len(name) <= 10 for name, *_ in FIELDS), "shapefile field names must be <=10 chars"


def main():
    if not os.path.exists(OUT_DIR):
        os.makedirs(OUT_DIR)

    with shapefile.Writer(OUT_PATH, shapeType=shapefile.POLYGON) as w:
        for name, ftype, length, decimal in FIELDS:
            w.field(name, ftype, size=length, decimal=decimal)
        # zero-feature shapefile -- a valid, empty template to copy per
        # project and digitize/populate from scratch.

    with open(OUT_PATH.replace(".shp", ".prj"), "w") as f:
        f.write(PRJ_TEXT)

    print("Wrote template with {0} fields to {1}".format(len(FIELDS), OUT_PATH))


if __name__ == "__main__":
    main()
