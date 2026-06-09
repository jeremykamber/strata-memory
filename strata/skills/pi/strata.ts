import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

// ── Helpers ─────────────────────────────────────────────────

/**
 * Detect the Strata store directory.
 * Prefers project-local `./strata_data/` when its active/ subdirectory
 * exists; otherwise falls back to the global `~/.strata/` store.
 */
function getStrataBaseDir(): string {
  const projectLocal = join(process.cwd(), "strata_data", "active");
  if (existsSync(projectLocal)) {
    return join(process.cwd(), "strata_data");
  }
  return join(process.env.HOME || homedir(), ".strata");
}

/**
 * Flatten message content blocks into a plain text string.
 * Handles both string content and structured arrays of blocks.
 */
function extractTextFromMessage(message: { content?: string | Array<{ type?: string; text?: string }> }): string {
  if (!message?.content) return "";
  if (typeof message.content === "string") return message.content;
  if (Array.isArray(message.content)) {
    return message.content
      .filter((b) => b?.type === "text" && b.text)
      .map((b) => b.text ?? "")
      .join("\n");
  }
  return "";
}

/**
 * Lightweight heuristic to decide whether text is worth persisting.
 * Uses pattern matching only — no LLM calls.
 *
 * Returns true when the text contains:
 *  - Markdown headings (sectioned/structured information)
 *  - Fenced code blocks (technical reference)
 *  - Multi-item bulleted or numbered lists (structured data)
 *  - Explicit saving keywords ("remember this", "key takeaway", etc.)
 */
function isWorthStoring(text: string): boolean {
  if (!text || text.length < 50) return false;

  // Markdown heading(s) present — likely structured content
  if (/^#{1,6}\s/m.test(text)) return true;

  // Fenced code block — potential technical reference
  if (/```[\s\S]*?```/.test(text)) return true;

  // At least two bullet items or two numbered items → structured list
  if ((text.match(/^\s*[-*+]\s/gm) ?? []).length >= 2) return true;
  if ((text.match(/^\s*\d+\.\s/gm) ?? []).length >= 2) return true;

  // Explicit "save this" language
  if (
    /\b(remember this|note this|key takeaway|key insight|important to remember|worth saving|capture this|save this)\b/i.test(
      text,
    )
  ) {
    return true;
  }

  return false;
}

/**
 * Build a sensible store path under `pi/memos/`.
 * Derives a URL-friendly slug from the first H1 when available;
 * falls back to a date-based name.
 */
function deriveStorePath(text: string): string {
  const h1 = text.match(/^#\s+(.+)$/m);
  if (h1) {
    const slug = h1[1]
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 60);
    return `pi/memos/${slug}.md`;
  }
  const today = new Date().toISOString().slice(0, 10);
  return `pi/memos/memo-${today}.md`;
}

/**
 * Persist content to Strata by shelling out to `strata add`.
 * Errors are silently caught — the extension should never crash Pi
 * just because the Strata CLI is unavailable.
 */
async function persistToStrata(
  pi: ExtensionAPI,
  path: string,
  heading: string,
  body: string,
): Promise<void> {
  const content = [
    `# ${heading}`,
    "",
    `> Auto-captured by Pi Strata extension (${new Date().toISOString()})`,
    "",
    body,
  ].join("\n");

  try {
    await pi.exec("strata", ["add", path, content], { timeout: 5_000 });
  } catch {
    // Strata CLI may not be installed or the command may fail —
    // silently ignore so the extension never blocks the agent.
  }
}

// ── Extension entry point ───────────────────────────────────

export default function (pi: ExtensionAPI) {
  const baseDir = getStrataBaseDir();

  // ── before_agent_start: Inject Strata memory awareness ─────
  //
  // Adds a structured system prompt section describing the three
  // Strata tiers and the key CLI commands.  The agent sees this
  // every turn and can act on it without any extra tooling.
  pi.on("before_agent_start", async (event, _ctx) => {
    const strataPrompt = [
      "",
      "## Strata Memory System",
      "",
      `Your Strata memory store lives at \`${baseDir}\`. It organises information across three tiers of plain markdown files:`,
      "",
      "- **1st Stratum (active/)** — working memory; read and write here freely",
      "- **2nd Stratum (cooled/)** — aged-out files; query only",
      "- **3rd Stratum (archive/ + shadow.db)** — cold storage with keyword search",
      "",
      "### Key commands",
      "",
      "| Command | Purpose |",
      "|---------|---------|",
      "| `strata add <path> <content>` | Save important information you learn |",
      "| `strata read <path>` | Read the full content of a file |",
      "| `strata search <query>` | Search across all three tiers |",
      "| `strata list [path]` | List available files |",
      "",
      "Use **`strata add`** whenever you learn something substantive about the project, architecture, user preferences, or key decisions. Use **`strata search`** at the start of a session or when you need to recall past context.",
      "",
    ].join("\n");

    return {
      systemPrompt: event.systemPrompt + strataPrompt,
    };
  });

  // ── turn_end: Auto-store substantive content ───────────────
  //
  // After each assistant turn, check the response for patterns
  // that indicate important information: markdown headings, code
  // blocks, structured lists, or explicit saving keywords.
  // When found, persist the content via `strata add`.
  pi.on("turn_end", async (event, ctx) => {
    const text = extractTextFromMessage(event.message);
    if (!isWorthStoring(text)) return;

    // Derive a heading from the first H1 or the opening line
    let heading = "Session Memory";
    const h1Match = text.match(/^#\s+(.+)$/m);
    if (h1Match) {
      heading = h1Match[1];
    } else {
      const firstLine = text.split("\n")[0]?.trim();
      if (firstLine && firstLine.length > 5) {
        heading = firstLine.slice(0, 100);
      }
    }

    const storePath = deriveStorePath(text);
    await persistToStrata(pi, storePath, heading, text);
  });
}
