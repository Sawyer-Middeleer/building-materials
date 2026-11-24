-- Building Materials Graph — SQLite lossless relational + FTS5 schema (v2)

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS build_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

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
    source_file TEXT,
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
    valid_until  TEXT,
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
    value_type     TEXT CHECK (value_type IS NULL OR value_type IN ('string', 'boolean')),
    quantity_value REAL,
    quantity_min   REAL,
    quantity_max   REAL,
    quantity_unit  TEXT,
    quantity_basis TEXT,
    si_value       REAL,
    si_min         REAL,
    si_max         REAL,
    si_unit        TEXT,
    state          TEXT CHECK (state IS NULL OR state IN ('unknown', 'withheld')),
    scope          TEXT,
    method         TEXT,
    conditions     TEXT,
    geography      TEXT,
    pcr            TEXT,
    valid_until    TEXT,
    plant_actor_id TEXT REFERENCES nodes(id) ON DELETE SET NULL,
    basis          TEXT NOT NULL CHECK (basis IN (
                       'measured', 'simulated', 'manufacturer-declared',
                       'specification', 'typical-reference', 'inferred'
                   )),
    qual_role      TEXT,
    qual_position  TEXT,
    qual_sequence  INTEGER,
    qual_qty_value REAL,
    qual_qty_min   REAL,
    qual_qty_max   REAL,
    qual_qty_unit  TEXT,
    qual_qty_basis TEXT,
    inherited_from TEXT,
    source_file    TEXT,
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

CREATE TABLE IF NOT EXISTS node_guides (
    node_id        TEXT PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
    summary        TEXT NOT NULL,
    how_it_works   TEXT,
    why_it_matters TEXT,
    tradeoffs      TEXT,
    steps_json     TEXT,
    chemistry_json TEXT,
    firm_json      TEXT
);

CREATE TABLE IF NOT EXISTS property_guides (
    property           TEXT PRIMARY KEY,
    title              TEXT NOT NULL,
    summary            TEXT NOT NULL,
    better_direction   TEXT,
    typical_range      TEXT,
    why_it_matters     TEXT,
    ucum_unit          TEXT,
    external_refs_json TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    node_id UNINDEXED,
    label,
    description,
    identifiers,
    guide_summary,
    tokenize = 'unicode61'
);

CREATE INDEX IF NOT EXISTS idx_nodes_kind ON nodes(kind);
CREATE INDEX IF NOT EXISTS idx_nodes_label ON nodes(label);
CREATE INDEX IF NOT EXISTS idx_identifiers_ns_val ON node_identifiers(namespace, value);
CREATE INDEX IF NOT EXISTS idx_statements_subject ON statements(subject_id);
CREATE INDEX IF NOT EXISTS idx_statements_target ON statements(target_id);
CREATE INDEX IF NOT EXISTS idx_statements_predicate ON statements(predicate);
CREATE INDEX IF NOT EXISTS idx_statements_prop_scope ON statements(property, scope);
CREATE INDEX IF NOT EXISTS idx_statements_basis ON statements(basis);
CREATE INDEX IF NOT EXISTS idx_statements_state ON statements(state);
CREATE INDEX IF NOT EXISTS idx_statements_geography ON statements(geography);
CREATE INDEX IF NOT EXISTS idx_statements_valid_until ON statements(valid_until);
CREATE INDEX IF NOT EXISTS idx_citations_stmt ON citations(statement_id);
CREATE INDEX IF NOT EXISTS idx_citations_source ON citations(source_id);
