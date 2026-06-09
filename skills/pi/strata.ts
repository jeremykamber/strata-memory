import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

// ═══════════════════════════════════════════════════════════════
//  Types
// ═══════════════════════════════════════════════════════════════

interface LLMConfig {
  enabled: boolean;
  provider: "openai" | "anthropic" | "openrouter";
  model: string;
  apiKey: string;
  temperature: number;
  maxTokens: number;
}

interface PiExtensionConfig {
  llm: LLMConfig;
}

interface ClassificationResult {
  should_store: boolean;
  reason: string;
  title?: string;
  category?: string;
}

// ═══════════════════════════════════════════════════════════════
//  Defaults
// ═══════════════════════════════════════════════════════════════

const DEFAULT_LLM_CONFIG: LLMConfig = {
  enabled: false,
  provider: "openai",
  model: "gpt-4o-mini",
  apiKey: "",
  temperature: 0.0,
  maxTokens: 500,
};

const PROVIDER_DEFAULTS: Record<string, string> = {
  openai: "gpt-4o-mini",
  anthropic: "claude-3-5-haiku-latest",
  openrouter: "openai/gpt-4o-mini",
};

// ═══════════════════════════════════════════════════════════════
//  Strata helpers (unchanged from original)
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

/**
 * Lightweight heuristic to decide whether text is worth persisting.
 * Uses pattern matching only — no LLM calls.
 *
 * This serves as the FALLBACK when the LLM classifier is:
 *   - disabled (config `enabled: false`)
 *   - missing an API key
 *   - unreachable or returns an error
 *   - returns invalid JSON
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
 * Build a sensible store path under `pi/<category>/`.
 * Uses the LLM-suggested title when available (semantic routing);
 * falls back to the first H1 heading or a date-based name.
 */
function deriveStorePath(
  text: string,
  suggestedTitle?: string,
  category?: string,
): string {
  // LLM-suggested routing — semantic title + category
  if (suggestedTitle) {
    const slug = suggestedTitle
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 60);
    const base = category || "memos";
    return `pi/${base}/${slug}.md`;
  }

  // Heuristic fallback: first H1
  const h1 = text.match(/^#\s+(.+)$/m);
  if (h1) {
    const slug = h1[1]
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 60);
    return `pi/memos/${slug}.md`;
  }

  // Date fallback
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

// ═══════════════════════════════════════════════════════════════
//  LLM Configuration
// ═══════════════════════════════════════════════════════════════

function piConfigPath(baseDir: string): string {
  return join(baseDir, "pi-config.json");
}

/**
 * Load the Pi extension configuration from `<strataBaseDir>/pi-config.json`.
 * Missing or malformed files silently return defaults.
 */
function loadPiConfig(): PiExtensionConfig {
  try {
    const baseDir = getStrataBaseDir();
    const configFile = piConfigPath(baseDir);
    if (!existsSync(configFile)) return { llm: { ...DEFAULT_LLM_CONFIG } };

    const raw = readFileSync(configFile, "utf-8");
    const parsed = JSON.parse(raw);
    const llm: Record<string, unknown> = parsed?.llm ?? {};

    const provider = (llm.provider as string) || DEFAULT_LLM_CONFIG.provider;

    return {
      llm: {
        enabled:
          typeof llm.enabled === "boolean"
            ? llm.enabled
            : DEFAULT_LLM_CONFIG.enabled,
        provider: provider as LLMConfig["provider"],
        model: (llm.model as string) || PROVIDER_DEFAULTS[provider] || DEFAULT_LLM_CONFIG.model,
        apiKey: typeof llm.apiKey === "string" ? llm.apiKey : DEFAULT_LLM_CONFIG.apiKey,
        temperature:
          typeof llm.temperature === "number"
            ? llm.temperature
            : DEFAULT_LLM_CONFIG.temperature,
        maxTokens:
          typeof llm.maxTokens === "number"
            ? llm.maxTokens
            : DEFAULT_LLM_CONFIG.maxTokens,
      },
    };
  } catch {
    return { llm: { ...DEFAULT_LLM_CONFIG } };
  }
}

/**
 * Resolve the effective API key for the current provider.
 * Resolution order:
 *   1. Direct string in config (apiKey field)
 *   2. Env var reference in config (e.g. "${MY_API_KEY}")
 *   3. Well-known env vars per provider
 * Returns empty string when no key is found.
 */
