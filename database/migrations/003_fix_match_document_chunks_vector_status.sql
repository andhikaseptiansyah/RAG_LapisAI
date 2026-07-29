-- Fix stale RAG retrieval function.
-- Older versions checked d.vector_status = 'active', but the current enum uses
-- pending | processing | completed | failed. Indexed documents must use completed.

CREATE OR REPLACE FUNCTION public.match_document_chunks(
  query_embedding vector,
  match_count integer DEFAULT 5,
  match_threshold double precision DEFAULT 0,
  filter_document_ids uuid[] DEFAULT NULL
)
RETURNS TABLE (
  chunk_id uuid,
  document_id uuid,
  document_name text,
  content text,
  page_number integer,
  chunk_index integer,
  similarity double precision,
  metadata jsonb
)
LANGUAGE sql
STABLE
AS $$
  SELECT
    dc.id AS chunk_id,
    d.id AS document_id,
    d.filename::text AS document_name,
    dc.content::text AS content,
    dc.page_number,
    dc.chunk_index,
    1 - (dc.embedding <=> query_embedding) AS similarity,
    dc.metadata
  FROM public.document_chunks dc
  JOIN public.documents d
    ON d.id = dc.document_id
  WHERE
    dc.embedding IS NOT NULL
    AND d.status = 'indexed'::public.document_status
    AND d.vector_status = 'completed'::public.vector_status
    AND (
      filter_document_ids IS NULL
      OR d.id = ANY(filter_document_ids)
    )
    AND (1 - (dc.embedding <=> query_embedding)) >= match_threshold
  ORDER BY dc.embedding <=> query_embedding
  LIMIT GREATEST(match_count, 1);
$$;
