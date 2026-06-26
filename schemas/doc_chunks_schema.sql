-- SeismoSearch document chunk schema
-- Purpose:
--   Store seismology knowledge document chunks for retrieval, citation,
--   concept explanation, misinformation correction, and safety-bounded risk communication.
--
-- Design principles:
--   1. Every chunk must be traceable to a document source.
--   2. Chunk metadata must support retrieval evaluation.
--   3. Source, section, and content hash must be retained for auditability.
--   4. Embedding metadata is recorded, but the vector itself can live in a vector database.

CREATE TABLE IF NOT EXISTS doc_chunks (
    -- Primary chunk identity.
    chunk_id             VARCHAR PRIMARY KEY,

    -- Document-level identity shared by chunks from the same source document.
    doc_id               VARCHAR NOT NULL,

    -- Source organization or website, for example: USGS, IRIS, FEMA.
    source_name          VARCHAR NOT NULL,

    -- URL of the original document or webpage.
    source_url           VARCHAR,

    -- License or usage note if available.
    license              VARCHAR,

    -- Document title.
    title                VARCHAR NOT NULL,

    -- Author or publishing organization.
    author_or_org        VARCHAR,

    -- Publication date if available.
    publication_date     DATE,

    -- Time when this document was fetched.
    fetched_time_utc     TIMESTAMP,

    -- Document type, for example: faq, glossary, guide, report, article.
    doc_type             VARCHAR,

    -- Local section title containing this chunk.
    section_title        VARCHAR,

    -- Hierarchical section path, for example: Earthquake Basics > Magnitude.
    section_path         VARCHAR,

    -- Page number for PDF sources if available.
    page_number          INTEGER,

    -- Paragraph index inside the source section if available.
    paragraph_index      INTEGER,

    -- Chunk text used for retrieval and generation grounding.
    content              TEXT NOT NULL,

    -- Hash of content, used for deduplication and version tracking.
    content_hash         VARCHAR,

    -- Language code, for example: en, zh.
    language             VARCHAR DEFAULT 'en',

    -- Character count of content.
    char_count           INTEGER,

    -- Approximate token count of content.
    token_count          INTEGER,

    -- Keyword list extracted or manually assigned.
    keywords             VARCHAR[],

    -- Entity or concept list, for example: magnitude, intensity, tsunami.
    entities             VARCHAR[],

    -- Topic labels, for example: concept, catalog_field, safety, misinformation.
    topic_tags           VARCHAR[],

    -- Difficulty level, for example: basic, intermediate, advanced.
    difficulty_level     VARCHAR,

    -- Embedding model name used for this chunk.
    embedding_model      VARCHAR,

    -- Embedding vector dimension.
    embedding_dim        INTEGER,

    -- Vector database name, for example: faiss, chroma, milvus.
    vector_store         VARCHAR,

    -- External vector ID in the vector database.
    vector_id            VARCHAR,

    -- Whether this chunk is active for retrieval.
    is_active            BOOLEAN DEFAULT TRUE,

    -- Optional chunk quality score from manual or automatic checks.
    chunk_quality_score  DOUBLE,

    -- Free-text notes for chunking or source quality issues.
    notes                VARCHAR
);