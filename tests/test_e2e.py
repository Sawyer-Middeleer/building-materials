"""Minimal end-to-end tests for the Building Materials graph pipeline (per AGENTS.md)."""

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from building_materials.server import make_server

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-B", "-m", "building_materials", *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )


def minimal_pdf_bytes(text: str = "Table 1 Performance 0.25 12.4") -> bytes:
    """Construct a tiny, valid single-page PDF readable by pypdf."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objs = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        f"5 0 obj << /Length {len(stream)} >> stream\n".encode("latin-1") + stream + b"\nendstream endobj\n",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode("latin-1"))
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        f"trailer << /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin-1")
    )
    return bytes(out)


class BuildingMaterialsE2ETest(unittest.TestCase):
    def cli_json(self, *args) -> dict:
        proc = run_cli(*args)
        self.assertEqual(proc.returncode, 0, f"CLI failed for {args}:\n{proc.stderr}")
        return json.loads(proc.stdout)

    def test_real_corpus_build_audit_and_cli_queries(self):
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "materials.db"
            built = self.cli_json("--db", db_path, "build")
            self.assertEqual(built["schemaVersion"], 2)
            self.assertGreater(built["nodes"], 60)

            validated = self.cli_json("validate")
            self.assertTrue(validated["valid"])

            audited = self.cli_json("--db", db_path, "audit")
            self.assertTrue(audited["ok"], audited)
            self.assertEqual(audited["summary"]["errors"], 0)

            parts = self.cli_json("--db", db_path, "parts", "envelope.openings.window")
            part_ids = {n["id"] for n in parts["nodes"]}
            self.assertTrue({"material.soda-lime-glass", "structure.amorphous-silicate-network", "chem.si"}.issubset(part_ids))

            trace = self.cli_json("--db", db_path, "trace", "envelope.openings.window")
            trace_ids = {n["id"] for n in trace["nodes"]}
            self.assertIn("process.fabrication.float-glass", trace_ids)

            used = self.cli_json("--db", db_path, "used-by", "material.soda-lime-glass")
            self.assertIn("envelope.openings.window.outer-pane", {n["id"] for n in used["nodes"]})

            compared = self.cli_json(
                "--db", db_path, "compare",
                "product.vitro.solarban-70.solargray-air",
                "product.vitro.solarban-70.solargray-argon",
            )
            self.assertEqual([m["id"] for m in compared["materials"]["onlyLeft"]], ["material.air-fill"])
            self.assertEqual([m["id"] for m in compared["materials"]["onlyRight"]], ["material.argon-fill"])
            u_row = next(f for f in compared["facts"] if f["property"] == "uFactor")
            self.assertEqual(u_row["left"]["quantity"]["value"], 0.28)
            self.assertEqual(u_row["right"]["quantity"]["value"], 0.24)
            self.assertEqual(u_row["right"]["siQuantity"]["unit"], "W/(m²·K)")

            search_punct = self.cli_json("--db", db_path, "search", "08 50 00")
            self.assertGreaterEqual(search_punct["total"], 1)

            explained = self.cli_json("--db", db_path, "explain", "uFactor")
            self.assertEqual(explained["guide"]["ucumUnit"], "W/(m2.K)")

            cited = self.cli_json("--db", db_path, "cite", u_row["right"]["id"])
            self.assertEqual(cited["evidence"][0]["locator"]["page"], 2)

            for tier in ("catalog", "assembly", "atomic"):
                g = self.cli_json("--db", db_path, "gaps", "--tier", tier)
                self.assertEqual(g["tier"], tier)
                self.assertEqual(g["summary"]["composition"], 0)
                self.assertEqual(g["summary"]["valueChain"], 0)

    def test_authoring_roundtrip_and_negative_contracts(self):
        with TemporaryDirectory() as tmp:
            t = Path(tmp)
            data_dir = t / "data"
            assets_dir = t / "assets"
            db_path = t / "test.db"

            pdf1 = t / "epd.pdf"
            pdf1.write_bytes(minimal_pdf_bytes("Table 1 Performance 0.25 12.4 72.0"))
            pdf2 = t / "epd-modified.pdf"
            pdf2.write_bytes(minimal_pdf_bytes("Modified content"))

            imp1 = self.cli_json(
                "--data", data_dir, "--assets", assets_dir,
                "import-source", pdf1, "--id", "acme.epd-2026",
                "--url", "https://example.com/acme-epd.pdf", "--issuer", "Acme Corp",
            )
            self.assertEqual(imp1["status"], "created")
            self.assertTrue((data_dir / "sources" / "acme" / "epd-2026.yaml").is_file())

            # Slug immutability firewall
            bad_imp = run_cli(
                "--data", data_dir, "--assets", assets_dir,
                "import-source", pdf2, "--id", "acme.epd-2026",
                "--url", "https://example.com/acme-epd.pdf",
            )
            self.assertNotEqual(bad_imp.returncode, 0)

            (data_dir / "guides.yaml").write_text(
                """propertyGuides:
  uFactor: { title: U-Factor, summary: Thermal transmittance, ucumUnit: W/(m2.K) }
  gwp: { title: GWP, summary: Embodied carbon, ucumUnit: kg }
  tempered: { title: Tempered, summary: Safety tempered glass }
