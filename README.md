# Building Materials

A source-backed graph describing what goes into a building—from assemblies down to atomic structure—and how each component is designed, made, and installed. The first working slice is a single window (`fixtures/window.json`).

## Setup

Requires Python 3.11 or later.

```text
python -m pip install -r requirements.txt
```

## CLI

All commands default to `fixtures/window.json` and `.materials/`. Pass `--graph <path>` or `--assets <dir>` before the subcommand to override.

```text
python -m building_materials validate
python -m building_materials parts window-assembly
python -m building_materials trace igu-gray-argon
python -m building_materials used-by vitro-solarban-70
python -m building_materials compare igu-gray-air igu-gray-argon
python -m building_materials gaps
python -m building_materials export-db
python -m building_materials facts igu-gray-reference
python -m building_materials explain uFactor
python -m building_materials explain andersen
python -m building_materials cite igu-gray-shgc
python -m building_materials serve --open
```

Archive a source URL or local file into `.materials/`:

```text
python -m building_materials import-source <url>
python -m building_materials import-source <path> --url <source-url>
```

Local source captures under `.materials/` are gitignored. On a fresh clone without local captures, `cite` resolves claims as `link-only` using the original source URL and locator until the sources are imported.

## Tests

```text
python -m unittest discover -s tests -v
```

## Schema and Design

See [specs/graph-data-schema.md](specs/graph-data-schema.md), [graph.schema.json](graph.schema.json), [guide.schema.json](guide.schema.json), and [schema.sql](schema.sql).
