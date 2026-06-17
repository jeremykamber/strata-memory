# Strata Documentation

Welcome to the Strata documentation. Strata is a CLI-first, stdlib-first tiered memory system for AI agents. It organises memories across three strata (active, cooled, and archive) so that recent information is instantly accessible while older data settles into deeper, cheaper storage.

For a high-level project overview, installation instructions, and quick-start guide, see the [README](../README.md).

## Documentation Sections

| Section | Description |
|---|---|
| [Installation](installation.md) | Installing Strata from source, via pip, and setting up QMD. |
| [Configuration](configuration.md) | Full reference for `StrataConfig` -- decay thresholds, eviction rules, daemon settings. |
| [CLI Reference](cli-reference.md) | All `strata` commands, arguments, options, and exit codes. |
| [Architecture](architecture.md) | How the three-tier system works -- Janitor lifecycle, strata transitions, shadow index. |
| [Search](search.md) | Search backends -- filesystem grep, SQLite FTS5 (shadow index), QMD with BM25 + vector fusion. |
| [Cost Tracking](tracking.md) | Methodology for tracking storage, search, and lifecycle costs across tiers. |
| [Pi Integration](pi-integration.md) | Using Strata with Pi agents -- extension install, auto-injection, workflow patterns. |

## Quick Links

- **Project repo**: [github.com/jeremykamber/strata-memory](https://github.com/jeremykamber/strata-memory)
- **Blog post**: [Strata -- A Tiered Memory System for Effective AI Agents](https://jeremykamber.com/blog/strata-a-tiered-memory-system-for-effective-ai-agents)
- **Issue tracker**: [GitHub Issues](https://github.com/jeremykamber/strata-memory/issues)
- **PyPI**: `pip install strata-memory` (coming soon)

## Contributing

Contributions are welcome. The project follows these conventions:

- **No new pip dependencies.** Strata is stdlib-first. Optional extras are scoped to `[openai]`, `[anthropic]`, `[all]`.
- **Tests are pytest only.** No Jest, no TypeScript test infra.
- **Hand-written markdown.** No doc generation pipeline.
- **Conventional commits.** Format: `type(scope): description`. Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.
- **Files are the truth.** Strata stores data as plain markdown files. No databases for active storage.
- **The Janitor is algorithmic.** No LLM calls in lifecycle management.

See the [AGENTS.md](../AGENTS.md) for detailed contribution rules.

## Licence

Strata is released under the MIT licence. See the [repository](https://github.com/jeremykamber/strata-memory) on GitHub for details.
