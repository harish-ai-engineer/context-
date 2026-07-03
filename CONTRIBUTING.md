# Contributing to AgentContext

Thanks for helping build the most trustworthy parser you can put in a RAG
pipeline.

## Ground rules

1. **Provenance is not optional.** Every block a parser emits must carry a
   `Provenance` — unknown fields are explicit `None`, never omitted. A block
   without provenance is a bug and will fail review.
2. **No heavyweight dependencies in core.** Optional formats gate their
   imports at parse time (see `parsers/pdf.py` for the pattern) and are wired
   up as extras in `pyproject.toml`.
3. **Tests are offline.** The suite must pass with zero network access and no
   optional dependencies installed.

## Adding a parser

Implement the small `Parser` protocol and register it:

```python
from agentcontext import Document, Parser, register_parser
from agentcontext.core.model import Block, BlockType, Provenance
from agentcontext.parsers import SectionTracker

class EpubParser(Parser):
    name = "epub"
    version = "epub-parser/0.1"
    extensions = ("epub",)

    def parse(self, path: str) -> Document:
        doc = Document(source=path)
        ...
        return doc

register_parser(EpubParser())
```

Use `SectionTracker` to give blocks hierarchical `section_path`s, and set
`page` / `char_span` wherever the format allows.

## Dev setup

```bash
pip install -e ".[all,dev]"
pytest
ruff check src tests
```

## Pull requests

- One parser / fix per PR.
- Include tests that construct fixtures in-test (no binary blobs in the repo).
- Update `README.md`'s format list if you add a format.
