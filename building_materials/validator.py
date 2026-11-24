"""Static schema, taxonomy, inheritance, and EPD invariant validator."""

import graphlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

from .model import (
    CompiledBundle,
    EN15804_SCOPE_RE,
    EPD_PROPERTIES,
    GraphValidationError,
    ID_RE,
    LINK_KINDS,
    ROOT,
    UNIQUE_IDENTIFIER_NAMESPACES,
)


def _read_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_bundle(bundle: CompiledBundle) -> CompiledBundle:
    """Validate a CompiledBundle against JSON Schemas and static graph invariants."""
    graph_payload = {
        "schemaVersion": 1,
        "nodes": bundle.nodes,
        "statements": bundle.statements,
    }
    graph_validator = Draft202012Validator(
        _read_schema(ROOT / "graph.schema.json"),
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )
    try:
        graph_validator.validate(graph_payload)
    except ValidationError as exc:
        loc = "/".join(map(str, exc.absolute_path))
        prov = None
        if len(exc.absolute_path) >= 2 and exc.absolute_path[0] in {"nodes", "statements"}:
            collection = graph_payload[exc.absolute_path[0]]
            idx = exc.absolute_path[1]
            if isinstance(idx, int) and 0 <= idx < len(collection):
                item_id = collection[idx].get("id")
                if item_id:
                    prov = bundle.provenance.get(item_id)
        raise GraphValidationError(f"Invalid graph at /{loc}: {exc.message}", prov) from exc

    guide_validator = Draft202012Validator(
        _read_schema(ROOT / "guide.schema.json"),
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )
    try:
        guide_validator.validate(bundle.guide)
    except ValidationError as exc:
        loc = "/".join(map(str, exc.absolute_path))
        raise GraphValidationError(f"Invalid guide at /{loc}: {exc.message}") from exc

    guide_props = bundle.guide.get("properties") or {}
    guide_params = bundle.guide.get("parameters") or {}
    guide_ifaces = bundle.guide.get("interfaces") or {}

    for prop_key, pg in guide_props.items():
        for band in pg.get("bands") or ():
            if "min" in band and "max" in band and band["min"] > band["max"]:
                raise GraphValidationError(
                    f"propertyGuide '{prop_key}' band '{band['label']}' min exceeds max",
                    bundle.provenance.get(f"propertyGuide:{prop_key}"),
                )

    nodes_by_id: dict[str, dict] = {}
    unique_ext_ids: dict[tuple[str, str, str], str] = {}
    for node in bundle.nodes:
        nid = node["id"]
        prov = bundle.provenance.get(nid)
        if not ID_RE.match(nid):
            raise GraphValidationError(
                f"Node ID '{nid}' must match lowercase dotted convention (^[a-z0-9]+([.-][a-z0-9]+)*$)",
                prov,
            )
        if nid in nodes_by_id:
            raise GraphValidationError(f"Duplicate node ID: {nid}", prov)
        if "parameters" in node:
            if node["kind"] != "productModel":
                raise GraphValidationError(f"{nid}: 'parameters' is only allowed on productModel nodes", prov)
            for pkey, pval in node["parameters"].items():
                if pkey not in guide_params:
                    raise GraphValidationError(
                        f"{nid}: unregistered parameter '{pkey}' (register it in data/guides/parameters/)",
                        prov,
                    )
                shape = guide_params[pkey]["shape"]
                if shape in {"enum", "values"}:
                    if not isinstance(pval, dict) or "values" not in pval or not isinstance(pval["values"], list):
                        raise GraphValidationError(
                            f"{nid}: parameter '{pkey}' has registered shape '{shape}' (expected values list)",
                            prov,
                        )
                elif shape == "range":
                    if not isinstance(pval, dict) or "min" not in pval or "max" not in pval:
                        raise GraphValidationError(
                            f"{nid}: parameter '{pkey}' has registered shape 'range' (expected {{min, max}})",
                            prov,
                        )
                    if pval["min"] > pval["max"]:
                        raise GraphValidationError(f"{nid}: parameter '{pkey}' min exceeds max", prov)
        if "expectedProfile" in node:
            if node["kind"] != "referenceDesign":
                raise GraphValidationError(f"{nid}: 'expectedProfile' is only allowed on referenceDesign nodes", prov)
            ep = node["expectedProfile"]
            for prop_k in ep.get("properties", ()):
                if prop_k not in guide_props:
                    raise GraphValidationError(f"{nid}: expectedProfile references unregistered property '{prop_k}'", prov)
            for param_k in ep.get("parameters", ()):
                if param_k not in guide_params:
                    raise GraphValidationError(f"{nid}: expectedProfile references unregistered parameter '{param_k}'", prov)
            for iface_k in ep.get("interfaces", ()):
                if iface_k not in guide_ifaces:
                    raise GraphValidationError(f"{nid}: expectedProfile references unregistered interface '{iface_k}'", prov)
        seen_idents: set[tuple[str, str]] = set()
        for ident in node.get("identifiers", ()):
            ns = ident["namespace"].strip()
            val = ident["value"].strip()
            if not ns or not val:
                raise GraphValidationError(f"{nid}: identifier namespace and value must be non-empty", prov)
            key = (ns, val)
            if key in seen_idents:
                raise GraphValidationError(f"{nid}: duplicate identifier ({ns}: {val})", prov)
            seen_idents.add(key)
            if ns in UNIQUE_IDENTIFIER_NAMESPACES:
                ext_key = (node["kind"], ns, val.lower())
                if ext_key in unique_ext_ids:
                    owner = unique_ext_ids[ext_key]
                    raise GraphValidationError(
                        f"{nid}: unique identifier {ns}:{val} is already owned by '{owner}'",
                        prov,
                    )
                unique_ext_ids[ext_key] = nid
        nodes_by_id[nid] = node

    for nid, node in nodes_by_id.items():
        if params := node.get("parameters"):
            prov = bundle.provenance.get(nid)
            for pkey, pval in params.items():
                for citation in pval.get("evidence", ()):
                    src = nodes_by_id.get(citation["source"])
                    if src is None:
                        raise GraphValidationError(f"{nid}.parameters.{pkey}: unknown evidence source '{citation['source']}'", prov)
                    if src["kind"] != "source":
                        raise GraphValidationError(f"{nid}.parameters.{pkey}: evidence must cite a source node", prov)
                    if src["source"]["mediaType"] == "application/pdf" and "page" not in citation["locator"]:
                        raise GraphValidationError(f"{nid}.parameters.{pkey}: PDF evidence requires locator.page", prov)

    stmts_by_id: dict[str, dict] = {}
    for stmt in bundle.statements:
        sid = stmt["id"]
        if sid in stmts_by_id:
            raise GraphValidationError(f"Duplicate statement ID: {sid}", bundle.provenance.get(sid))
        stmts_by_id[sid] = stmt

    parts = graphlib.TopologicalSorter()
    derivations = graphlib.TopologicalSorter()
    variant_parents: dict[str, list[str]] = {}

    for stmt in bundle.statements:
        sid = stmt["id"]
        prov = bundle.provenance.get(sid)
        subject = nodes_by_id.get(stmt["subject"])
        if subject is None:
            raise GraphValidationError(f"{sid}: unknown subject '{stmt['subject']}'", prov)

        if target_id := stmt.get("target"):
            target = nodes_by_id.get(target_id)
            if target is None:
                raise GraphValidationError(f"{sid}: unknown target '{target_id}'", prov)
            kinds = LINK_KINDS.get(stmt["predicate"])
            if kinds and (
                subject["kind"] not in kinds[0]
                or (kinds[1] is not None and target["kind"] not in kinds[1])
            ):
                raise GraphValidationError(
                    f"{sid}: invalid endpoint kinds ({subject['kind']} -> {target['kind']}) for {stmt['predicate']}",
                    prov,
                )
            if stmt["predicate"] == "hasPart":
                parts.add(subject["id"], target_id)
            elif stmt["predicate"] == "isVariantOf":
                variant_parents.setdefault(subject["id"], []).append(target_id)

        if iface := (stmt.get("qualifiers") or {}).get("interface"):
            if iface not in guide_ifaces:
                raise GraphValidationError(
                    f"{sid}: unregistered qualifiers.interface '{iface}' (register it in data/guides/interfaces/)",
                    prov,
                )

        if plant_id := stmt.get("plantActor"):
            plant = nodes_by_id.get(plant_id)
            if plant is None or plant["kind"] != "actor":
                raise GraphValidationError(
                    f"{sid}: plantActor '{plant_id}' must reference an existing actor node",
                    prov,
                )

        if prop := stmt.get("property"):
            if prop in EPD_PROPERTIES:
                scope = stmt.get("scope")
                if not scope or not EN15804_SCOPE_RE.match(scope):
                    raise GraphValidationError(
                        f"{sid}: EPD property '{prop}' requires valid EN 15804 scope (e.g. 'A1-A3', 'A1-A3+C1-C4+D'), got {scope!r}",
                        prov,
                    )
                if qty := stmt.get("quantity"):
                    if "co2e" not in qty["unit"].lower():
                        raise GraphValidationError(
                            f"{sid}: EPD property '{prop}' quantity.unit must include 'CO2e', got {qty['unit']!r}",
                            prov,
                        )
                    if not qty.get("basis") or not str(qty["basis"]).strip():
                        raise GraphValidationError(
                            f"{sid}: EPD property '{prop}' quantity requires declared unit in quantity.basis",
                            prov,
                        )

        for quantity in (
            stmt.get("quantity"),
            stmt.get("siQuantity"),
            stmt.get("qualifiers", {}).get("quantity"),
        ):
            if quantity and "min" in quantity and quantity["min"] > quantity["max"]:
                raise GraphValidationError(f"{sid}: quantity minimum exceeds maximum", prov)

        for citation in stmt["evidence"]:
            src = nodes_by_id.get(citation["source"])
            if src is None:
                raise GraphValidationError(f"{sid}: unknown evidence source '{citation['source']}'", prov)
            if src["kind"] != "source":
                raise GraphValidationError(f"{sid}: evidence must cite a source node", prov)
            if src["source"]["mediaType"] == "application/pdf" and "page" not in citation["locator"]:
                raise GraphValidationError(f"{sid}: PDF evidence requires locator.page", prov)

        for dep in stmt.get("derivedFrom", ()):
            if dep not in stmts_by_id:
                raise GraphValidationError(f"{sid}: unknown derivedFrom statement '{dep}'", prov)
            derivations.add(sid, dep)

    for vid, parents in variant_parents.items():
        if len(parents) > 1:
            raise GraphValidationError(
                f"productVariant '{vid}' has multiple isVariantOf parents: {', '.join(parents)}",
                bundle.provenance.get(vid),
            )

    for sorter, name in [(parts, "composition"), (derivations, "claim derivation")]:
        try:
            tuple(sorter.static_order())
        except graphlib.CycleError as exc:
            raise GraphValidationError(f"Cycle in {name}: {' -> '.join(exc.args[1])}") from exc

    unknown_guides = [nid for nid in bundle.guide["nodes"] if nid not in nodes_by_id]
    if unknown_guides:
        raise GraphValidationError(f"Guide references unknown node IDs: {', '.join(unknown_guides)}")

    return bundle