""",
                encoding="utf-8",
            )
            (data_dir / "model.yaml").write_text(
                """defaults:
  basis: manufacturer-declared
  evidence:
    - source: source.acme.epd-2026
      locator: { page: 1, table: Table 1 }

entities:
  - id: actor.acme
    kind: actor
    label: Acme Glass Plant
  - id: chem.sio2
    kind: chemicalEntity
    label: Silicon dioxide
  - id: material.glass
    kind: material
    label: Float glass
    links:
      - predicate: hasComposition
        target: chem.sio2
        qualifiers:
          role: network former
          quantity: { min: 70.0, max: 72.0, unit: "%", basis: mass }
  - id: envelope.window.igu
    kind: referenceDesign
    label: Reference IGU
  - id: product.acme.line
    kind: productModel
    label: Acme Glazing Line
    links:
      - { predicate: manufacturedBy, target: actor.acme }
      - { predicate: realizesDesign, target: envelope.window.igu }
    properties:
      - property: gwp
        scope: A1-A3
        geography: US-TX
        pcr: UL-Flat-Glass-2024
        validUntil: "2030-12-31"
        plantActor: actor.acme
        quantity: { value: 12.4, unit: "kg CO2e/m²", basis: "per m2 (6mm glass)" }
      - property: tempered
        value: true
    variantDefaults:
      links:
        - { predicate: realizesDesign, target: envelope.window.igu }
    variantsTable:
      csv: skus.csv
      idTemplate: "product.acme.line.{sku}"
      labelTemplate: "Acme {sku}"
      columns:
        u: { property: uFactor, unit: "Btu/(h·ft²·°F)", scope: center-of-glass }
""",
                encoding="utf-8",
            )
            (data_dir / "skus.csv").write_text("sku,u\nsku-a,0.25\nsku-b,0.20\n", encoding="utf-8")

            self.cli_json("--data", data_dir, "--assets", assets_dir, "--db", db_path, "build")
            facts = self.cli_json("--data", data_dir, "--assets", assets_dir, "--db", db_path, "facts", "product.acme.line.sku-a")
            by_prop = {s["property"]: s for s in facts["statements"]}
            self.assertIs(by_prop["tempered"]["value"], True)
            self.assertEqual(by_prop["gwp"]["geography"], "US-TX")
            self.assertEqual(by_prop["gwp"]["validUntil"], "2030-12-31")
            self.assertEqual(by_prop["gwp"]["plantActor"], "actor.acme")
            self.assertIn("inheritedFrom", by_prop["gwp"])
            self.assertEqual(by_prop["uFactor"]["siQuantity"]["unit"], "W/(m²·K)")

            # Auto-rebuild on YAML edit
            (data_dir / "skus.csv").write_text("sku,u\nsku-a,0.22\nsku-b,0.20\n", encoding="utf-8")
            facts_after = self.cli_json("--data", data_dir, "--assets", assets_dir, "--db", db_path, "facts", "product.acme.line.sku-a")
            u_after = next(s for s in facts_after["statements"] if s["property"] == "uFactor")
            self.assertEqual(u_after["quantity"]["value"], 0.22)

            # Fuzzy duplicate label warning in audit
            (data_dir / "dup-actor.yaml").write_text(
                """id: actor.acme-dup