function resolveApiKey(config: LLMConfig): string {
  // Direct key
  if (config.apiKey && !config.apiKey.startsWith("${")) {
    return config.apiKey;
  }

  // Env-var reference: "${STRATA_OPENAI_API_KEY}"
  if (config.apiKey.startsWith("${") && config.apiKey.endsWith("}")) {
    const varName = config.apiKey.slice(2, -1);
    return process.env[varName] || "";
  }

  // Well-known env-var names per provider
  switch (config.provider) {
    case "openai":
      return process.env.STRATA_OPENAI_API_KEY || process.env.OPENAI_API_KEY || "";
    case "anthropic":
      return process.env.STRATA_ANTHROPIC_API_KEY || process.env.ANTHROPIC_API_KEY || "";
    case "openrouter":
      return process.env.STRATA_OPENROUTER_API_KEY || process.env.OPENROUTER_API_KEY || "";
  }
  return "";
}

// ═══════════════════════════════════════════════════════════════
//  LLM classification
// ═══════════════════════════════════════════════════════════════

/**
 * Build the structured prompt for memory classification.
 * The LLM is instructed to return a JSON object with `should_store`,
 * `reason`, `title`, and `category` fields.
 */
function buildClassificationPrompt(text: string): { system: string; user: string } {
  const system = [
    `You are a memory classifier for an AI agent's tiered memory system.`,
    `Your job is to analyze text from an AI assistant response and decide`,
    `if it contains information worth persisting as a long-term memory.`,
    ``,
    `A memory IS worth storing when it contains:`,
    `- Key decisions or architectural choices`,
    `- Technical details (code patterns, API endpoints, configuration)`,
    `- User preferences, requirements, or constraints`,
    `- Project-specific knowledge or domain concepts`,
    `- Action items, tasks, deadlines, or plans`,
    `- Explanations, rationale, or reasoning useful to recall later`,
    `- Important facts about people, companies, tools, or systems`,
    ``,
    `A memory is NOT worth storing when it contains:`,
    `- Simple greetings or sign-offs`,
    `- Generic acknowledgments without substance`,
    `- Trivial or obvious statements`,
    `- Confirmation of completed tasks without new information`,
    `- Repetitive or redundant content already captured`,
    ``,
    `Respond with ONLY a raw JSON object (no markdown, no code fences):`,
    `{`,
    `  "should_store": true or false,`,
    `  "reason": "Brief one-sentence explanation of your decision",`,
    `  "title": "Concise, descriptive title for the memory (omit if should_store is false)",`,
    `  "category": "One of: projects, entities, gtd, reference, general (omit if should_store is false)"`,
    `}`,
    ``,
    `Category meanings:`,
    `- projects: Technical specs, architecture, code patterns, project plans`,
    `- entities: People, companies, tools, services`,
    `- gtd: Tasks, action items, deadlines, to-dos`,
    `- reference: General reference information, concepts, explanations`,
    `- general: Anything that doesn't fit the above`,
  ].join("\n");

  const user = [
    "Analyze this text from an AI assistant response and determine if it should be stored as a memory:",
    "",
    text.slice(0, 4000),
  ].join("\n");

  return { system, user };
}

async function callOpenAI(
  text: string,
  config: LLMConfig,
): Promise<string | null> {
  const apiKey = resolveApiKey(config);
  if (!apiKey) return null;

  const { system, user } = buildClassificationPrompt(text);

  try {
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: config.model,
        messages: [
          { role: "system", content: system },
          { role: "user", content: user },
        ],
        response_format: { type: "json_object" },
        temperature: config.temperature,
        max_tokens: config.maxTokens,
      }),
    });

    if (!response.ok) return null;

    const data = (await response.json()) as {
      choices?: Array<{ message?: { content?: string } }>;
    };
    return data?.choices?.[0]?.message?.content || null;
  } catch {
    return null;
  }
}

async function callAnthropic(
  text: string,
  config: LLMConfig,
): Promise<string | null> {
  const apiKey = resolveApiKey(config);
  if (!apiKey) return null;

  const { system, user } = buildClassificationPrompt(text);

  try {
    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: config.model,
        max_tokens: config.maxTokens,
        system,
        messages: [{ role: "user", content: user }],
        temperature: config.temperature,
      }),
    });

    if (!response.ok) return null;

    const data = (await response.json()) as {
      content?: Array<{ text?: string }>;
    };
    return data?.content?.[0]?.text || null;
  } catch {
    return null;
  }
}

