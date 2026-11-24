"""Entity-centric YAML + CSV SKU matrix compiler lowering data/ into canonical IR."""

import copy
import csv
import hashlib
import json
from pathlib import Path
import re

import yaml

from .model import CompiledBundle, CompileError, Provenance, to_si_quantity


class SafeStringLoader(yaml.SafeLoader):
    """YAML SafeLoader that keeps ISO dates/timestamps as plain strings."""


# Strip implicit timestamp resolvers so YYYY-MM-DD stays str for JSON Schema `format: date`.
for _ch, _resolvers in list(SafeStringLoader.yaml_implicit_resolvers.items()):
    SafeStringLoader.yaml_implicit_resolvers[_ch] = [
        (tag, regexp) for tag, regexp in _resolvers if tag != "tag:yaml.org,2002:timestamp"
    ]


NODE_FIELDS = {
    "id",
    "kind",
    "label",
    "description",
    "revision",
    "scale",
    "stage",
    "identifiers",
    "source",
}
ENTITY_CONTAINER_FIELDS = NODE_FIELDS | {
    "defaults",
    "links",
    "properties",
    "guide",
    "variantDefaults",
    "variantsTable",
}
DEFAULTABLE_FIELDS = (
    "basis",
    "scope",
    "method",
    "conditions",
    "geography",
    "pcr",
    "validUntil",
    "plantActor",
    "qualifiers",
    "evidence",
)
STATEMENT_OPTIONAL_FIELDS = (
    "scope",
    "method",
    "conditions",
    "geography",
    "pcr",
    "validUntil",
    "plantActor",
    "derivedFrom",
)
SLUG_SANITIZE_RE = re.compile(r"[^a-z0-9._-]+")
PLACEHOLDER_RE = re.compile(r"\{([A-Za-z0-9_.-]+)\}")


def load_yaml(path: Path):
    """Parse a YAML file with date-safe string preservation."""
    try:
        return yaml.load(path.read_text(encoding="utf-8"), Loader=SafeStringLoader)
    except yaml.YAMLError as exc:
        raise CompileError(f"YAML parse error: {exc}", Provenance(str(path))) from exc


def compute_data_fingerprint(data_dir: Path) -> str:
    """Compute a deterministic SHA-256 fingerprint across all YAML and CSV files under data/."""
    hasher = hashlib.sha256()
    if not data_dir.is_dir():
        return hasher.hexdigest()
    files = sorted(
        p for p in data_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in {".yaml", ".yml", ".csv"}
    )
    for path in files:
        rel = path.relative_to(data_dir).as_posix()
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def _merge_defaults(parent: dict, child: dict | None) -> dict:
    """Deep-merge file/entity defaults without mutating inputs."""
    merged = copy.deepcopy(parent)
    if not child:
        return merged
    for key in DEFAULTABLE_FIELDS:
        if key not in child:
            continue
        if key == "qualifiers" and isinstance(merged.get("qualifiers"), dict) and isinstance(child[key], dict):
            q = copy.deepcopy(merged["qualifiers"])
            q.update(copy.deepcopy(child[key]))
            merged["qualifiers"] = q
        else:
            merged[key] = copy.deepcopy(child[key])
    return merged


def _resolve_evidence(item: dict, defaults: dict, prov: Provenance) -> list[dict]:
    """Resolve item evidence, supporting shorthand `locator:` overlay on single default source."""
    default_ev = defaults.get("evidence")
    raw_ev = item.get("evidence")
    shorthand_locator = item.get("locator")

    if raw_ev is not None and shorthand_locator is not None:
        raise CompileError("Specify either 'evidence' or shorthand 'locator', not both", prov)

    if shorthand_locator is not None:
        if not isinstance(shorthand_locator, dict):
            raise CompileError("Shorthand 'locator' must be a mapping", prov)
        if not default_ev or not isinstance(default_ev, list) or len(default_ev) != 1:
            raise CompileError(
                "Shorthand 'locator' requires a single default evidence entry in file or entity defaults",
                prov,
            )
        base = copy.deepcopy(default_ev[0])
        loc = copy.deepcopy(base.get("locator") or {})
        loc.update(copy.deepcopy(shorthand_locator))
        base["locator"] = loc
        return [base]

    if raw_ev is None:
        if default_ev is None:
            raise CompileError("Statement is missing 'evidence' (and no default evidence is set)", prov)
        return copy.deepcopy(default_ev)

    if not isinstance(raw_ev, list) or not raw_ev:
        raise CompileError("'evidence' must be a non-empty list", prov)

    resolved = []
    for entry in raw_ev:
        if not isinstance(entry, dict):
            raise CompileError("Each evidence entry must be a mapping", prov)
        out = copy.deepcopy(entry)
        if "source" not in out:
            if default_ev and len(default_ev) == 1 and "source" in default_ev[0]:
                out["source"] = default_ev[0]["source"]
                base_loc = copy.deepcopy(default_ev[0].get("locator") or {})
                base_loc.update(out.get("locator") or {})
                out["locator"] = base_loc
            else:
                raise CompileError("Evidence entry missing 'source'", prov)
        resolved.append(out)
    return resolved


