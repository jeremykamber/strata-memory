# Installation

You can install Strata with a one-liner, grab it from source, or wait for the PyPI release (whenever that lands on the calendar). Your call.

## Quick Install (Recommended)

```bash
pip install git+https://github.com/jeremykamber/strata-memory.git
```

That's it. This installs the `strata` CLI globally and makes the `strata` Python package importable. Zero pip dependencies. Nothing to clone. No extra steps. You're done. Go grab a coffee.

## Requirements

- **Python 3.9+** (stdlib only  -  no pip dependencies, we're not animals)
- **Node.js** (optional, for QMD hybrid search)
- **OS**: macOS and Linux fully supported. Windows hasn't been tested yet  -  contributions welcome, no pressure.

## From Source

If you'd rather clone the repo and poke around locally:

```bash
git clone https://github.com/jeremykamber/strata-memory.git
cd strata-memory
pip install -e .
```

Editable mode (`-e`) means you can tweak the package and see changes immediately. Handy for contributors, curious tinkerers, or anyone who enjoys living on the bleeding edge.

## From PyPI (When Published)

```bash
pip install strata-memory
```

For the cautious among us (hi, that's me):

```bash
pip install strata-memory==0.2.0
```

Version pinning is your friend in production. Trust me on this one.

## Verify Installation

```bash
strata init
strata status
```

If both commands run without screaming, you're in business. `init` creates your data directory and walks you through search backend selection. `status` shows you the system state  -  healthy, we hope.

## Optional: QMD Hybrid Search

[QMD](https://github.com/tobi/qmd) by Tobias Lutke brings you BM25 full-text search combined with vector embeddings. All local. No LLM required. It's pretty neat.

```bash
# Install QMD globally via npm
npm install -g @tobilu/qmd

# Configure Strata to use it
strata qmd-setup
strata qmd-embed
```

If you select QMD during `strata init`, Strata will try to auto-install it via `npx` (there's a 30-second timeout, so don't wander off too far). If that fails, just install manually with the commands above. It happens.

### QMD Reranker Providers (Optional)

Want even better search results? QMD supports LLM reranker providers:

- **OpenAI** (`openai://gpt-4o-mini`)
- **Anthropic** (`anthropic://claude-3-haiku`)
- **Ollama** (`ollama://llama3`)  -  local inference, no cloud required
- **Local GGUF**  -  fully local, no API calls, maximum privacy

Rerankers chew through API credits or your local compute, depending on which route you take. Set one up during `strata init`, or come back later with `strata config set qmd_reranker <provider>`.

### Fallback: FTS5 Keyword Search

No QMD? No problem. If you choose FTS5 during init  -  or QMD just isn't installed  -  Strata falls back to the built-in SQLite FTS5 shadow index for archive searches. Active and cooled strata get searched via trusty old filesystem grep. Works without Node.js, no extra setup, no fuss.

See [Search](search.md) for the full breakdown on search backends and their tradeoffs.

## Platform Notes

- **macOS / Linux**: Fully supported. Everything works  -  daemon mode, background Janitor, signal handling. You're in good hands.
- **Windows**: Not yet tested. Path handling and daemon mode might need some TLC. If you're a Windows user with opinions, we'd love to hear from you.

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

After upgrading, run `strata status` to make sure everything's still in one piece. Configuration files and existing data play nice across updates within the same major version  -  we've got your back.

## Cross-Reference

- [Quick Start (README)](../README.md#quick-start)
- [Daemon Mode (README)](../README.md#daemon-mode)
- [Configuration](configuration.md)
- [Search](search.md)  -  search backend options
