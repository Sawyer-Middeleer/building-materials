import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
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


class WindowGraphTest(unittest.TestCase):
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

            fixture = json.loads((ROOT / "fixtures" / "window.json").read_text(encoding="utf-8"))
            rating = next(row for row in fixture["statements"] if row["id"] == "igu-gray-shgc")
            rating["evidence"] = [{
                "source": first["source"]["id"],
                "locator": {"anchor": "performance", "quote": "SHGC 0.19"},
            }]
            graph = workspace / "window.json"
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
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
