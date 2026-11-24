"""Core domain constants, unit conversions, IR bundle types, and error classes."""

from dataclasses import dataclass, field
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "data"
DEFAULT_ASSETS = ROOT / ".materials"
DEFAULT_DB = DEFAULT_ASSETS / "materials.db"
MAX_ASSET_BYTES = 32 * 1024 * 1024

ID_RE = re.compile(r"^[a-z0-9]+([.-][a-z0-9]+)*$")

GAP_TIERS = ("catalog", "assembly", "atomic")

TAXONOMY_DOMAINS = (
    "substructure",
    "superstructure",
    "envelope",
    "interiors",
    "mep",
    "siteworks",
)

IDENTIFIER_NAMESPACES = frozenset({
    "uniformat2",
    "omniclass",
    "uniclass",
    "masterformat",
    "nrm1",
    "icms",
    "ifc",
    "bsdd",
    "etim",
    "gtin",
    "nfrc",
    "astm",
    "openepd",
    "epd",
    "hpd",
    "cas",
})

# Registry namespaces that uniquely identify a single real-world entity per node kind.
UNIQUE_IDENTIFIER_NAMESPACES = frozenset({
    "cas",
    "nfrc",
    "openepd",
    "epd",
    "gtin",
})

EPD_PROPERTIES = frozenset({
    "gwp",
    "gwpFossil",
    "gwpBiogenic",
    "gwpLuluc",
    "embodiedCarbon",
})

# Matches EN 15804 / ISO 21930 module tokens (A1-A3, A4, A5, B1-B7, C1-C4, D, A1-D, etc.)
# joined by '+' or ','.
_EN15804_MOD = r"(?:A[1-5](?:-A[1-5]|-D)?|B[1-7](?:-B[1-7])?|C[1-4](?:-C[1-4])?|D)"
EN15804_SCOPE_RE = re.compile(rf"^{_EN15804_MOD}(?:[+,]{_EN15804_MOD})*$")

# Deterministic linear conversion factors to canonical SI units.
SI_CONVERSIONS: dict[str, tuple[float, str]] = {
    "Btu/(h·ft²·°F)": (5.678263, "W/(m²·K)"),
    "Btu/(hr·ft²·°F)": (5.678263, "W/(m²·K)"),
    "Btu/(h*ft2*F)": (5.678263, "W/(m²·K)"),
    "Btu/(hr*ft2*F)": (5.678263, "W/(m²·K)"),
    "W/(m²·K)": (1.0, "W/(m²·K)"),
    "W/(m2*K)": (1.0, "W/(m²·K)"),
    "W/(m·°C)": (1.0, "W/(m·K)"),
    "W/(m·K)": (1.0, "W/(m·K)"),
    "W/(m*K)": (1.0, "W/(m·K)"),
    "psf": (47.880259, "Pa"),
    "psi": (6894.757, "Pa"),
    "Pa": (1.0, "Pa"),
    "kPa": (1000.0, "Pa"),
    "MPa": (1_000_000.0, "Pa"),
    "in": (0.0254, "m"),
    "ft": (0.3048, "m"),
    "mm": (0.001, "m"),
    "cm": (0.01, "m"),
    "m": (1.0, "m"),
    "lb/ft³": (16.018463, "kg/m³"),
    "lb/ft3": (16.018463, "kg/m³"),
    "kg/m³": (1.0, "kg/m³"),
    "kg/m3": (1.0, "kg/m³"),
    "cfm/ft²": (5.08, "L/(s·m²)"),
    "cfm/ft2": (5.08, "L/(s·m²)"),
    "kg": (1.0, "kg"),
    "g": (0.001, "kg"),
    "lb": (0.45359237, "kg"),
    "kg CO2e": (1.0, "kg CO2e"),
    "kg CO2e/m2": (1.0, "kg CO2e/m²"),
    "kg CO2e/m²": (1.0, "kg CO2e/m²"),
    "kg CO2e/m3": (1.0, "kg CO2e/m³"),
    "kg CO2e/m³": (1.0, "kg CO2e/m³"),
    "kg CO2e/kg": (1.0, "kg CO2e/kg"),
    "1": (1.0, "1"),
    "%": (0.01, "1"),
}


