# Bilingual Evaluation Patch v11

## Diagnosis from the submitted benchmark

The old run retrieved the correct source for many failed questions, but generation
still received zero contexts. The failure was caused by ordering: context selection
ran over accepted rows that still included non-strict candidates. A higher-scoring
non-strict row could displace the valid strict row; the later generation-context
filter then removed the selected row and produced an empty bundle.

Indonesian also had intent coverage gaps. Several questions had no natural English
bridge, so the English corpus path was never replayed for calendar sharing, access
cards, parking, payroll, onboarding, phishing, lost devices, and software access.

## Safety constraints retained

- Client snapshot text is never trusted; chunk text is hydrated from Chroma by ID.
- Snapshot candidates are revalidated against the original question.
- Hard evidence contradictions still reject a candidate.
- Unanswerable questions still require refusal and no citation.
- No expected answer value or expected document name is inserted into query expansion.
