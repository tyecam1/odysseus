# MarkItDown pilot report (partial, synthetic corpus)

Task: `2026-07-27-markitdown-extraction-backend-pilot`. Prerequisite evidence (licence, version, identity) is in `automation/review/blocker-reconciliation/2026-11-09-odysseus-blocked-cards.md` and obsidian-PhD PR #668. **This is a bounded characterisation pilot on a generated corpus. It is not an adoption verdict and not a comparison against the repository's real extraction adapters.** Raw results: `markitdown-pilot-results.json`.

## Method
- Lab host, throwaway virtualenv under `/tmp` (Python 3.10.12), `markitdown==0.1.9` with extras `docx,pptx,xlsx`; nothing installed into any repository or service environment. Dependencies resolved to 39 installed packages (`pip list`), about **360 MB** on disk (`du`, 367,680 KB), including `onnxruntime` 1.23.2 and `magika` 1.0.3 (file-type detection) and `mammoth` 1.13.0.
- Narrowest local interface only: `MarkItDown(enable_plugins=False).convert_local(path)`. Plugins off. **Network denied during conversion** by replacing `socket.connect` with a function that raises and counts attempts; **0 connect attempts** were recorded (the install step itself used the network).
- Corpus generated in the script (no real data): ordinary DOCX, PPTX, XLSX, HTML and EPUB; malformed variants (truncated DOCX, empty DOCX, random bytes as PPTX, plain text named `.xlsx`, unclosed HTML); an unsupported binary; and a small ZIP with one highly compressible 5 MB entry. Each file's SHA-256 prefix, size and runtime are in the JSON.
- Baseline for comparison is a **naive direct text extractor** written for this pilot (python-docx, python-pptx, openpyxl, tag stripping), a stand-in and not the repository's current adapters.

## Results (ordinary files)
| Format | MarkItDown output | Naive baseline |
|---|---|---|
| DOCX (heading, bold, bullets, 2x3 table) | heading `#`, `**bold**`, `*` bullets and a Markdown table preserved | plain paragraph text only: no table, no structure |
| PPTX (title, two body lines, notes) | slide marker, `#` title, the two body lines as plain lines (no bullet markers) and a `### Notes:` section containing the speaker note | text frames only; the note was not extracted by the baseline |
| XLSX (header, 2 rows, one formula cell `D1` `=SUM(B2:B3)` with **no cached value**, checked with openpyxl `data_only`) | sheet heading and a Markdown table of the `id` and `value` columns; **the formula cell does not appear in the output**; whether a cached value would have been shown was not tested | the baseline prints each non-empty cell with `str(value)`, which for `D1` is the formula string (by construction; the baseline output was not stored) |
| HTML (h1, link, table, image alt) | heading, `[link](url)`, table, `![alt](src)` | tags stripped, no structure |
| EPUB | metadata, table of contents and chapter heading/text | no extractor |

Measured conversion times for the four non-DOCX ordinary files were 3 to 8 ms each (one run). DOCX took about 130 ms in the corpus run and 150 to 250 ms in three further fresh-instance and three same-instance repeat runs, so DOCX conversion is slower by an order of magnitude here; the cause was not investigated.

## Failure behaviour
- Truncated DOCX, empty DOCX and random bytes named `.pptx` raised `FileConversionException` (a visible failure). The unsupported binary raised `UnsupportedFormatException`.
- **Plain text named `.xlsx` was converted without error** and the output was the text itself (`this is not a workbook`). The converter's selection rule was not examined. The result object exposes only `markdown`, `text_content` and `title` (`title` was `None`), so a caller gets no indication of the detected type. That is in tension with "unsupported or unsafe formats fail visibly" unless the caller checks the type separately.
- **Large expansion was not refused:** a 4,987-byte ZIP whose single entry expands to 5 MB produced **5,000,082 characters** of output in about 140 ms with the default call. Whether a configurable limit exists was not examined and multi-entry inputs were not tested. A decompression-amplification input is therefore a plausible memory and storage risk, and any adoption should put a size and entry-count guard around the call.
- Unclosed HTML converted without error, giving heading and paragraph text plus table-like text with no valid Markdown table (`table_rows` 0).

## What this does and does not show
- Shows, on a small synthetic corpus, that MarkItDown preserves structure (headings, lists, tables, links, notes) that a naive extractor drops, that, with plugins off, no `socket.connect` call was attempted during conversion of this corpus (a narrow observation, not a proof of offline operation), and the failure modes above.
- Does **not** show: behaviour on real documents, PDFs, images, audio or any format not listed; comparison with the repository's actual adapters or with Docling/GROBID/Marker; provenance and span-contract integration; or a format-by-format adoption decision. The acceptance criteria that require those remain open.
- The dependency footprint (360 MB, ONNX runtime) is a real cost for an "optional backend" and should be weighed per format; DOCX and XLSX alone do not need `magika`'s model if the format is already known, but that was not tested.
- No canonical write path was introduced; output is extraction support material.

## Reproduction
This change includes the generating script (`markitdown-pilot-script.py`), the measured values (`markitdown-pilot-results.json`) and the supplementary console output (`markitdown-pilot-extra-checks.txt`: xlsx formula check, repeat timings, package count and disk size). The corpus is regenerated by the script. Independent (Sol) review of this report is owed.