kind: actor
label: Acme Glass Plant Inc.
""",
                encoding="utf-8",
            )
            dup_proc = run_cli("--data", data_dir, "--assets", assets_dir, "--db", db_path, "audit")
            dup_audit = json.loads(dup_proc.stdout)
            self.assertTrue(any(w["code"] == "possible-duplicate-label" for w in dup_audit["warnings"]), dup_audit)
            (data_dir / "dup-actor.yaml").unlink()

            # Negative contracts: duplicate unique external ID (CAS RN)
            (data_dir / "dup-cas.yaml").write_text(
                """entities:
  - id: chem.silica-a
    kind: chemicalEntity
    label: Silica A
    identifiers: [{namespace: cas, value: "7631-86-9"}]
  - id: chem.silica-b
    kind: chemicalEntity
    label: Silica B
    identifiers: [{namespace: cas, value: "7631-86-9"}]
""",
                encoding="utf-8",
            )
            bad_cas = run_cli("--data", data_dir, "validate")
            self.assertNotEqual(bad_cas.returncode, 0)
            self.assertIn("7631-86-9", bad_cas.stderr)
            (data_dir / "dup-cas.yaml").unlink()

            # Negative contracts: bad EPD scope
            (data_dir / "bad.yaml").write_text(
                """id: product.bad
kind: productModel
label: Bad EPD
properties:
  - property: gwp
    scope: invalid-scope
    state: unknown
    basis: manufacturer-declared
    evidence: [{source: source.acme.epd-2026, locator: {page: 1}}]
""",
                encoding="utf-8",
            )
            bad = run_cli("--data", data_dir, "validate")
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("EN 15804", bad.stderr)

    def test_headless_json_http_api(self):
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "api.db"
            self.cli_json("--db", db_path, "build")
            server = make_server(db_path, ROOT / ".materials", host="127.0.0.1", port=0)
            port = server.server_port
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get_json(path: str):
                    with urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as resp:
                        return resp.status, json.loads(resp.read().decode("utf-8"))

                status, health = get_json("/api/health")
                self.assertEqual(status, 200)
                self.assertTrue(health["ok"])
                self.assertEqual(health["schemaVersion"], 2)

                _, page = get_json("/api/nodes?kind=productVariant&limit=2&offset=0")
                self.assertEqual(len(page["items"]), 2)
                self.assertEqual(page["total"], 8)
                self.assertTrue(page["hasMore"])

                _, stmts = get_json("/api/statements?property=uFactor&limit=5")
                self.assertEqual(len(stmts["items"]), 5)

                _, searched = get_json("/api/search?q=silicate")
                self.assertGreaterEqual(searched["total"], 1)

                _, facts = get_json("/api/nodes/product.vitro.solarban-70.solargray-argon/facts")
                u_stmt = next(s for s in facts["statements"] if s["property"] == "uFactor")

                _, cited = get_json(f"/api/statements/{u_stmt['id']}/cite")
                self.assertTrue(cited["evidence"][0]["webHref"].startswith("/assets/"))
                blob_url = cited["evidence"][0]["webHref"].split("#")[0]
                with urlopen(f"http://127.0.0.1:{port}{blob_url}", timeout=5) as blob_resp:
                    self.assertEqual(blob_resp.status, 200)
                    self.assertTrue(blob_resp.read(5).startswith(b"%PDF-"))

                _, compared = get_json(
                    "/api/compare?left=product.vitro.solarban-70.solargray-air&right=product.vitro.solarban-70.solargray-argon"
                )
                self.assertEqual([m["id"] for m in compared["materials"]["onlyRight"]], ["material.argon-fill"])

                _, gaps = get_json("/api/gaps?tier=catalog")
                self.assertEqual(gaps["tier"], "catalog")

                for bad_path, expected_code in [
                    ("/", 404),
                    ("/assets/../secret", 404),
                    ("/api/gaps?tier=bogus", 400),
                    ("/api/nodes?limit=9999", 400),
                ]:
                    with self.assertRaises(HTTPError) as ctx:
                        urlopen(f"http://127.0.0.1:{port}{bad_path}", timeout=5)
                    self.assertEqual(ctx.exception.code, expected_code)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
