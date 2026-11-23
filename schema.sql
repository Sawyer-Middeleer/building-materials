-- Building Materials Graph — SQLite relational schema (v1)

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL CHECK (kind IN (
                    'referenceDesign', 'productModel', 'productVariant',
                    'material', 'structureModel', 'chemicalEntity',
                    'process', 'requirement', 'actor', 'source'
                )),
    label       TEXT NOT NULL,
    description TEXT,
    revision    TEXT,
    scale       TEXT,
    stage       TEXT CHECK (stage IS NULL OR stage IN (
                    'extraction', 'research', 'testing', 'design',
                    'specification', 'fabrication', 'distribution', 'installation'
                )),
    CHECK ((kind = 'process') = (stage IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS sources (
    node_id      TEXT PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
    origin       TEXT NOT NULL,
    media_type   TEXT NOT NULL,
    issuer       TEXT,
    issued_on    TEXT,
    retrieved_at TEXT,
    retrieved_on TEXT,
    sha256       TEXT
);

CREATE TABLE IF NOT EXISTS node_identifiers (
    node_id   TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    namespace TEXT NOT NULL,
    value     TEXT NOT NULL,
    PRIMARY KEY (node_id, namespace, value)
);

CREATE TABLE IF NOT EXISTS statements (
    id             TEXT PRIMARY KEY,
    subject_id     TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    predicate      TEXT,
    target_id      TEXT REFERENCES nodes(id) ON DELETE CASCADE,
    property       TEXT,
    value_text     TEXT,
    quantity_value REAL,
    quantity_min   REAL,
    quantity_max   REAL,
    quantity_unit  TEXT,
    quantity_basis TEXT,
    state          TEXT CHECK (state IS NULL OR state IN ('unknown', 'withheld')),
    scope          TEXT,
    method         TEXT,
    conditions     TEXT,
    basis          TEXT NOT NULL CHECK (basis IN (
                       'measured', 'simulated', 'manufacturer-declared',
                       'specification', 'typical-reference', 'inferred'
                   )),
    qual_role      TEXT,
    qual_position  TEXT,
    qual_sequence  INTEGER,
    CHECK (
        (predicate IS NOT NULL AND target_id IS NOT NULL AND property IS NULL)
        OR
        (property IS NOT NULL AND predicate IS NULL AND target_id IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS citations (
    statement_id TEXT NOT NULL REFERENCES statements(id) ON DELETE CASCADE,
    source_id    TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    page         INTEGER,
    section      TEXT,
    table_name   TEXT,
    row_name     TEXT,
    column_name  TEXT,
    figure       TEXT,
    anchor       TEXT,
    quote        TEXT
);

CREATE TABLE IF NOT EXISTS statement_derivations (
    statement_id TEXT NOT NULL REFERENCES statements(id) ON DELETE CASCADE,
    derived_from TEXT NOT NULL REFERENCES statements(id) ON DELETE CASCADE,
    PRIMARY KEY (statement_id, derived_from)
);

CREATE INDEX IF NOT EXISTS idx_nodes_kind ON nodes(kind);
CREATE INDEX IF NOT EXISTS idx_statements_subject ON statements(subject_id);
CREATE INDEX IF NOT EXISTS idx_statements_target ON statements(target_id);
CREATE INDEX IF NOT EXISTS idx_statements_predicate ON statements(predicate);
CREATE INDEX IF NOT EXISTS idx_citations_source ON citations(source_id);
