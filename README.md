# Building Materials

A source-backed graph describing what goes into a building—from whole-building systems and assemblies down to atomic structure—and how each component is designed, made, and installed.

Data is authored in modular, human-readable YAML and tabular CSV SKU matrices under `data/`, compiled and validated against JSON Schema and EN 15804 EPD rules, and queried through a lossless SQLite v2 runtime store (`.materials/materials.db`) via CLI or headless JSON HTTP API.

## Setup

Requires Python 3.11 or later.

```text
python -m pip install -r requirements.txt
```

## Authoring Layout (`data/`)

- `data/systems/` — Uniformat II / IFC physical element hierarchy (`building.yaml`) and system assemblies + value-chain processes (`envelope/windows/{assembly,processes}.yaml`).
- `data/products/` — manufacturer `productModel` definitions, `variantDefaults` inheritance, and tabular CSV SKU matrices (`vitro/solarban-70.{yaml,csv}`).
- `data/materials/` — shared materials organized by material family (`glass/`, `metals/`, `minerals/`, `polymers/`, `gases/`).
- `data/chemistry/` — shared `chemicalEntity` (with CAS RNs) and `structureModel` definitions.
- `data/actors/` — manufacturers, institutions, and trade roles.
- `data/sources/` — tracked source registry nested by issuer/category (written by `import-source --id <slug>`).
- `data/guides/` — canonical `propertyGuides` with `ucumUnit` and `externalRefs` (`ifcPset`, `bsdd`, `openepd`).

## CLI

All commands default to `data/`, `.materials/`, and `.materials/materials.db`. Pass `--data`, `--assets`, `--db`, or `--no-rebuild` before the subcommand to override. Query commands automatically rebuild SQLite when `data/` changes.

```text
python -m building_materials validate
python -m building_materials build
python -m building_materials audit
python -m building_materials nodes --kind productVariant --limit 20
python -m building_materials search "08 50 00"
python -m building_materials parts envelope.openings.window
python -m building_materials trace envelope.openings.window
python -m building_materials used-by material.soda-lime-glass
python -m building_materials facts product.vitro.solarban-70.solargray-argon
python -m building_materials compare product.vitro.solarban-70.solargray-air product.vitro.solarban-70.solargray-argon
python -m building_materials gaps --tier catalog
python -m building_materials explain uFactor
python -m building_materials cite <statement-id>
python -m building_materials serve --port 8000
```

Archive a source URL or local file into `.materials/blobs/` and `data/sources/`:

```text
python -m building_materials import-source <url> --id <issuer.slug>
python -m building_materials import-source <path> --url <source-url> --id <issuer.slug>
```

Dotted `--id` slugs map to subfolders (e.g. `--id usgs.silica-2025` writes `data/sources/usgs/silica-2025.yaml` with node ID `source.usgs.silica-2025`). Local blobs under `.materials/` are gitignored; without local captures, `cite` resolves claims as `link-only`.

## Tests

```text
python -m unittest discover -s tests -v
```

## Schema and Architecture

See [specs/graph-data-schema.md](specs/graph-data-schema.md), [graph.schema.json](graph.schema.json), [guide.schema.json](guide.schema.json), [schema.sql](schema.sql), and [specs/scalable-graph-architecture/README.md](specs/scalable-graph-architecture/README.md).
