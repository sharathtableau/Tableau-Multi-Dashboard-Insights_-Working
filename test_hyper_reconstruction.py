"""
Standalone test: Parse the sample TWBX and reconstruct CSV for the "Dashboard" dashboard.

Usage:
    python test_hyper_reconstruction.py

Expected output: CSV sections for each worksheet in the "Dashboard" dashboard,
showing grouped/aggregated data reconstructed from the Hyper extract.
"""
import sys, os, zipfile, io, logging, xml.etree.ElementTree as ET

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s",
    stream=sys.stdout
)

# ── Locate the sample workbook ──────────────────────────────────────────────
TWBX_PATH = os.path.expanduser(
    "~/Downloads/E-Commerce (Software) Sales Dashboard #VOTD.twbx"
)
DASHBOARD_NAME = "Dashboard"

if not os.path.exists(TWBX_PATH):
    print(f"ERROR: File not found: {TWBX_PATH}")
    sys.exit(1)

print(f"\n{'='*70}")
print(f"  Testing Hyper Reconstruction")
print(f"  Workbook : {os.path.basename(TWBX_PATH)}")
print(f"  Dashboard: {DASHBOARD_NAME}")
print(f"{'='*70}\n")

# ── Import the extractor ────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from tableau_api import TableauHyperExtractor
except ImportError as e:
    print(f"ERROR importing tableau_api: {e}")
    sys.exit(1)

# ── Load workbook bytes ─────────────────────────────────────────────────────
with open(TWBX_PATH, "rb") as f:
    wb_content = f.read()

# ── Set up extractor (no server needed for offline test) ────────────────────
extractor = TableauHyperExtractor(
    server_url="http://localhost",
    site_id="",
    token="",
    output_dir="/tmp/hyper_test"
)

# ── STEP 1: Extract TWB and Hyper file ──────────────────────────────────────
print("STEP 1: Extracting .twb XML and .hyper file from TWBX archive...")
hyper_path = "/tmp/hyper_test/test_extract.hyper"
os.makedirs("/tmp/hyper_test", exist_ok=True)

twb_content = None
with zipfile.ZipFile(io.BytesIO(wb_content)) as z:
    names = z.namelist()
    print(f"  Archive contents: {names}")
    twb_files   = [n for n in names if n.endswith(".twb")]
    hyper_files = [n for n in names if n.endswith(".hyper")]
    if twb_files:
        twb_content = z.read(twb_files[0])
        print(f"  TWB: {twb_files[0]} ({len(twb_content):,} bytes)")
    if hyper_files:
        with z.open(hyper_files[0]) as hf:
            with open(hyper_path, "wb") as out:
                out.write(hf.read())
        print(f"  Hyper: {hyper_files[0]} → {hyper_path}")

if not twb_content:
    print("ERROR: No .twb file found in archive.")
    sys.exit(1)

# ── STEP 2: Parse TWB XML ───────────────────────────────────────────────────
print("\nSTEP 2: Parsing TWB XML...")
root = ET.fromstring(twb_content)

all_dashboards = [d.attrib.get("name", "") for d in root.iter("dashboard")]
print(f"  Available dashboards: {all_dashboards}")

# ── STEP 3: Find sheets in the target dashboard ─────────────────────────────
print(f"\nSTEP 3: Finding sheets in dashboard '{DASHBOARD_NAME}'...")
target_norm = DASHBOARD_NAME.lower().replace(" ", "").replace("_", "")
dashboard_sheets = []
for dash in root.iter("dashboard"):
    name = dash.attrib.get("name", "")
    if name == DASHBOARD_NAME or name.lower().replace(" ", "").replace("_", "") == target_norm:
        seen = set()
        for zone in dash.iter("zone"):
            sheet = zone.attrib.get("name")
            if sheet and sheet not in seen:
                seen.add(sheet)
                dashboard_sheets.append(sheet)
        print(f"  Matched dashboard '{name}' with {len(dashboard_sheets)} sheets:")
        for i, s in enumerate(dashboard_sheets, 1):
            print(f"    {i:2d}. {s}")
        break

if not dashboard_sheets:
    print(f"ERROR: No sheets found for dashboard '{DASHBOARD_NAME}'.")
    sys.exit(1)

# ── STEP 4: Parse workbook structure (fields + filters per sheet) ────────────
print(f"\nSTEP 4: Parsing worksheet definitions (fields + filters)...")
worksheet_defs = extractor._parse_workbook_structure(root)
print(f"  Total worksheets parsed: {len(worksheet_defs)}")

for sheet in dashboard_sheets:
    if sheet in worksheet_defs:
        defn = worksheet_defs[sheet]
        print(f"\n  [{sheet}]")
        print(f"    rows_fields : {[(f['agg'], f['caption']) for f in defn['rows_fields']]}")
        print(f"    cols_fields : {[(f['agg'], f['caption']) for f in defn['cols_fields']]}")
        print(f"    cat_filters : {len(defn['categorical_filters'])}")
        print(f"    date_filters: {len(defn['date_filters'])}")
        print(f"    marks       : {len(defn['marks_measures'])}")
    else:
        print(f"  [{sheet}] — NO DEFINITION FOUND")

# ── STEP 5: Load Hyper data ─────────────────────────────────────────────────
print(f"\nSTEP 5: Loading Hyper extract...")
import pandas as pd
if os.path.exists(hyper_path):
    df_master = extractor._read_hyper(hyper_path)
    print(f"  Hyper rows  : {len(df_master)}")
    print(f"  Hyper cols  : {list(df_master.columns)}")
    if not df_master.empty:
        print(f"  Sample row  : {df_master.iloc[0].to_dict()}")
else:
    print(f"  No .hyper file found at {hyper_path} — live connection workbook.")
    df_master = pd.DataFrame()

# ── STEP 6: Reconstruct CSV per sheet ──────────────────────────────────────
print(f"\nSTEP 6: Reconstructing CSV for each sheet in '{DASHBOARD_NAME}'...")
if df_master.empty:
    print("  Skipped — no Hyper data available.")
else:
    csv_result = extractor.reconstruct_csv(df_master, dashboard_sheets, worksheet_defs)
    if csv_result:
        out_path = "/tmp/hyper_test/reconstructed.csv"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(csv_result)
        print(f"\n  ✓ Output written to: {out_path}")
        print(f"  Total output size  : {len(csv_result):,} characters")
        print(f"\n{'='*70}")
        print("  RECONSTRUCTED CSV PREVIEW (first 4000 chars):")
        print(f"{'='*70}")
        print(csv_result[:4000])
    else:
        print("  ✗ No CSV output produced. Check logs above for details.")

print(f"\n{'='*70}")
print("  Test complete.")
print(f"{'='*70}\n")
