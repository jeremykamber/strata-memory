# Installation

Install Strata with a one-liner, from source, or from PyPI (when published).

## Quick Install (Recommended)

```bash
pip install git+https://github.com/jeremykamber/strata-memory.git
```

This installs the `strata` CLI globally and makes the `strata` Python package importable. Zero pip dependencies. Nothing to clone, no extra steps.

## Requirements

- **Python 3.9+** (stdlib only -- no pip dependencies)
- **Node.js** (optional, for QMD hybrid search)
- **OS**: macOS and Linux fully supported. Windows not yet tested.

## From Source

If you prefer to clone the repository and develop locally:

```bash
git clone https://github.com/jeremykamber/strata-memory.git
cd strata-memory
pip install -e .
```

Editable mode (`-e`) lets you modify the package and see changes immediately. Useful for contributors or custom builds.

## From PyPI (When Published)

```bash
pip install strata-memory
```

Version pinning is recommended for production use:

```bash
pip install strata-memory==0.2.0
```

## Verify Installation

```bash
strata init
strata status
```

If both commands succeed, Strata is ready. The `init` command creates your data directory and walks you through search backend selection. `status` shows the system state.

## Optional: QMD Hybrid Search

[QMD](https://github.com/tobi/qmd) by Tobias Lutke provides BM25 full-text search combined with vector embeddings -- all local, no LLM required.

```bash
# Install QMD globally via npm
npm install -g @tobilu/qmd

# Configure Strata to use it
strata qmd-setup
strata qmd-embed
```

If you select QMD during `strata init`, Strata attempts to auto-install it via `npx` (30-second timeout). If that fails, install manually with the command above.

### QMD Reranker Providers (Optional)

For even better search results, QMD supports LLM reranker providers:

- **OpenAI** (`openai://gpt-4o-mini`)
- **Anthropic** (`anthropic://claude-3-haiku`)
- **Ollama** (`ollama://llama3`) -- local inference
- **Local GGUF** -- fully local, no API calls

Rerankers use API credits or local compute. Set during `strata init` or later with `strata config set qmd_reranker <provider>`.

### Fallback: FTS5 Keyword Search

If QMD is not installed or you choose FTS5 during init, Strata uses the built-in SQLite FTS5 shadow index for archive searches. Active and cooled strata are searched via filesystem grep. Works without Node.js, no extra setup.

See [Search](search.md) for details on search backends and their tradeoffs.

## Platform Notes

- **macOS / Linux**: Fully supported. All features work including daemon mode, background Janitor, and signal handling.
- **Windows**: Not yet tested. Path handling and daemon mode may need adjustments. Contributions welcome.

## Upgrading

```bash
# From git (recommended)
pip install --upgrade git+https://github.com/jeremykamber/strata-memory.git

# From source
cd strata-memory
git pull
pip install -e .

# From PyPI
pip install --upgrade strata-memory
```

After upgrading, run `strata status` to verify everything works. Configuration files and existing data are forward-compatible within the same major version.

## Cross-Reference

- [Quick Start (README)](../README.md#quick-start)
- [Daemon Mode (README)](../README.md#daemon-mode)
- [Configuration](configuration.md)
- [Search](search.md) -- search backend options
