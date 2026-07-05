# Sample doc (REPLACE with real public docs)

This placeholder exists so `ingest.py` runs on first try. Delete it once you add
real public documents (see GUIDE.md "Corpus" section for suggested public sources).

## Germline NGS QC — quick reference

Common quality-control metrics reviewed after a germline whole-genome or exome run:

- **Mean coverage / depth**: average number of reads covering each target base.
  Low mean coverage reduces variant-calling sensitivity.
- **Coverage uniformity**: fraction of targets above a threshold (e.g. 20x).
- **Duplicate rate**: proportion of PCR/optical duplicate reads; high values waste depth.
- **Contamination estimate**: a nonzero cross-sample contamination fraction (e.g. from
  VerifyBamID-style methods) suggests sample mix-up or index hopping. A contamination
  estimate above ~2-3% is a common flag to investigate before trusting variant calls.
- **Ti/Tv ratio**: transition/transversion ratio; deviation from the expected ~2.0-2.1
  for WGS can indicate systematic error or artifacts.
- **Insert size distribution**: unexpected shifts can indicate library-prep problems.
- **Callable regions**: fraction of the genome/exome confidently callable after filters.

## Reading a QC failure

If contamination is elevated AND Ti/Tv is off, suspect a sample-handling or
demultiplexing problem before pipeline parameters. If coverage is low but uniform,
suspect input DNA quantity/quality rather than capture design.
