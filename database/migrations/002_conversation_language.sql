DO $$
BEGIN
  CREATE TYPE public.conversation_language AS ENUM ('ID', 'EN');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE public.conversations
ADD COLUMN IF NOT EXISTS language public.conversation_language NOT NULL DEFAULT 'ID';

UPDATE public.conversations
SET language = 'ID'
WHERE language IS NULL;
