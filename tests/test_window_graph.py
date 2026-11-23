import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


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

    def test_window_from_opening_to_atoms_and_back_to_fabrication(self):
        self.output("validate")
        parts = self.output("parts", "opening-w01")
        part_links = {
            (row["subject"], row["predicate"], row.get("target"))
            for row in parts["statements"] if "predicate" in row
        }
        self.assertTrue({
            ("window-w01", "fillsOpening", "opening-w01"),
            ("window-w01", "hasPart", "glazing-unit-w01"),
            ("glazing-unit-w01", "hasPart", "outer-pane-w01"),
            ("outer-pane-w01", "madeOf", "low-e-coating"),
            ("outer-pane-w01", "madeOf", "soda-lime-glass"),
            ("soda-lime-glass", "hasStructure", "amorphous-silicate-network"),
            ("amorphous-silicate-network", "includesChemical", "sodium-ion"),
        }.issubset(part_links))

        trace = self.output("trace", "window-w01")
        lineage = {
            (row["subject"], row["predicate"], row.get("target"))
            for row in trace["statements"] if "predicate" in row
        }
        self.assertTrue({
            ("assemble-igu-w01", "produces", "glazing-unit-w01"),
            ("assemble-igu-w01", "uses", "coated-pane-batch"),
            ("substitution-w01", "evaluates", "igu-gray-air"),
            ("substitution-w01", "selects", "igu-gray-argon"),
            ("glazing-unit-w01", "isInstanceOf", "igu-gray-argon"),
            ("ship-window-w01", "uses", "window-w01"),
            ("install-window-w01", "uses", "window-w01"),
        }.issubset(lineage))

        with TemporaryDirectory() as directory:
            graph = Path(directory) / "window.json"
            fixture = json.loads((ROOT / "fixtures" / "window.json").read_text(encoding="utf-8"))
            fixture["nodes"].extend([
                {"id": "another-order", "kind": "activity", "stage": "fabrication", "label": "Other order"},
                {"id": "another-window", "kind": "physicalItem", "label": "Other window"},
            ])
            for predicate, target in [("uses", "coated-pane-batch"), ("produces", "another-window")]:
                fixture["statements"].append({
                    "id": f"other-order-{predicate}", "subject": "another-order", "predicate": predicate,
                    "target": target, "basis": "illustrative",
                    "evidence": [{"source": "window-example", "locator": {"section": "Unrelated order"}}],
                })
            graph.write_text(json.dumps(fixture), encoding="utf-8")
            scoped = self.output("--graph", graph, "trace", "glazing-unit-w01")
            scoped_nodes = {node["id"] for node in scoped["nodes"]}
            self.assertIn("install-window-w01", scoped_nodes)
            self.assertNotIn("another-window", scoped_nodes)
            self.assertNotIn("another-order", scoped_nodes)

        facts = self.output("facts", "igu-gray-reference")["statements"]
        rating = next(row for row in facts if row["property"] == "solarHeatGainCoefficient")
        self.assertEqual(rating["quantity"], {"value": 0.19, "unit": "1"})
        self.assertEqual(rating["scope"], "center-of-glass")
        self.assertEqual(rating["basis"], "simulated")
        self.assertNotIn("argon", rating["conditions"])
        self.assertEqual(self.output("facts", "window-w01")["statements"], [])
        for fill, expected in [("air", 0.28), ("argon", 0.24)]:
            variant = self.output("facts", f"igu-gray-{fill}")["statements"]
            self.assertEqual([(row["property"], row["quantity"]["value"]) for row in variant],
                             [("uFactor", expected)])
        citation = self.output("cite", rating["id"])
        self.assertEqual(citation["evidence"][0]["locator"]["page"], 2)
        self.assertEqual(citation["evidence"][0]["locator"]["column"], "SHGC")

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
