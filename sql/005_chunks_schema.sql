CREATE TABLE IF NOT EXISTS chunks (
    chunk_id char(64) PRIMARY KEY CHECK (chunk_id ~ '^[0-9a-f]{64}$'),
    document_sha256 char(64) NOT NULL,
    page_number integer NOT NULL,
    chunk_index integer NOT NULL CHECK (chunk_index > 0),
    chunk_text text NOT NULL CHECK (char_length(chunk_text) > 0),
    char_start integer NOT NULL CHECK (char_start >= 0),
    char_end integer NOT NULL CHECK (char_end > char_start),
    char_count integer GENERATED ALWAYS AS (char_length(chunk_text)) STORED,
    lexical_token_count integer NOT NULL CHECK (lexical_token_count > 0),
    overlap_previous_tokens integer NOT NULL CHECK (overlap_previous_tokens >= 0),
    section_labels jsonb NOT NULL DEFAULT '[]'::jsonb,
    source_text_sha256 char(64) NOT NULL CHECK (source_text_sha256 ~ '^[0-9a-f]{64}$'),
    chunk_text_sha256 char(64) NOT NULL CHECK (chunk_text_sha256 ~ '^[0-9a-f]{64}$'),
    segmentation_method text NOT NULL,
    segmentation_version text NOT NULL,
    created_at timestamptz NOT NULL,
    FOREIGN KEY (document_sha256, page_number)
        REFERENCES pages (document_sha256, page_number) ON DELETE CASCADE,
    UNIQUE (document_sha256, page_number, chunk_index)
);

CREATE INDEX IF NOT EXISTS chunks_document_page_idx
    ON chunks (document_sha256, page_number, chunk_index);

COMMENT ON TABLE chunks IS
    'Fragmentos textuais rastreáveis até documento e página, preparados para embeddings.';
