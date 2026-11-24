import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

import building_materials


ROOT = Path(__file__).resolve().parents[1]


def cli(*args):
    return subprocess.run(
        [sys.executable, "-B", "-m", "building_materials", *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )


class BuildingGraphTest(unittest.TestCase):
    def output(self, *args):
        result = cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_window_composition_value_chain_and_comparison(self):
        self.output("validate")
        parts = self.output("parts", "window-assembly")
        part_links = {
            (row["subject"], row["predicate"], row.get("target"))
            for row in parts["statements"] if "predicate" in row
        }
        self.assertTrue({
            ("window-assembly", "hasPart", "insulating-glass-unit"),
            ("insulating-glass-unit", "hasPart", "outer-pane"),
            ("outer-pane", "madeOf", "low-e-coating"),
            ("outer-pane", "madeOf", "soda-lime-glass"),
            ("soda-lime-glass", "hasStructure", "amorphous-silicate-network"),
            ("amorphous-silicate-network", "includesChemical", "sodium-ion"),
        }.issubset(part_links))

        trace = self.output("trace", "igu-gray-argon")
        lineage = {
            (row["subject"], row["predicate"], row.get("target"))
            for row in trace["statements"] if "predicate" in row
        }
        self.assertTrue({
            ("igu-assembly-argon", "produces", "igu-gray-argon"),
            ("igu-assembly-argon", "uses", "argon-fill"),
            ("sputter-coating", "produces", "vitro-solarban-70"),
            ("float-glass-forming", "uses", "silica-sand"),
            ("float-glass-forming", "produces", "soda-lime-glass"),
        }.issubset(lineage))
        self.assertNotIn("igu-gray-air", {node["id"] for node in trace["nodes"]})

        used = self.output("used-by", "vitro-solarban-70")
        used_nodes = {node["id"] for node in used["nodes"]}
        self.assertTrue({"igu-gray-air", "igu-gray-argon", "igu-assembly-argon"}.issubset(used_nodes))

        compared = self.output("compare", "igu-gray-air", "igu-gray-argon")
        self.assertEqual([n["id"] for n in compared["materials"]["onlyLeft"]], ["air-fill"])
        self.assertEqual([n["id"] for n in compared["materials"]["onlyRight"]], ["argon-fill"])
        self.assertEqual(
            {n["id"] for n in compared["processes"]["onlyLeft"]},
            {"air-drying", "igu-assembly-air"},
        )
        self.assertEqual(
            {n["id"] for n in compared["processes"]["onlyRight"]},
            {"cryogenic-air-separation", "igu-assembly-argon"},
        )
        u_row = next(row for row in compared["facts"] if row["property"] == "uFactor")
        self.assertEqual(u_row["left"]["quantity"]["value"], 0.28)
        self.assertEqual(u_row["right"]["quantity"]["value"], 0.24)

        win_cmp = self.output("compare", "winco-4410s-single-hung", "andersen-100-single-hung")
        self.assertEqual([n["id"] for n in win_cmp["materials"]["onlyLeft"]], ["polyurethane-thermal-break"])
        self.assertEqual([n["id"] for n in win_cmp["materials"]["onlyRight"]], ["fibrex-composite"])
        self.assertEqual(
            {n["id"] for n in win_cmp["processes"]["onlyLeft"]},
            {"thermal-break-pouring", "winco-window-assembly"},
        )
        self.assertEqual(
            {n["id"] for n in win_cmp["processes"]["onlyRight"]},
            {"fibrex-compounding", "composite-extrusion", "andersen-window-assembly"},
        )
        win_u = next(row for row in win_cmp["facts"] if row["property"] == "uFactor")
        self.assertEqual(win_u["left"]["quantity"]["value"], 0.50)
        self.assertEqual(win_u["right"]["quantity"]["value"], 0.25)

        facts = self.output("facts", "igu-gray-reference")["statements"]
        rating = next(row for row in facts if row["property"] == "solarHeatGainCoefficient")
        self.assertEqual(rating["quantity"], {"value": 0.19, "unit": "1"})
        self.assertEqual(rating["scope"], "center-of-glass")
        self.assertEqual(rating["basis"], "simulated")
        self.assertEqual(self.output("facts", "window-assembly")["statements"], [])
        citation = self.output("cite", rating["id"])
        self.assertEqual(citation["evidence"][0]["locator"]["page"], 2)
        self.assertEqual(citation["evidence"][0]["locator"]["column"], "SHGC")

        validated = self.output("validate")
        self.assertGreater(validated["guideNodes"], 0)
        self.assertGreater(validated["guideProperties"], 0)
        self.assertEqual(self.output("explain", "andersen")["guide"]["firm"]["founded"], 1903)
        self.assertEqual(self.output("explain", "sodium-ion")["guide"]["chemistry"]["atomicNumber"], 11)
        self.assertIn("U-Factor", self.output("explain", "uFactor")["guide"]["title"])
        gaps = self.output("gaps")
        self.assertEqual(gaps["summary"]["total"], 0)

        with TemporaryDirectory() as directory:
            db_path = Path(directory) / "materials.db"
            exported = self.output("export-db", db_path)
            self.assertEqual(exported["nodes"], validated["nodes"])
            self.assertEqual(exported["statements"], validated["statements"])
            self.assertTrue(db_path.is_file())

    def test_masonry_composition_value_chain_comparison_and_cross_links(self):
        brick_parts = self.output("parts", "glengery-clay-brick-veneer")
        brick_links = {
            (row["subject"], row["predicate"], row.get("target"))
            for row in brick_parts["statements"] if "predicate" in row
        }
        self.assertTrue({
            ("glengery-clay-brick-veneer", "hasPart", "glengery-modular-clay-brick"),
            ("glengery-modular-clay-brick", "madeOf", "fired-clay-brick-body"),
            ("fired-clay-brick-body", "hasStructure", "fired-clay-ceramic-matrix"),
            ("fired-clay-ceramic-matrix", "includesChemical", "aluminum"),
            ("type-n-portland-lime-mortar", "hasStructure", "csh-hydration-gel"),
            ("csh-hydration-gel", "includesChemical", "calcium-ion"),
        }.issubset(brick_links))

        cmu_trace = self.output("trace", "echelon-cmu-veneer")
        cmu_lineage = {
            (row["subject"], row["predicate"], row.get("target"))
            for row in cmu_trace["statements"] if "predicate" in row
        }
        self.assertTrue({
            ("echelon-cmu-veneer-installation", "produces", "echelon-cmu-veneer"),
            ("cmu-vibro-compaction-curing", "produces", "echelon-normal-weight-cmu"),
            ("cement-clinker-calcination", "uses", "limestone"),
            ("cement-clinker-calcination", "produces", "portland-cement"),
            ("mortar-blending-type-s", "produces", "specmix-mortar-type-s"),
        }.issubset(cmu_lineage))
        self.assertNotIn("glengery-clay-brick-veneer", {n["id"] for n in cmu_trace["nodes"]})

        # Shared feedstocks & sealants connect windows and masonry in one graph
        limestone_used = {n["id"] for n in self.output("used-by", "limestone")["nodes"]}
        self.assertTrue({"float-glass-forming", "cement-clinker-calcination", "lime-calcination-hydration"}.issubset(limestone_used))
        silica_used = {n["id"] for n in self.output("used-by", "silica-sand")["nodes"]}
        self.assertTrue({"float-glass-forming", "glengery-clay-brick-veneer", "echelon-cmu-veneer"}.issubset(silica_used))

        # Whole-wall comparison: fired clay brick veneer vs. normal-weight CMU wall
        wall_cmp = self.output("compare", "glengery-clay-brick-veneer", "echelon-cmu-veneer")
        self.assertEqual(
            {n["id"] for n in wall_cmp["materials"]["onlyLeft"]},
            {"fired-clay-brick-body", "type-n-portland-lime-mortar"},
        )
        self.assertEqual(
            {n["id"] for n in wall_cmp["materials"]["onlyRight"]},
            {"crushed-stone-aggregate", "concrete-masonry-body", "type-s-portland-lime-mortar"},
        )
        self.assertEqual(
            {n["id"] for n in wall_cmp["processes"]["onlyLeft"]},
            {"glengery-brick-extrusion-firing", "mortar-blending-type-n", "glengery-brick-veneer-installation"},
        )
        self.assertEqual(
            {n["id"] for n in wall_cmp["processes"]["onlyRight"]},
            {"aggregate-quarrying", "cmu-vibro-compaction-curing", "mortar-blending-type-s", "echelon-cmu-veneer-installation"},
        )
        rsl_row = next(row for row in wall_cmp["facts"] if row["property"] == "referenceServiceLife")
        self.assertEqual(rsl_row["left"]["quantity"]["value"], 150)
        self.assertEqual(rsl_row["right"]["quantity"]["value"], 100)

        # Sub-assembly comparison: Type N vs. Type S Portland-lime mortar
        mort_cmp = self.output("compare", "specmix-mortar-type-n", "specmix-mortar-type-s")
        self.assertEqual([n["id"] for n in mort_cmp["materials"]["onlyLeft"]], ["type-n-portland-lime-mortar"])
        self.assertEqual([n["id"] for n in mort_cmp["materials"]["onlyRight"]], ["type-s-portland-lime-mortar"])
        self.assertEqual([n["id"] for n in mort_cmp["processes"]["onlyLeft"]], ["mortar-blending-type-n"])
        self.assertEqual([n["id"] for n in mort_cmp["processes"]["onlyRight"]], ["mortar-blending-type-s"])
        comp_row = next(row for row in mort_cmp["facts"] if row["property"] == "compressiveStrength")
        self.assertEqual(comp_row["left"]["quantity"]["value"], 750)
        self.assertEqual(comp_row["right"]["quantity"]["value"], 1800)

        # Scoped unit facts, citations, and companion guide explainers
        belden_facts = self.output("facts", "belden-canton-clay-brick")["statements"]
        belden_comp = next(row for row in belden_facts if row["property"] == "compressiveStrength")
        self.assertEqual(belden_comp["quantity"], {"value": 14620, "unit": "psi"})
        self.assertEqual(belden_comp["scope"], "masonry-unit")
        self.assertEqual(self.output("facts", "masonry-wall-assembly")["statements"], [])
        belden_cite = self.output("cite", belden_comp["id"])
        self.assertEqual(belden_cite["evidence"][0]["locator"]["page"], 1)
        self.assertEqual(belden_cite["evidence"][0]["capture"], "saved")
        self.assertEqual(self.output("explain", "glengery")["guide"]["firm"]["founded"], 1890)
        self.assertEqual(self.output("explain", "iron")["guide"]["chemistry"]["atomicNumber"], 26)
        self.assertIn("Compressive Strength", self.output("explain", "compressiveStrength")["guide"]["title"])

        audit = self.output("audit")
        self.assertTrue(audit["ok"])
        self.assertEqual(audit["summary"]["errors"], 0)
        self.assertEqual(audit["summary"]["warnings"], 0)
        self.assertGreaterEqual(audit["summary"]["pdfsChecked"], 28)

    def test_source_versions_keep_the_original_citation_openable(self):
        with TemporaryDirectory() as directory:
            workspace = Path(directory)
            assets = workspace / "assets"
            original = workspace / "original.html"
            updated = workspace / "updated.html"
            original_bytes = b'<h2 id="performance">Performance</h2><p>SHGC 0.19</p>'
            original.write_bytes(original_bytes)
            updated.write_bytes(b'<h2 id="performance">Performance</h2><p>SHGC 0.20</p>')
            origin = "https://example.invalid/datasheet.html"
            options = ("--assets", assets)
            missing_url = cli(*options, "import-source", original)
            self.assertNotEqual(missing_url.returncode, 0)
            self.assertIn("require --url", missing_url.stderr)
            first = self.output(*options, "import-source", original, "--url", origin)
            self.assertEqual(first["source"]["source"]["origin"], origin)

            fixture = json.loads((ROOT / "fixtures" / "building.json").read_text(encoding="utf-8"))
            rating = next(row for row in fixture["statements"] if row["id"] == "igu-gray-shgc")
            rating["evidence"] = [{
                "source": first["source"]["id"],
                "locator": {"anchor": "performance", "quote": "SHGC 0.19"},
            }]
            graph = workspace / "building.json"
            graph.write_text(json.dumps(fixture), encoding="utf-8")

            newer = self.output(*options, "import-source", updated, "--url", origin)
            self.assertNotEqual(first["source"]["id"], newer["source"]["id"])
            replay = self.output(*options, "import-source", original, "--url", origin)
            self.assertEqual(first, replay)
            evidence = self.output(*options, "--graph", graph, "cite", rating["id"])["evidence"][0]
            self.assertEqual(evidence["source"]["id"], first["source"]["id"])
            self.assertEqual(evidence["href"], Path(first["savedPath"]).as_uri() + "#performance")
            self.assertEqual(Path(evidence["savedPath"]).read_bytes(), original_bytes)

            del rating["quantity"]["unit"]
            graph.write_text(json.dumps(fixture), encoding="utf-8")
            result = cli(*options, "--graph", graph, "validate")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Invalid graph", result.stderr)

            rating["quantity"]["unit"] = "1"
            fixture["statements"][0]["predicate"] = "unknownPredicate"
            graph.write_text(json.dumps(fixture), encoding="utf-8")
            bad_pred = cli(*options, "--graph", graph, "validate")
            self.assertNotEqual(bad_pred.returncode, 0)
            self.assertIn("Invalid graph", bad_pred.stderr)

            # Audit catches out-of-bounds PDF pages and missing process roles
            audit_fixture = json.loads((ROOT / "fixtures" / "building.json").read_text(encoding="utf-8"))
            belden_comp = next(row for row in audit_fixture["statements"] if row["id"] == "belden-unit-comp")
            belden_comp["evidence"][0]["locator"]["page"] = 999
            proc_stmt = next(row for row in audit_fixture["statements"] if row["id"] == "proc-ext-clay-out")
            del proc_stmt["qualifiers"]["role"]
            graph.write_text(json.dumps(audit_fixture), encoding="utf-8")
            bad_audit = cli("--graph", graph, "audit")
            self.assertNotEqual(bad_audit.returncode, 0)
            audit_codes = {e["code"] for e in json.loads(bad_audit.stdout)["errors"]}
            self.assertTrue({"pdf-page-out-of-bounds", "process-missing-role"}.issubset(audit_codes))

    def test_web_ui_serves_viewer_and_graph_endpoints(self):
        graph = building_materials.Graph(building_materials.DEFAULT_GRAPH, building_materials.DEFAULT_ASSETS)
        guide = building_materials.load_guide(graph, building_materials.DEFAULT_GRAPH)
        server = building_materials.make_server(graph, building_materials.DEFAULT_ASSETS, port=0, guide=guide)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            with urlopen(f"{base}/", timeout=5) as res:
                self.assertIn("Building Materials", res.read().decode("utf-8"))
            with urlopen(f"{base}/api/parts/window-assembly", timeout=5) as res:
                parts = json.loads(res.read().decode("utf-8"))
                self.assertEqual(parts["root"], "window-assembly")
            with urlopen(f"{base}/api/compare/igu-gray-air/igu-gray-argon", timeout=5) as res:
                cmp_data = json.loads(res.read().decode("utf-8"))
                self.assertEqual([n["id"] for n in cmp_data["materials"]["onlyRight"]], ["argon-fill"])
            with urlopen(f"{base}/api/gaps", timeout=5) as res:
                gaps_data = json.loads(res.read().decode("utf-8"))
                self.assertEqual(gaps_data["summary"]["total"], 0)
            with urlopen(f"{base}/api/schema", timeout=5) as res:
                schema_data = json.loads(res.read().decode("utf-8"))
                self.assertIn("CREATE TABLE IF NOT EXISTS nodes", schema_data["sql"])
            with urlopen(f"{base}/api/guide", timeout=5) as res:
                guide_data = json.loads(res.read().decode("utf-8"))
                self.assertIn("uFactor", guide_data["properties"])
                self.assertIn("andersen", guide_data["nodes"])
            with urlopen(f"{base}/api/cite/igu-gray-shgc", timeout=5) as res:
                cited = json.loads(res.read().decode("utf-8"))
                self.assertEqual(cited["evidence"][0]["locator"]["page"], 2)
                self.assertIn("webHref", cited["evidence"][0])
            for asset in (
                "/ui/studio.js",
                "/ui/materials.js",
                "/ui/inspector.js",
                "/ui/levels/building.js",
                "/ui/levels/window.js",
                "/ui/levels/igu.js",
                "/ui/levels/atomic.js",
            ):
                with urlopen(f"{base}{asset}", timeout=5) as res:
                    self.assertEqual(res.status, 200)
                    self.assertIn("javascript", res.headers.get("Content-Type", ""))
            with self.assertRaises(HTTPError) as ctx:
                urlopen(f"{base}/ui/../building_materials.py", timeout=5)
            self.assertEqual(ctx.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
