CREATE TABLE IF NOT EXISTS documents (
    sha256 char(64) PRIMARY KEY CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    edition smallint NOT NULL CHECK (edition BETWEEN 1 AND 5),
    site_user_id bigint NOT NULL,
    participant_name text NOT NULL,
    source_path text NOT NULL UNIQUE,
    byte_size bigint NOT NULL CHECK (byte_size > 0),
    page_count integer NOT NULL CHECK (page_count > 0),
    manifest_status text NOT NULL,
    audited_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (edition, site_user_id)
);

CREATE TABLE IF NOT EXISTS pages (
    document_sha256 char(64) NOT NULL REFERENCES documents(sha256) ON DELETE CASCADE,
    page_number integer NOT NULL CHECK (page_number > 0),
    raw_text text NOT NULL DEFAULT '',
    normalized_text text NOT NULL DEFAULT '',
    char_count integer GENERATED ALWAYS AS (char_length(normalized_text)) STORED,
    alpha_count integer NOT NULL CHECK (alpha_count >= 0),
    alpha_ratio numeric(7,6) NOT NULL CHECK (alpha_ratio BETWEEN 0 AND 1),
    replacement_char_count integer NOT NULL CHECK (replacement_char_count >= 0),
    extraction_status text NOT NULL CHECK (extraction_status IN ('extracted', 'empty', 'error')),
    extraction_method text NOT NULL,
    extractor_version text NOT NULL,
    text_sha256 char(64),
    needs_ocr boolean NOT NULL,
    extraction_error text,
    extracted_at timestamptz NOT NULL,
    PRIMARY KEY (document_sha256, page_number),
    CHECK (extraction_status = 'error' OR text_sha256 IS NOT NULL),
    CHECK (extraction_status <> 'error' OR extraction_error IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS documents_edition_idx ON documents (edition);
CREATE INDEX IF NOT EXISTS pages_needs_ocr_idx ON pages (needs_ocr) WHERE needs_ocr;

COMMENT ON TABLE documents IS 'Proveniência e integridade dos PDFs auditados dos Anais da SIC/UESC.';
COMMENT ON TABLE pages IS 'Texto extraído por página, métricas objetivas de qualidade e indicação de OCR.';

