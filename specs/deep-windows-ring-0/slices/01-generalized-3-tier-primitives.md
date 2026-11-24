# Slice 01 — Generalized 3-Tier Primitives

## Contract Unlocked

The graph engine supports **typed option spaces (`parameters`)**, **compatibility & physical interfaces (`compatibleWith`, `incompatibleWith`, `qualifiers.interface`)**, **per-system expected checklists (`expectedProfile`)**, and **plain-English interpretation bands (`propertyGuides.bands`)**—with **zero domain-specific schema columns** and strict controlled-vocabulary enforcement via `data/guides/`.

---

## API Seams & Data Contracts

### 1. Schema Extensions (`graph.schema.json`, `guide.schema.json`, `model.py`)
- **`graph.schema.json`:**
  - Add `"compatibleWith"` and `"incompatibleWith"` to `#/$defs/statement/properties/predicate/enum`.
  - Add optional `"interface"` (string) to `#/$defs/statement/properties/qualifiers/properties`.
  - Add optional `"parameters"` (object mapping registered parameter key → enum list, `{min, max, step?, unit?}` range, or `{values: [...], unit?}` discrete list) on `#/$defs/node` (allowed only when `kind == "productModel"`).
  - Add optional `"expectedProfile"` (`{properties?: [str], parameters?: [str], interfaces?: [str]}`) on `#/$defs/node` (allowed only when `kind == "referenceDesign"`).
- **`guide.schema.json`:**
  - Add optional `"bands"` array (`[{label, min?, max?, meaning}]`) on `#/$defs/propertyGuide`.
  - Add optional top-level `"parameters"` (`{<key>: {title?, shape: enum|range|values, role: aesthetic|dimensional|performance|interface, unit?, summary}}`) and `"interfaces"` (`{<key>: {title?, summary, typicalMates?}}`).
- **`model.py`:**
  - Add `LINK_KINDS` entries:
    - `"compatibleWith": ({"referenceDesign", "productModel", "productVariant", "material"}, {"referenceDesign", "productModel", "productVariant", "material"})`
    - `"incompatibleWith": ({"material", "referenceDesign", "productModel", "productVariant"}, {"material", "referenceDesign", "productModel", "productVariant"})`

### 2. Compiler & Controlled-Vocabulary Validator (`compiler.py`, `validator.py`)
- `compiler.py` loads `parameterGuides:` (`data/guides/parameters.yaml`) and `interfaceGuides:` (`data/guides/interfaces.yaml`) into `bundle.guide["parameters"]` and `bundle.guide["interfaces"]`, and carries `parameters` / `expectedProfile` on compiled nodes.
- `validator.py` enforces **Tier 2 controlled vocabulary**:
  - Every key in `node.parameters` must exist in `bundle.guide["parameters"]` and match its registered `shape` (`enum`, `range`, or `values`).
  - Every `qualifiers.interface` value on a statement must exist in `bundle.guide["interfaces"]`.
  - Every key in `referenceDesign.expectedProfile.{properties,parameters,interfaces}` must exist in the corresponding `data/guides/` registry.
  - `parameters` only allowed on `productModel`; `expectedProfile` only allowed on `referenceDesign`.

### 3. SQLite v2 Persistence & API (`schema.sql`, `store.py`, `server.py`)
- **`schema.sql` additions:**
  - `nodes`: add `parameters_json TEXT`, `expected_profile_json TEXT`.
  - `statements`: add `qual_interface TEXT`.
  - `property_guides`: add `bands_json TEXT`.
  - New tables: `parameter_guides (parameter PRIMARY KEY, title, shape NOT NULL, role NOT NULL, unit, summary NOT NULL)` and `interface_guides (interface PRIMARY KEY, title, summary NOT NULL)`.
- **`store.py`:**
  - Round-trip `parameters`, `expectedProfile`, `qualifiers.interface`, `propertyGuides.bands`, `parameter_guides`, and `interface_guides` losslessly.
  - `explain(key)` also resolves registered parameters and interfaces.
  - `gaps(..., tier="catalog"|"assembly"|"atomic")` checks `expectedProfile` on `productModel`s realizing a `referenceDesign` with an `expectedProfile` (flagging missing expected `parameters` / `properties` as `profile-missing-parameter` / `profile-missing-property` warnings/gaps).

---

## Playable Checkpoint & Verification

1. `python -m building_materials validate` and `build` succeed on existing `data/`.
2. Smoke test in temp dir proves:
   - Unregistered parameter name or interface name fails `validate` with a clear controlled-vocabulary error.
   - Valid `parameters`, `compatibleWith`/`incompatibleWith` + `qualifiers.interface`, `expectedProfile`, and `propertyGuides.bands` compile to SQLite and return intact via `GET /api/nodes/<id>` and `GET /api/explain/<key>`.

## Delegated Decisions
- Exact JSON serialization layout for `parameters_json` / `bands_json` in `store.py`.
- Whether `expectedProfile` gap checks emit under category `"properties"` or `"profile"`.
