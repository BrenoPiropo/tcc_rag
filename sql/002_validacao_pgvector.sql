-- Validacao reproduzivel da infraestrutura vetorial.
-- Esta tabela permanece apos o teste para permitir verificar a persistencia do volume.

BEGIN;

DROP TABLE IF EXISTS validation_vectors;

CREATE TABLE validation_vectors (
    id smallint PRIMARY KEY,
    label text NOT NULL UNIQUE,
    embedding vector(3) NOT NULL
);

INSERT INTO validation_vectors (id, label, embedding) VALUES
    (1, 'A', '[1,0,0]'),
    (2, 'B', '[0,1,0]'),
    (3, 'C', '[1,1,0]');

COMMIT;

SELECT current_setting('server_version') AS postgresql_version;

SELECT extversion AS pgvector_version
FROM pg_extension
WHERE extname = 'vector';

SELECT count(*) AS stored_vectors,
       min(vector_dims(embedding)) AS minimum_dimensions,
       max(vector_dims(embedding)) AS maximum_dimensions
FROM validation_vectors;

SELECT label,
       round((embedding <=> '[1,0,0]'::vector)::numeric, 6) AS cosine_distance,
       round((embedding <-> '[1,0,0]'::vector)::numeric, 6) AS euclidean_distance
FROM validation_vectors
ORDER BY embedding <=> '[1,0,0]'::vector, id;