def to_si_quantity(quantity: dict | None) -> dict | None:
    """Convert a verbatim quantity dict to canonical SI, returning None if unit is unmapped."""
    if not quantity or "unit" not in quantity:
        return None
    conv = SI_CONVERSIONS.get(quantity["unit"])
    if conv is None:
        return None
    factor, si_unit = conv
    out: dict = {"unit": si_unit}
    if "value" in quantity:
        out["value"] = round(float(quantity["value"]) * factor, 6)
    else:
        out["min"] = round(float(quantity["min"]) * factor, 6)
        out["max"] = round(float(quantity["max"]) * factor, 6)
    if "basis" in quantity:
        out["basis"] = quantity["basis"]
    return out


COMPOSITION = {
    "hasPart",
    "madeOf",
    "hasComposition",
    "hasStructure",
    "includesChemical",
    "realizesDesign",
    "usesConfiguration",
}
USED_BY = {
    "hasPart",
    "madeOf",
    "hasComposition",
    "hasStructure",
    "includesChemical",
    "realizesDesign",
    "isVariantOf",
    "usesConfiguration",
    "usesProduct",
    "uses",
}
TRACE_FORWARD = {
    "hasPart",
    "realizesDesign",
    "isVariantOf",
    "usesConfiguration",
    "usesProduct",
    "manufacturedBy",
    "uses",
    "performedBy",
    "supersedes",
}
TRACE_REVERSE = {"produces", "appliesTo"}

LINK_KINDS = {
    "hasPart": ({"referenceDesign", "productVariant"}, {"referenceDesign", "productVariant"}),
    "madeOf": ({"referenceDesign", "productVariant"}, {"material"}),
    "hasStructure": ({"material"}, {"structureModel"}),
    "hasComposition": ({"material"}, {"material", "chemicalEntity"}),
    "includesChemical": ({"structureModel"}, {"chemicalEntity"}),
    "realizesDesign": ({"productModel", "productVariant"}, {"referenceDesign"}),
    "isVariantOf": ({"productVariant"}, {"productModel"}),
    "usesConfiguration": ({"referenceDesign", "productVariant"}, {"referenceDesign", "productVariant"}),
    "usesProduct": ({"referenceDesign", "productVariant"}, {"productModel"}),
    "manufacturedBy": ({"productModel"}, {"actor"}),
    "uses": ({"process"}, None),
    "produces": ({"process"}, None),
    "performedBy": ({"process"}, {"actor"}),
    "appliesTo": ({"requirement"}, {"referenceDesign", "productModel", "productVariant"}),
}


@dataclass(frozen=True)
class Provenance:
    """Source location of an authored node or statement."""

    file: str
    line: int | None = None
    row: int | None = None

    def format(self) -> str:
        parts = [self.file]
        if self.row is not None:
            parts.append(f"row {self.row}")
        elif self.line is not None:
            parts.append(f"line {self.line}")
        return ":".join(parts)


@dataclass
class CompiledBundle:
    """Canonical compiled graph + guide IR produced from data/."""

    nodes: list[dict]
    statements: list[dict]
    guide: dict
    provenance: dict[str, Provenance] = field(default_factory=dict)
    fingerprint: str = ""


class CompileError(ValueError):
    """Raised when authoring files under data/ cannot be lowered to canonical IR."""

    def __init__(self, message: str, provenance: Provenance | None = None):
        self.provenance = provenance
        full = f"{provenance.format()}: {message}" if provenance else message
        super().__init__(full)


class GraphValidationError(ValueError):
    """Raised when a compiled bundle violates schema or graph invariants."""

    def __init__(self, message: str, provenance: Provenance | None = None):
        self.provenance = provenance
        full = f"{provenance.format()}: {message}" if provenance else message
        super().__init__(full)
