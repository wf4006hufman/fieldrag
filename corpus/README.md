# Corpus

The documents FieldRAG grounds its answers on. This public repo commits **open-source documentation only**.

## Committed (open source)

| File | Description | Source / license |
|---|---|---|
| `samtools(1) manual page.pdf` | samtools CLI manual (SAM/BAM/CRAM tooling) | man page from the htslib/samtools project — MIT |
| `bcftools(1).pdf` | bcftools CLI manual (VCF/BCF variant tooling) | man page from the htslib/bcftools project — MIT |
| `nextflow_document.pdf` | Nextflow workflow-manager documentation | Nextflow docs (Seqera) |
| `nfcore_document.pdf` | nf-core community pipeline documentation | nf-core project — MIT |
| `NGS_duplication_rate.md` | Explainer on why NGS duplicate rate matters (library complexity, depth, PCR vs. optical duplicates) | author-written |
| `sample_ngs_qc.md` | Small sample of NGS QC notes | author-written |

Do not rename these files — their exact names are referenced by `eval/golden.jsonl` and `eval/report.json`.

## Excluded (proprietary — not redistributed)

The **local** evaluation corpus also included two Illumina vendor documents:

- `dragen_v4_5_document.pdf` (DRAGEN v4.5)
- `illumina_connected_insights_all_sections_combined.pdf` (Connected Insights)

These are **proprietary and not redistributable**, so they are listed in `.gitignore` and are **not** part of this public repo.

Because they were part of the local eval run, `eval/golden.jsonl` and the committed `eval/report.json` still reference DRAGEN questions (`expect_source: dragen_v4_5_document.pdf`). Those results were produced locally against the full corpus. **A fresh clone reproduces only the open-source subset** — without the DRAGEN/Connected Insights PDFs, the DRAGEN golden rows will not retrieve their expected source. This is expected and documented, not a bug.

## Adding your own docs

Drop any public `.md`, `.txt`, or `.pdf` file into this directory and re-run the incremental ingest:

```bash
python -m app.ingest            # embeds only new/missing files
# or, to re-do a single file after editing it:
python -m app.ingest --only "your_new_doc.pdf"
```

Ingestion skips documents already present in the `chunks` table (matched by filename), so adding one file only embeds that file. Use `--force` to rebuild the entire corpus.
