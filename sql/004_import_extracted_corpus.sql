\set ON_ERROR_STOP on
BEGIN;

CREATE TEMP TABLE documents_stage (
    sha256 char(64), edition smallint, site_user_id bigint, participant_name text,
    source_path text, byte_size bigint, page_count integer, manifest_status text,
    audited_at timestamptz
);

CREATE TEMP TABLE pages_stage (
    document_sha256 char(64), page_number integer, raw_text text, normalized_text text,
    alpha_count integer, alpha_ratio numeric(7,6), replacement_char_count integer,
    extraction_status text, extraction_method text, extractor_version text,
    text_sha256 char(64), needs_ocr boolean, extraction_error text, extracted_at timestamptz
);

\copy documents_stage FROM '/tmp/corpus_documents.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy pages_stage FROM '/tmp/corpus_pages.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')

INSERT INTO documents (
    sha256, edition, site_user_id, participant_name, source_path, byte_size,
    page_count, manifest_status, audited_at
)
SELECT sha256, edition, site_user_id, participant_name, source_path, byte_size,
       page_count, manifest_status, audited_at
FROM documents_stage
ON CONFLICT (sha256) DO UPDATE SET
    edition = EXCLUDED.edition,
    site_user_id = EXCLUDED.site_user_id,
    participant_name = EXCLUDED.participant_name,
    source_path = EXCLUDED.source_path,
    byte_size = EXCLUDED.byte_size,
    page_count = EXCLUDED.page_count,
    manifest_status = EXCLUDED.manifest_status,
    audited_at = EXCLUDED.audited_at;

INSERT INTO pages (
    document_sha256, page_number, raw_text, normalized_text, alpha_count,
    alpha_ratio, replacement_char_count, extraction_status, extraction_method,
    extractor_version, text_sha256, needs_ocr, extraction_error, extracted_at
)
SELECT document_sha256, page_number, raw_text, normalized_text, alpha_count,
       alpha_ratio, replacement_char_count, extraction_status, extraction_method,
       extractor_version, text_sha256, needs_ocr, extraction_error, extracted_at
FROM pages_stage
ON CONFLICT (document_sha256, page_number) DO UPDATE SET
    raw_text = EXCLUDED.raw_text,
    normalized_text = EXCLUDED.normalized_text,
    alpha_count = EXCLUDED.alpha_count,
    alpha_ratio = EXCLUDED.alpha_ratio,
    replacement_char_count = EXCLUDED.replacement_char_count,
    extraction_status = EXCLUDED.extraction_status,
    extraction_method = EXCLUDED.extraction_method,
    extractor_version = EXCLUDED.extractor_version,
    text_sha256 = EXCLUDED.text_sha256,
    needs_ocr = EXCLUDED.needs_ocr,
    extraction_error = EXCLUDED.extraction_error,
    extracted_at = EXCLUDED.extracted_at;

COMMIT;