def _sanitize_slug(text: str) -> str:
    cleaned = SLUG_SANITIZE_RE.sub("-", text.lower()).strip(".-")
    return cleaned or "stmt"


def _synthesize_statement_id(
    stmt: dict,
    *,
    seen_ids: set[str],
    explicit_ids: set[str],
    prov: Provenance,
) -> str:
    """Use explicit ID if given; otherwise synthesize a readable deterministic ID."""
    if "id" in stmt and stmt["id"] is not None:
        sid = str(stmt["id"])
        if sid in seen_ids:
            raise CompileError(f"Duplicate explicit statement ID '{sid}'", prov)
        explicit_ids.add(sid)
        seen_ids.add(sid)
        return sid

    subject = stmt["subject"]
    parts = [subject]
    if "predicate" in stmt:
        parts.extend([stmt["predicate"], stmt["target"]])
        qual = stmt.get("qualifiers") or {}
        if qual.get("role"):
            parts.append(str(qual["role"]))
        elif qual.get("position"):
            parts.append(str(qual["position"]))
    else:
        parts.append(stmt["property"])
        if stmt.get("scope"):
            parts.append(str(stmt["scope"]))

    base = _sanitize_slug(".".join(parts))
    if base not in seen_ids:
        seen_ids.add(base)
        return base

    canonical_key = {
        "subject": stmt["subject"],
        "predicate": stmt.get("predicate"),
        "target": stmt.get("target"),
        "property": stmt.get("property"),
        "scope": stmt.get("scope"),
        "qualifiers": stmt.get("qualifiers"),
        "value": stmt.get("value"),
        "quantity": stmt.get("quantity"),
        "state": stmt.get("state"),
        "conditions": stmt.get("conditions"),
        "geography": stmt.get("geography"),
        "validUntil": stmt.get("validUntil"),
    }
    digest = hashlib.sha256(
        json.dumps(canonical_key, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:6]
    candidate = f"{base}.{digest}"
    counter = 2
    while candidate in seen_ids:
        candidate = f"{base}.{digest}.{counter}"
        counter += 1
    seen_ids.add(candidate)
    return candidate


def _lower_statement(
    subject_id: str,
    item: dict,
    defaults: dict,
    *,
    is_link: bool,
    seen_ids: set[str],
    explicit_ids: set[str],
    prov: Provenance,
) -> dict:
    if not isinstance(item, dict):
        raise CompileError("Link/property item must be a mapping", prov)

    stmt: dict = {"subject": subject_id}
    if "id" in item:
        stmt["id"] = item["id"]

    if is_link:
        if "predicate" not in item or "target" not in item:
            raise CompileError("Link item requires 'predicate' and 'target'", prov)
        stmt["predicate"] = item["predicate"]
        stmt["target"] = item["target"]
    else:
        if "property" not in item:
            raise CompileError("Property item requires 'property'", prov)
        stmt["property"] = item["property"]
        for val_key in ("value", "quantity", "state"):
            if val_key in item:
                stmt[val_key] = copy.deepcopy(item[val_key])
        if "quantity" in stmt:
            si = to_si_quantity(stmt["quantity"])
            if si is not None:
                stmt["siQuantity"] = si

    basis = item.get("basis", defaults.get("basis"))
    if not basis:
        raise CompileError("Statement is missing 'basis' (and no default basis is set)", prov)
    stmt["basis"] = basis

    for opt_key in STATEMENT_OPTIONAL_FIELDS:
        if opt_key in item:
            stmt[opt_key] = copy.deepcopy(item[opt_key])
        elif opt_key in defaults and opt_key != "derivedFrom":
            stmt[opt_key] = copy.deepcopy(defaults[opt_key])

    qual = copy.deepcopy(defaults.get("qualifiers") or {})
    if isinstance(item.get("qualifiers"), dict):
        qual.update(copy.deepcopy(item["qualifiers"]))
    if qual:
        stmt["qualifiers"] = qual

    stmt["evidence"] = _resolve_evidence(item, defaults, prov)
    stmt["id"] = _synthesize_statement_id(
        stmt, seen_ids=seen_ids, explicit_ids=explicit_ids, prov=prov
    )
    return stmt


def _interpolate_str(template: str, row: dict[str, str], prov: Provenance) -> str:
    def _replace(match: re.Match) -> str:
        col = match.group(1)
        if col not in row:
            raise CompileError(f"Unknown template column '{{{col}}}'", prov)
        return str(row[col]).strip()

    return PLACEHOLDER_RE.sub(_replace, template)


def _interpolate_obj(obj, row: dict[str, str], prov: Provenance):
    if isinstance(obj, str):
        return _interpolate_str(obj, row, prov)
    if isinstance(obj, list):
        return [_interpolate_obj(v, row, prov) for v in obj]
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            val = _interpolate_obj(v, row, prov)
            if k == "page" and isinstance(val, str):
                try:
                    val = int(val)
                except ValueError as exc:
                    raise CompileError(f"Locator page '{val}' must be an integer", prov) from exc
            out[k] = val
        return out
    return copy.deepcopy(obj)


def _expand_variants_table(
    model_id: str,
    table_spec: dict,
    *,
    yaml_path: Path,
    data_dir: Path,
    entity_defaults: dict,
    seen_node_ids: set[str],
    seen_stmt_ids: set[str],
    explicit_stmt_ids: set[str],
    nodes: list[dict],
    statements: list[dict],
    provenance: dict[str, Provenance],
) -> None:
    rel_yaml = yaml_path.relative_to(data_dir).as_posix()
    spec_prov = Provenance(rel_yaml)
    if not isinstance(table_spec, dict):
        raise CompileError("'variantsTable' must be a mapping", spec_prov)

    id_template = table_spec.get("idTemplate")
    label_template = table_spec.get("labelTemplate")
    if not id_template or not label_template:
        raise CompileError("'variantsTable' requires 'idTemplate' and 'labelTemplate'", spec_prov)

    if "csv" in table_spec and "rows" in table_spec:
        raise CompileError("'variantsTable' must specify either 'csv' or 'rows', not both", spec_prov)

    table_defaults = _merge_defaults(entity_defaults, table_spec.get("defaults"))

    if "csv" in table_spec:
        csv_path = (yaml_path.parent / table_spec["csv"]).resolve()
        if not csv_path.is_file():
            raise CompileError(f"variantsTable CSV not found: {table_spec['csv']}", spec_prov)
        source_rel = csv_path.relative_to(data_dir.resolve()).as_posix()
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = [(idx, row) for idx, row in enumerate(reader, start=2)]
    elif "rows" in table_spec:
        raw_rows = table_spec["rows"]
        if not isinstance(raw_rows, list):
            raise CompileError("'variantsTable.rows' must be a list", spec_prov)
        source_rel = rel_yaml
        rows = [(idx, {k: str(v) for k, v in row.items()}) for idx, row in enumerate(raw_rows, start=1)]
    else:
        raise CompileError("'variantsTable' requires 'csv' or 'rows'", spec_prov)

    columns = table_spec.get("columns") or {}
    if not isinstance(columns, dict):
        raise CompileError("'variantsTable.columns' must be a mapping", spec_prov)

    template_links = table_spec.get("links") or []

    for row_num, row in rows:
        row_prov = Provenance(source_rel, row=row_num)
        variant_id = _interpolate_str(id_template, row, row_prov)
        variant_label = _interpolate_str(label_template, row, row_prov)
        if variant_id in seen_node_ids:
            raise CompileError(f"Duplicate node ID '{variant_id}' from variantsTable", row_prov)
        seen_node_ids.add(variant_id)

        node: dict = {
            "id": variant_id,
            "kind": "productVariant",
            "label": variant_label,
        }
        if "identifiers" in table_spec:
            idents = []
            for ident_tpl in table_spec["identifiers"]:
                val = _interpolate_str(ident_tpl["value"], row, row_prov)
                if val:
                    idents.append({"namespace": ident_tpl["namespace"], "value": val})
            if idents:
                node["identifiers"] = idents
        nodes.append(node)
        provenance[variant_id] = row_prov

        row_defaults = _interpolate_obj(table_defaults, row, row_prov)

        # Automatic `isVariantOf` -> parent productModel
        iv_stmt = _lower_statement(
            variant_id,
            {"predicate": "isVariantOf", "target": model_id},
            row_defaults,
            is_link=True,
            seen_ids=seen_stmt_ids,
            explicit_ids=explicit_stmt_ids,
            prov=row_prov,
        )
        statements.append(iv_stmt)
        provenance[iv_stmt["id"]] = row_prov

        # Row-templated links
        for link_tpl in template_links:
            resolved_link = _interpolate_obj(link_tpl, row, row_prov)
            if not resolved_link.get("target"):
                continue
            l_stmt = _lower_statement(
                variant_id,
                resolved_link,
                row_defaults,
                is_link=True,
                seen_ids=seen_stmt_ids,
                explicit_ids=explicit_stmt_ids,
                prov=row_prov,
            )
            statements.append(l_stmt)
            provenance[l_stmt["id"]] = row_prov

        # Row-templated property columns
        for col_name, col_spec in columns.items():
            if col_name not in row:
                raise CompileError(f"CSV missing configured column '{col_name}'", row_prov)
            raw_val = (row[col_name] or "").strip()
            if not raw_val:
                continue

            prop_item: dict = {"property": col_spec["property"]}
            for copy_key in ("basis", "scope", "method", "conditions", "geography", "pcr", "validUntil", "plantActor"):
                if copy_key in col_spec:
                    prop_item[copy_key] = _interpolate_obj(col_spec[copy_key], row, row_prov)

            if "locatorColumn" in col_spec:
                col_loc = _interpolate_str(str(col_spec["locatorColumn"]), row, row_prov)
                if col_loc:
                    prop_item["locator"] = {"column": col_loc}

            low = raw_val.lower()
            if low in {"unknown", "withheld"}:
                prop_item["state"] = low
            elif col_spec.get("valueType") == "string":
                prop_item["value"] = raw_val
            elif col_spec.get("valueType") == "boolean":
                if low in {"true", "1", "yes"}:
                    prop_item["value"] = True
                elif low in {"false", "0", "no"}:
                    prop_item["value"] = False
                else:
                    raise CompileError(
                        f"Column '{col_name}' expects boolean, got '{raw_val}'", row_prov
                    )
            else:
                try:
                    num = float(raw_val)
                except ValueError as exc:
                    raise CompileError(
                        f"Column '{col_name}' expects numeric value (or unknown/withheld), got '{raw_val}'",
                        row_prov,
                    ) from exc
                qty: dict = {"value": num, "unit": col_spec["unit"]}
                if "quantityBasis" in col_spec:
                    qty["basis"] = _interpolate_str(str(col_spec["quantityBasis"]), row, row_prov)
                prop_item["quantity"] = qty

            p_stmt = _lower_statement(
                variant_id,
                prop_item,
                row_defaults,
                is_link=False,
                seen_ids=seen_stmt_ids,
                explicit_ids=explicit_stmt_ids,
                prov=row_prov,
            )
            statements.append(p_stmt)
            provenance[p_stmt["id"]] = row_prov


def _apply_model_inheritance(
    nodes: list[dict],
    statements: list[dict],
    model_variant_defaults: dict[str, dict],
    *,
    seen_stmt_ids: set[str],
    explicit_stmt_ids: set[str],
    provenance: dict[str, Provenance],
) -> None:
    """Materialize inherited productModel properties and variantDefaults onto child productVariants."""
    nodes_by_id = {n["id"]: n for n in nodes}
    by_subject: dict[str, list[dict]] = {}
    for stmt in statements:
        by_subject.setdefault(stmt["subject"], []).append(stmt)

    # Identify each productVariant's parent productModel (validator enforces at-most-one).
    variant_to_model: list[tuple[str, str]] = []
    for node in nodes:
        if node["kind"] != "productVariant":
            continue
        vid = node["id"]
        parents = [
            s["target"]
            for s in by_subject.get(vid, ())
            if s.get("predicate") == "isVariantOf" and nodes_by_id.get(s["target"], {}).get("kind") == "productModel"
        ]
        if len(parents) == 1:
            variant_to_model.append((vid, parents[0]))

    new_statements: list[dict] = []
    for vid, mid in variant_to_model:
        v_prov = provenance.get(vid, Provenance("<inherited>"))
        existing = by_subject.get(vid, ())

        existing_prop_keys = {
            (s["property"], s.get("scope") or "")
            for s in existing
            if "property" in s
        }
        existing_link_keys = {
            (
                s["predicate"],
                (s.get("qualifiers") or {}).get("role") or "",
                (s.get("qualifiers") or {}).get("position") or "",
            )
            for s in existing
            if "predicate" in s
        }

        # 1. Inherit direct productModel properties unless overridden on (property, scope).
        for m_stmt in by_subject.get(mid, ()):
            if "property" not in m_stmt:
                continue
            pkey = (m_stmt["property"], m_stmt.get("scope") or "")
            if pkey in existing_prop_keys:
                continue
            cloned = copy.deepcopy(m_stmt)
            cloned.pop("id", None)
            cloned["subject"] = vid
            cloned["inheritedFrom"] = m_stmt["id"]
            cloned["id"] = _synthesize_statement_id(
                cloned, seen_ids=seen_stmt_ids, explicit_ids=explicit_stmt_ids, prov=v_prov
            )
            new_statements.append(cloned)
            provenance[cloned["id"]] = v_prov
            existing_prop_keys.add(pkey)

        # 2. Inherit productModel.variantDefaults links and properties unless overridden.
        vdefs = model_variant_defaults.get(mid)
        if not vdefs:
            continue
        base_defaults = vdefs["defaults"]
        for link_tpl in vdefs.get("links") or ():
            qual = link_tpl.get("qualifiers") or {}
            lkey = (
                link_tpl["predicate"],
                qual.get("role") or "",
                qual.get("position") or "",
            )
            if lkey in existing_link_keys:
                continue
            l_stmt = _lower_statement(
                vid,
                link_tpl,
                base_defaults,
                is_link=True,
                seen_ids=seen_stmt_ids,
                explicit_ids=explicit_stmt_ids,
                prov=v_prov,
            )
            l_stmt["inheritedFrom"] = mid
            new_statements.append(l_stmt)
            provenance[l_stmt["id"]] = v_prov
            existing_link_keys.add(lkey)

        for prop_tpl in vdefs.get("properties") or ():
            pkey = (prop_tpl["property"], prop_tpl.get("scope", base_defaults.get("scope")) or "")
            if pkey in existing_prop_keys:
                continue
            p_stmt = _lower_statement(
                vid,
                prop_tpl,
                base_defaults,
                is_link=False,
                seen_ids=seen_stmt_ids,
                explicit_ids=explicit_stmt_ids,
                prov=v_prov,
            )
            p_stmt["inheritedFrom"] = mid
            new_statements.append(p_stmt)
            provenance[p_stmt["id"]] = v_prov
            existing_prop_keys.add(pkey)

    statements.extend(new_statements)


def compile_dir(data_dir: Path) -> CompiledBundle:
    """Recursively load and lower all YAML + CSV files under data_dir into a CompiledBundle."""
    if not data_dir.is_dir():
        raise CompileError(f"Data directory not found: {data_dir}")

    yaml_files = sorted(
        p for p in data_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in {".yaml", ".yml"}
    )
    if not yaml_files:
        raise CompileError(f"No YAML files found under {data_dir}")

    nodes: list[dict] = []
    statements: list[dict] = []
    guide_nodes: dict[str, dict] = {}
    guide_props: dict[str, dict] = {}
    provenance: dict[str, Provenance] = {}
    model_variant_defaults: dict[str, dict] = {}
    seen_node_ids: set[str] = set()
    seen_stmt_ids: set[str] = set()
    explicit_stmt_ids: set[str] = set()

    for path in yaml_files:
        rel = path.relative_to(data_dir).as_posix()
        file_prov = Provenance(rel)
        doc = load_yaml(path)
        if doc is None:
            continue
        if not isinstance(doc, dict):
            raise CompileError("Top-level YAML document must be a mapping", file_prov)

        if "propertyGuides" in doc:
            pg = doc["propertyGuides"]
            if not isinstance(pg, dict):
                raise CompileError("'propertyGuides' must be a mapping", file_prov)
            for prop_key, prop_val in pg.items():
                if prop_key in guide_props:
                    raise CompileError(f"Duplicate propertyGuide '{prop_key}'", file_prov)
                guide_props[prop_key] = copy.deepcopy(prop_val)
                provenance[f"propertyGuide:{prop_key}"] = file_prov

        file_defaults = _merge_defaults({}, doc.get("defaults"))

        if "entities" in doc:
            raw_entities = doc["entities"]
            if not isinstance(raw_entities, list):
                raise CompileError("'entities' must be a list", file_prov)
        elif "id" in doc:
            raw_entities = [doc]
        elif "propertyGuides" in doc:
            raw_entities = []
        else:
            raise CompileError(
                "YAML file must contain 'entities', a single entity with 'id', or 'propertyGuides'",
                file_prov,
            )

        for entity in raw_entities:
            if not isinstance(entity, dict):
                raise CompileError("Each entity must be a mapping", file_prov)
            unknown_keys = set(entity.keys()) - ENTITY_CONTAINER_FIELDS
            if unknown_keys:
                raise CompileError(
                    f"Unknown entity fields: {', '.join(sorted(unknown_keys))}", file_prov
                )
            node_id = entity.get("id")
            if not isinstance(node_id, str) or not node_id:
                raise CompileError("Entity is missing string 'id'", file_prov)
            if node_id in seen_node_ids:
                raise CompileError(f"Duplicate node ID '{node_id}'", file_prov)
            seen_node_ids.add(node_id)

            node = {k: copy.deepcopy(entity[k]) for k in NODE_FIELDS if k in entity}
            nodes.append(node)
            provenance[node_id] = file_prov

            entity_defaults = _merge_defaults(file_defaults, entity.get("defaults"))

            for link in entity.get("links") or ():
                stmt = _lower_statement(
                    node_id,
                    link,
                    entity_defaults,
                    is_link=True,
                    seen_ids=seen_stmt_ids,
                    explicit_ids=explicit_stmt_ids,
                    prov=file_prov,
                )
                statements.append(stmt)
                provenance[stmt["id"]] = file_prov

            for prop in entity.get("properties") or ():
                stmt = _lower_statement(
                    node_id,
                    prop,
                    entity_defaults,
                    is_link=False,
                    seen_ids=seen_stmt_ids,
                    explicit_ids=explicit_stmt_ids,
                    prov=file_prov,
                )
                statements.append(stmt)
                provenance[stmt["id"]] = file_prov

            if "guide" in entity:
                if node_id in guide_nodes:
                    raise CompileError(f"Duplicate guide entry for node '{node_id}'", file_prov)
                guide_nodes[node_id] = copy.deepcopy(entity["guide"])

            if "variantDefaults" in entity:
                if node.get("kind") != "productModel":
                    raise CompileError("'variantDefaults' is only allowed on productModel entities", file_prov)
                vd = entity["variantDefaults"]
                if not isinstance(vd, dict):
                    raise CompileError("'variantDefaults' must be a mapping", file_prov)
                model_variant_defaults[node_id] = {
                    "defaults": _merge_defaults(entity_defaults, vd.get("defaults")),
                    "links": copy.deepcopy(vd.get("links") or []),
                    "properties": copy.deepcopy(vd.get("properties") or []),
                }

            if "variantsTable" in entity:
                if node.get("kind") != "productModel":
                    raise CompileError("'variantsTable' is only allowed on productModel entities", file_prov)
                _expand_variants_table(
                    node_id,
                    entity["variantsTable"],
                    yaml_path=path,
                    data_dir=data_dir,
                    entity_defaults=entity_defaults,
                    seen_node_ids=seen_node_ids,
                    seen_stmt_ids=seen_stmt_ids,
                    explicit_stmt_ids=explicit_stmt_ids,
                    nodes=nodes,
                    statements=statements,
                    provenance=provenance,
                )

    _apply_model_inheritance(
        nodes,
        statements,
        model_variant_defaults,
        seen_stmt_ids=seen_stmt_ids,
        explicit_stmt_ids=explicit_stmt_ids,
        provenance=provenance,
    )

    return CompiledBundle(
        nodes=nodes,
        statements=statements,
        guide={"schemaVersion": 1, "properties": guide_props, "nodes": guide_nodes},
        provenance=provenance,
        fingerprint=compute_data_fingerprint(data_dir),
    )
