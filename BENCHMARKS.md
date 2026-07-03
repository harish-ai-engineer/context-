# Benchmarks

**Status: under construction — no numbers published yet.**

The v0.1 quality bar (see `agentcontext-v0.1-spec-and-readme.md`) requires a
public, honest benchmark before we claim anything. This page will hold it.

## Planned methodology

1. **Golden corpus:** 25–50 real-world documents — papers, invoices, reports,
   contracts, documentation pages — with hand-verified expected output.
2. **Metrics, tracked in CI:**
   - **Text extraction accuracy** vs. golden output (normalized diff)
   - **Heading/structure accuracy** (correct levels and order)
   - **Table cell accuracy** (% of cells correct)
   - **Provenance accuracy** (page numbers correct on sampled blocks)
3. **Baselines:** MarkItDown and Docling, run on the same corpus with default
   settings.

## Commitments

- Numbers are published **even where we lose**. Trust is the product.
- The corpus, harness, and scoring scripts ship in this repo so anyone can
  reproduce the table.
- Every release updates this page from CI, not by hand.