async function callOpenRouter(
  text: string,
  config: LLMConfig,
): Promise<string | null> {
  const apiKey = resolveApiKey(config);
  if (!apiKey) return null;

  const { system, user } = buildClassificationPrompt(text);

  try {
    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
        "HTTP-Referer": "https://github.com/jeremykamber/strata-memory",
        "X-Title": "Strata Memory",
      },
      body: JSON.stringify({
        model: config.model,
        messages: [
          { role: "system", content: system },
          { role: "user", content: user },
        ],
        temperature: config.temperature,
        max_tokens: config.maxTokens,
      }),
    });

    if (!response.ok) return null;

    const data = (await response.json()) as {
      choices?: Array<{ message?: { content?: string } }>;
    };
    return data?.choices?.[0]?.message?.content || null;
  } catch {
    return null;
  }
}

/**
 * Classify assistant response text using the configured LLM provider.
 * Returns structured result on success, null on failure (caller falls
 * back to the heuristic).
 */
async function classifyWithLLM(
  text: string,
  config: LLMConfig,
): Promise<ClassificationResult | null> {
  let rawContent: string | null = null;

  switch (config.provider) {
    case "openai":
      rawContent = await callOpenAI(text, config);
      break;
    case "anthropic":
      rawContent = await callAnthropic(text, config);
      break;
    case "openrouter":
      rawContent = await callOpenRouter(text, config);
      break;
    default:
      return null;
  }

  if (!rawContent) return null;

  try {
    // Strip any markdown code fences the LLM might wrap the JSON in
    const cleaned = rawContent.replace(/```(?:json)?\s*/g, "").trim();
    const parsed = JSON.parse(cleaned) as Record<string, unknown>;

    return {
      should_store: parsed.should_store === true,
      reason: typeof parsed.reason === "string" ? parsed.reason : "",
      title: typeof parsed.title === "string" ? parsed.title : undefined,
      category:
        typeof parsed.category === "string" ? parsed.category : undefined,
    };
  } catch {
    return null;
  }
}

// ═══════════════════════════════════════════════════════════════
//  Extension entry point
// ═══════════════════════════════════════════════════════════════

export default function (pi: ExtensionAPI) {
  const baseDir = getStrataBaseDir();
  const config = loadPiConfig();

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
  // After each assistant turn, decide whether the response contains
  // information worth persisting as a memory.
  //
  // Decision pipeline (in order):
  //   1. LLM classifier (when `enabled: true` in pi-config.json) —
  //      calls the configured provider with a structured prompt that
  //      returns JSON: { should_store, reason, title, category }
  //   2. Heuristic fallback (regex-based) — used when the LLM is
  //      disabled, unreachable, or returns invalid results.
  //
  // When storing, the path is derived from the LLM-suggested title
  // and category (semantic routing) or falls back to the first H1
  // heading / date-based name.
  pi.on("turn_end", async (event, _ctx) => {
    const text = extractTextFromMessage(event.message);
    if (!text || text.length < 50) return;

    // ── Decision pipeline ──────────────────────────────────
    let shouldStore = false;
    let suggestedTitle: string | undefined;
    let suggestedCategory: string | undefined;

    if (config.llm.enabled) {
      // Phase 1: LLM-powered classification
      const result = await classifyWithLLM(text, config.llm);
      if (result) {
        shouldStore = result.should_store;
        suggestedTitle = result.title;
        suggestedCategory = result.category;
      } else {
        // LLM call failed — fall back to heuristic
        shouldStore = isWorthStoring(text);
      }
    } else {
      // Phase 2: Heuristic fallback (default behaviour)
      shouldStore = isWorthStoring(text);
    }

    if (!shouldStore) return;

    // ── Derive heading ─────────────────────────────────────
    let heading = "Session Memory";
    if (suggestedTitle) {
      heading = suggestedTitle;
    } else {
      const h1Match = text.match(/^#\s+(.+)$/m);
      if (h1Match) {
        heading = h1Match[1];
      } else {
        const firstLine = text.split("\n")[0]?.trim();
        if (firstLine && firstLine.length > 5) {
          heading = firstLine.slice(0, 100);
        }
      }
    }

    const storePath = deriveStorePath(text, suggestedTitle, suggestedCategory);
    await persistToStrata(pi, storePath, heading, text);
  });
}
