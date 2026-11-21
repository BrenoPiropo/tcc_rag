\set ON_ERROR_STOP on
BEGIN;

CREATE TEMP TABLE chunks_stage (
    chunk_id char(64), document_sha256 char(64), page_number integer,
    chunk_index integer, chunk_text text, char_start integer, char_end integer,
    lexical_token_count integer, overlap_previous_tokens integer,
    section_labels jsonb, source_text_sha256 char(64), chunk_text_sha256 char(64),
    segmentation_method text, segmentation_version text, created_at timestamptz
);

\copy chunks_stage FROM '/tmp/sample_chunks.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')

INSERT INTO chunks (
    chunk_id, document_sha256, page_number, chunk_index, chunk_text, char_start,
    char_end, lexical_token_count, overlap_previous_tokens, section_labels,
    source_text_sha256, chunk_text_sha256, segmentation_method,
    segmentation_version, created_at
)
SELECT chunk_id, document_sha256, page_number, chunk_index, chunk_text, char_start,
       char_end, lexical_token_count, overlap_previous_tokens, section_labels,
       source_text_sha256, chunk_text_sha256, segmentation_method,
       segmentation_version, created_at
FROM chunks_stage
ON CONFLICT (chunk_id) DO UPDATE SET
    chunk_text = EXCLUDED.chunk_text,
    char_start = EXCLUDED.char_start,
    char_end = EXCLUDED.char_end,
    lexical_token_count = EXCLUDED.lexical_token_count,
    overlap_previous_tokens = EXCLUDED.overlap_previous_tokens,
    section_labels = EXCLUDED.section_labels,
    source_text_sha256 = EXCLUDED.source_text_sha256,
    chunk_text_sha256 = EXCLUDED.chunk_text_sha256,
    segmentation_method = EXCLUDED.segmentation_method,
    segmentation_version = EXCLUDED.segmentation_version,
    created_at = EXCLUDED.created_at;

COMMIT;
