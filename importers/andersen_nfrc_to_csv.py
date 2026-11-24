"""Repeatable document-driven importer: archived Andersen NFRC PDF -> SKU CSV.

Reads an archived Andersen NFRC Certified Total Unit Performance PDF via its
tracked `data/sources/...yaml` manifest (never scrapes live URLs, never writes
directly to SQLite), extracts verified "Without Grilles" glazing rows and any
NFRC/Hallmark sample label on the final page, and emits a deterministic CSV
compatible with `variantsTable`.
"""

import argparse
import csv
from pathlib import Path
import re
import sys

import pypdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from building_materials.compiler import load_yaml  # noqa: E402
from building_materials.model import DEFAULT_ASSETS  # noqa: E402
from building_materials.sources import asset_path  # noqa: E402

HEADER_RE = re.compile(
    r"(?P<series>\d00 Series)\s+(?P<product>[A-Za-z0-9®™\-\s&]+?Windows)\s+AND-N-\d+",
    re.S,
)
ROW_RE = re.compile(
    r"(?P<glass>Low-E(?:4)?(?:\s+(?:SmartSun|Sun|PassiveSun|Enhanced))?(?:\s+w/HeatLock)?)\s*"
    r"[®™]*\s+Without Grilles\s+(?P<u>\d\.\d{2})\s+(?P<shgc>\d\.\d{2})\s+(?P<vlt>\d\.\d{2})",
    re.S,
)
NFRC_LABEL_RE = re.compile(r"(AND-N-\d+-\d+-\d+)")
CLASS_RE = re.compile(r"Class\s+([A-Z]+-PG\d+)")
DP_RE = re.compile(r"DP\+(\d+)/-\d+")
AIR_RE = re.compile(r"Air Infiltration Requirements of (\d+(?:\.\d+)?)\s*CFM/sq\.ft\.", re.I)
SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    return SLUG_RE.sub("-", text.lower().replace("®", "").replace("™", "")).strip("-")


def extract_rows(pdf_path: Path, *, products_filter: set[str] | None = None) -> list[dict]:
    reader = pypdf.PdfReader(pdf_path)
    rows: list[dict] = []
    seen_skus: set[str] = set()

    for page_num, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        norm = " ".join(raw.split())

        # Detect product sections on this page
        headers = list(HEADER_RE.finditer(norm))
        for idx, h in enumerate(headers):
            prod_name = " ".join(h.group("product").replace("®", "").replace("™", "").split())
            if products_filter and prod_name.lower() not in products_filter:
                continue
            start = h.end()
            end = headers[idx + 1].start() if idx + 1 < len(headers) else len(norm)
            chunk = norm[start:end]

            # Detect dual vs triple pane from page header
            pane_prefix = "Triple-Pane" if "Triple-Pane" in norm[:h.start() + 40] else "Dual-Pane"
            prod_short = (
                prod_name.replace("Full-Frame Windows", "")
                .replace("Windows", "")
                .strip()
            )
            for m in ROW_RE.finditer(chunk):
                glass = " ".join(m.group("glass").replace("®", "").replace("™", "").split())
                sku = slugify(f"{prod_short}-{pane_prefix}-{glass}")
                if sku in seen_skus:
                    continue
                seen_skus.add(sku)
                rows.append({
                    "sku": sku,
                    "label": f"{prod_short} {pane_prefix} ({glass})",
                    "page": page_num,
                    "row": f"{glass} Without Grilles",
                    "nfrc_id": "",
                    "u_factor": m.group("u"),
                    "shgc": m.group("shgc"),
                    "vlt": m.group("vlt"),
                    "dp": "",
                    "air": "",
                    "perf_class": "",
                })

    # Enrich or append certified sample label from final page if present
    last_text = " ".join((reader.pages[-1].extract_text() or "").split())
    nfrc_m = NFRC_LABEL_RE.search(last_text)
    if nfrc_m:
        cpd_id = nfrc_m.group(1)
        cls_m = CLASS_RE.search(last_text)
        dp_m = DP_RE.search(last_text)
        air_m = AIR_RE.search(last_text)
        # Match certified numbers (U-Factor, SI, SHGC, VT) right after Product Type: <type>
        pt_m = re.search(r"Product Type:\s+([A-Za-z\s-]+?)\s+(0\.\d{2})\s+\d\.\d{2}\s+(0\.\d{2})\s+(0\.\d{2})", last_text)
        if pt_m:
            ptype = " ".join(pt_m.group(1).split())
            sku = slugify(f"{ptype}-certified-sample")
            if sku not in seen_skus:
                rows.insert(0, {
                    "sku": sku,
                    "label": f"{ptype} Certified Sample ({cpd_id})",
                    "page": len(reader.pages),
                    "row": f"{ptype} Window",
                    "nfrc_id": cpd_id,
                    "u_factor": pt_m.group(2),
                    "shgc": pt_m.group(3),
                    "vlt": pt_m.group(4),
                    "dp": dp_m.group(1) if dp_m else "",
                    "air": air_m.group(1) if air_m else "",
                    "perf_class": cls_m.group(1) if cls_m else "",
                })
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source_yaml", type=Path, help="Tracked source YAML under data/sources/")
    ap.add_argument("output_csv", type=Path, help="Destination CSV under data/products/")
    ap.add_argument("--assets", type=Path, default=DEFAULT_ASSETS)
    ap.add_argument("--product", action="append", default=[], help="Optional product heading filter (repeatable)")
    args = ap.parse_args(argv)

    src = load_yaml(args.source_yaml)
    meta = src["source"]
    pdf_path = asset_path(args.assets, meta["sha256"], meta["mediaType"])
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Archived PDF blob missing: {pdf_path}")

    filt = {p.lower() for p in args.product} if args.product else None
    rows = extract_rows(pdf_path, products_filter=filt)
    if not rows:
        raise ValueError(f"No NFRC rows extracted from {pdf_path}")

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["sku", "label", "page", "row", "nfrc_id", "u_factor", "shgc", "vlt", "dp", "air", "perf_class"]
    with args.output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} verified SKU rows -> {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
