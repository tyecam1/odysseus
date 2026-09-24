# Initialising-prompt application traces

Append-only empirical records for prompts registered in
`config/initialising-prompts.yaml`.

Use one file per substantive prompt application. Do not edit an existing trace
to improve its rating. If the operator later supplies a rating/correction,
append a sibling amendment that points to the original `application_id`.

File naming recommendation:

`<YYYY-MM-DD>-<prompt-id>-<short-session-id>.yaml`

No raw prompts or transcripts are duplicated here; reference the immutable
registered prompt version.
