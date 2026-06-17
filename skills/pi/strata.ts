import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { homedir } from "node:os";
import { join } from "node:path";

// ═══════════════════════════════════════════════════════════════
//  Strata helpers
// ═══════════════════════════════════════════════════════════════

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
function extractTextFromMessage(
  message: { content?: string | Array<{ type?: string; text?: string }> },
): string {
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

// ═══════════════════════════════════════════════════════════════
//  Conversation formatting
// ═══════════════════════════════════════════════════════════════

/**
 * Generate a deterministic short hash from an array of messages.
 * Used for the session filename to ensure uniqueness without UUID deps.
 */
function shortHash(messages: Array<{ content?: unknown }>): string {
  const raw = messages
    .map((m) => {
      if (typeof m.content === "string") return m.content;
      if (Array.isArray(m.content)) {
        return m.content
          .filter((b): b is { type?: string; text?: string } => typeof b?.text === "string")
          .map((b) => b.text ?? "")
          .join(" ");
      }
      return "";
    })
    .join("\n---\n");
  return createHash("md5").update(raw, "utf-8").digest("hex").slice(0, 8);
}

/**
 * Format a conversation transcript as a markdown document.
 */
function formatTranscript(
  messages: Array<{ role?: string; content?: string | Array<{ type?: string; text?: string }> }>,
): string {
  const lines: string[] = [
    `# Session Transcript — ${new Date().toISOString()}`,
    "",
    "*Conversation captured by Pi Strata extension*",
    "",
  ];

  for (const msg of messages) {
    const role = msg.role || "unknown";
    const text = extractTextFromMessage(msg);
    if (!text) continue;

    lines.push("---", "");
    if (role === "user") {
      lines.push(`**${role}:**`, "", text, "");
    } else if (role === "assistant") {
      lines.push(`**${role}:**`, "", text, "");
    } else {
      lines.push(`**${role} (${msg.role})**:`, "", text, "");
    }
  }

  return lines.join("\n");
}

// ═══════════════════════════════════════════════════════════════
//  Extension entry point
// ═══════════════════════════════════════════════════════════════

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

  // ── agent_end: Capture full conversation transcript ────────
  //
  // After each prompt completes, save the full conversation
  // (user and assistant messages) as a plain markdown file to
  // `pi/conversations/YYYY-MM-DD/YYYYMMDDThhmmss-{hash}.md`.
  //
  // Unlike the old turn_end handler, this captures everything
  // with no heuristic filtering — the raw transcript is always
  // preserved. Background distillation (run by the Strata daemon)
  // extracts standalone fact files from these transcripts.
  pi.on("agent_end", async (event, _ctx) => {
    const messages = event.messages as Array<{
      role?: string;
      content?: string | Array<{ type?: string; text?: string }>;
    }> | undefined;

    if (!messages || messages.length === 0) return;

    // Build session identity
    const now = new Date();
    const datePart = now.toISOString().slice(0, 10); // YYYY-MM-DD
    const timePart = now.toISOString()
      .slice(0, 19)
      .replace(/[-:]/g, ""); // YYYYMMDDThhmmss
    const hash = shortHash(messages);
    const filename = `${timePart}-${hash}.md`;

    const dir = join(baseDir, "active", "pi", "conversations", datePart);
    const filePath = join(dir, filename);

    try {
      mkdirSync(dir, { recursive: true });
      const transcript = formatTranscript(messages);
      writeFileSync(filePath, transcript, "utf-8");
    } catch {
      // Filesystem write errors must never block the agent.
      // Silently ignore so the extension stays non-blocking.
    }
  });
}
