# AgentContext — v0.1 Specification & README Draft

This document contains two parts:

1. **Part A — v0.1 Internal Spec** (what to build, what to cut, how to know it's done)
2. **Part B — Public README draft** (what the world sees on GitHub day one)

---

# Part A — v0.1 Internal Spec

## One-line goal

> A document parser that never loses provenance: every piece of output knows exactly where it came from.

This is the wedge. MarkItDown and Docling give you clean Markdown but throw away *where* the content came from. Agents need traceable context. v0.1 wins on that single axis.

## In scope (v0.1)

### 1. Input formats — only four

| Format | Why it's in |
|--------|-------------|
| PDF (digital, text-layer) | The #1 format in every RAG pipeline |
| DOCX | The #2 enterprise format |
| HTML | Web content, docs sites |
| Markdown | Pass-through + normalization, cheap to support |

**Explicitly deferred:** scanned PDFs / OCR, PPTX, XLSX, EPUB, images, audio, video, email, ZIP, code repos. Each of these is a v0.2+ plugin, not a v0.1 feature.

### 2. Unified Document Model (UDM)

A single internal representation all parsers emit. This is the most important design decision in the entire project — everything downstream depends on it.

```
Document
├── metadata          (title, author, created, source_path, sha256, parser_version)
├── blocks[]          ordered list of content blocks
│   ├── type          (heading | paragraph | table | list | code | image_ref | caption)
│   ├── text          normalized text content
│   ├── level         (for headings/lists)
│   └── provenance    ← the differentiator
│       ├── page          (int, 1-based; null for HTML/MD)
│       ├── section_path  ("2. Methods > 2.1 Setup")
│       ├── bbox          ([x0, y0, x1, y1] in PDF points; null otherwise)
│       └── char_span     (start, end offsets in source text where applicable)
└── tables[]          extracted tables as structured rows/cols, each with provenance
```

Rules:
- **No block without provenance.** If a parser can't determine a field, it must be explicitly `null`, never omitted.
- The UDM is versioned (`udm_version: "0.1"`). Breaking changes bump it.
- Tables are first-class: stored both inline (as a block) and in `tables[]` with cell-level structure.

### 3. Output formats — only two

- **Markdown** — human-readable, with optional inline citation anchors (`[^p3]` style or HTML comments carrying provenance).
- **JSON** — the full UDM, lossless.

Everything else (HTML, YAML, CSV, SQL, Parquet) is an exporter plugin later.

### 4. Python SDK — minimal surface

```python
from agentcontext import Document

doc = Document.parse("report.pdf")

doc.to_markdown()                 # clean markdown
doc.to_json()                     # full UDM
doc.blocks                        # iterate blocks with provenance
doc.tables                        # structured tables
doc.blocks[12].provenance.page    # -> 7
```

That's it. No `.ask()`, no `.embed()`, no `.search()` in v0.1. Those methods appearing later on the same `Document` object is the growth path — but shipping them half-baked now dilutes the parser.

### 5. CLI — three commands

```
agentcontext parse report.pdf                 # -> report.md next to source
agentcontext parse report.pdf --json          # -> full UDM JSON
agentcontext parse report.pdf --cite inline   # markdown with citation anchors
```

`summarize`, `search`, `chunk`, `embed`, `graph`, `serve` — all deferred. A CLI with three commands that work perfectly beats twelve that mostly work.

### 6. Plugin interface (skeleton only)

Define the `Parser` protocol now (`can_parse(path) -> bool`, `parse(path) -> Document`) and register the four built-in parsers through it. Don't build a plugin marketplace or dynamic loading — just make sure the architecture doesn't need rework when OCR arrives in v0.2.

## Out of scope (v0.1) — the "no" list

Say no, in writing, to all of these until the parser is loved:

- OCR / scanned documents
- Chunking strategies
- Embeddings
- Vector DB connectors
- Knowledge graph
- Entity extraction / AI understanding layer
- Context builder / context packages
- Memory (any kind — likely never belongs in this project)
- REST server
- Web UI
- Connectors (Drive, Notion, Slack, …)
- Enterprise features (auth, RBAC, multi-tenancy)

## Quality bar & evaluation (ship with v0.1, not after)

The pitch is *quality of context*, so quality must be measurable from day one:

1. **Golden corpus:** 25–50 real-world documents (papers, invoices, reports, contracts, docs pages) with hand-verified expected output.
2. **Metrics tracked in CI:**
   - Text extraction accuracy vs. golden output (normalized diff)
   - Heading/structure accuracy (correct levels & order)
   - Table cell accuracy (% cells correct)
   - Provenance accuracy (page numbers correct on sampled blocks)
3. **Public benchmark page:** a table comparing AgentContext vs. MarkItDown vs. Docling on the same corpus. Honest numbers, including where you lose. This is your marketing.

## Definition of done for v0.1

- [ ] Parses the golden corpus with ≥ target accuracy on all four metrics
- [ ] `pip install agentcontext` works on Linux/macOS/Windows, Python 3.10+
- [ ] Zero heavyweight required dependencies (no torch, no CUDA) — pure parsing
- [ ] Every block in every output has provenance (or explicit nulls)
- [ ] README, quickstart, and benchmark page published
- [ ] < 5 second parse time for a typical 50-page digital PDF

## v0.2 preview (so the team knows what's next, not to build now)

OCR (Tesseract adapter via the Parser protocol), PPTX + XLSX parsers, chunking module (`agentcontext-chunking`) that consumes the UDM and preserves provenance into chunks. That last part — **provenance-preserving chunks** — is the bridge from "parser" to "context platform."

---

# Part B — Public README Draft

---

# AgentContext

**Document parsing that never loses the plot — or the page number.**

AgentContext converts documents into clean Markdown and structured JSON, and unlike other converters, **every block of output carries full provenance**: source page, section path, bounding box, and character span. When your agent cites something, you can prove where it came from.

```
PDF / DOCX / HTML / Markdown  →  Markdown + JSON, fully traceable
```

## Why another parser?

Tools like MarkItDown and Docling produce good Markdown — and then throw away everything an AI agent actually needs to be trustworthy:

| | MarkItDown | Docling | **AgentContext** |
|---|---|---|---|
| Clean Markdown | ✅ | ✅ | ✅ |
| Structured JSON model | ❌ | ✅ | ✅ |
| Page-level provenance on every block | ❌ | partial | ✅ |
| Section path per block | ❌ | ❌ | ✅ |
| Bounding boxes | ❌ | partial | ✅ |
| Built for downstream RAG citations | ❌ | ❌ | ✅ |

If your LLM answer says *"revenue grew 12%"*, AgentContext lets you point at **page 7, section 3.2, exact coordinates** — automatically.

## Install

```bash
pip install agentcontext
```

No GPU. No torch. No API keys. Pure parsing.

## Quickstart

```python
from agentcontext import Document

doc = Document.parse("report.pdf")

print(doc.to_markdown())          # clean, structured markdown

for block in doc.blocks:
    print(block.text[:60], "→ page", block.provenance.page)

for table in doc.tables:
    print(table.to_rows())        # structured cells, with provenance
```

Or from the command line:

```bash
agentcontext parse report.pdf                # writes report.md
agentcontext parse report.pdf --json         # full document model
agentcontext parse report.pdf --cite inline  # markdown with citation anchors
```

## Supported formats (v0.1)

- **PDF** (digital / text-layer)
- **DOCX**
- **HTML**
- **Markdown** (normalization + provenance)

OCR for scanned documents, PPTX, and XLSX are next on the [roadmap](#roadmap).

## The Unified Document Model

Every parser emits the same structure, so your downstream code never cares what the source format was:

```json
{
  "udm_version": "0.1",
  "metadata": { "title": "...", "sha256": "...", "parser_version": "..." },
  "blocks": [
    {
      "type": "paragraph",
      "text": "Revenue grew 12% year over year...",
      "provenance": {
        "page": 7,
        "section_path": "3. Financials > 3.2 Revenue",
        "bbox": [72.0, 214.5, 540.0, 260.1],
        "char_span": null
      }
    }
  ],
  "tables": [ ... ]
}
```

## Benchmarks

We maintain a public benchmark against MarkItDown and Docling on a 50-document golden corpus (papers, reports, contracts, invoices), measuring text accuracy, structure accuracy, table cell accuracy, and provenance accuracy. See [BENCHMARKS.md](./BENCHMARKS.md).

We publish the numbers even where we lose. Trust is the product.

## Roadmap

- **v0.1 (now):** PDF/DOCX/HTML/MD → Markdown + JSON with full provenance. CLI + Python SDK.
- **v0.2:** OCR for scanned documents, PPTX/XLSX parsers, provenance-preserving chunking.
- **v0.3:** Embedding adapters, citation-aware retrieval helpers.
- **Later:** Context packages for agents — retrieval that returns not just chunks, but summaries, tables, entities, and citations in one structured payload.

The long-term vision is a full open context-engineering layer for AI agents. The short-term promise is simpler: **the most trustworthy parser you can put in a RAG pipeline.**

## Design principles

1. **Provenance is not optional.** A block without a source location is a bug.
2. **Small core, pluggable edges.** Parsers, OCR engines, and exporters implement a small protocol.
3. **No heavyweight dependencies in core.** `pip install` and go.
4. **Honest benchmarks.** Measured in CI, published publicly.

## Contributing

The `Parser` protocol makes new formats easy to add:

```python
class Parser(Protocol):
    def can_parse(self, path: Path) -> bool: ...
    def parse(self, path: Path) -> Document: ...
```

See [CONTRIBUTING.md](./CONTRIBUTING.md).

## License

MIT
