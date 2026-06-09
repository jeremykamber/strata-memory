"""Cost tracking and estimation for Strata memory system."""

import re

from strata.config import StrataConfig


class CostTracker:
    """Estimate token and cost savings from Janitor automation."""

    def __init__(self, config: StrataConfig):
        """Initialize the tracker with a reference to the daemon log.

        Args:
            config: Active Strata configuration (used to locate the
                daemon log at ``strata.log`` in the base directory).
        """
        self.config = config
        self.log_path = config.base_dir / "strata.log"

    def estimate_daemon_savings(self) -> dict:
        """Read daemon log, estimate token savings from Janitor automation."""
        if not self.log_path.exists():
            return {
                "error": (
                    "No daemon activity yet. Run 'strata serve' first."
                ),
                "daemon_cycles": {
                    "value": 0,
                    "methodology": "No daemon log found.",
                    "disclaimer": "No daemon activity to analyze.",
                },
                "files_migrated": {
                    "value": 0,
                    "methodology": "No daemon log found.",
                    "disclaimer": "No daemon activity to analyze.",
                },
                "files_evicted": {
                    "value": 0,
                    "methodology": "No daemon log found.",
                    "disclaimer": "No daemon activity to analyze.",
                },
                "lru_decisions": {
                    "value": 0,
                    "methodology": "No daemon log found.",
                    "disclaimer": "No daemon activity to analyze.",
                },
                "tokens_saved_estimate": {
                    "value": 0,
                    "methodology": "No daemon log found.",
                    "disclaimer": "No daemon activity to analyze.",
                },
                "tokens_saved_range": {
                    "value": "0 - 0",
                    "methodology": "No daemon log found.",
                    "disclaimer": "No daemon activity to analyze.",
                },
            }

        content = self.log_path.read_text(encoding="utf-8")

        # Count unique daemon cycles
        cycle_numbers = set(
            int(m) for m in re.findall(r"\[Cycle (\d+)\]", content)
        )
        cycles_count = len(cycle_numbers)

        # Sum migrated counts across all log lines
        migrated = sum(
            int(m) for m in re.findall(r"Migrated:\s*(\d+)", content)
        )

        # Sum evicted counts across all log lines
        evicted = sum(
            int(e) for e in re.findall(r"Evicted:\s*(\d+)", content)
        )

        # Calculate estimated tokens saved
        # Avg active file: ~2000 tokens
        # Avg cooled file: ~1500 tokens / 3 ≈ 500 tokens for partial reads
        tokens_saved = (migrated * 2000) + (evicted * 500)
        lower = int(tokens_saved * 0.8)
        upper = int(tokens_saved * 1.2)

        methodology = (
            "Compared against hypothetical system that stores all files in "
            "active tier indefinitely, requiring full re-processing on each "
            "lifecycle cycle."
        )
        disclaimer = (
            "These are approximate ranges. Actual savings depend on file "
            "sizes and access patterns."
        )

        return {
            "daemon_cycles": {
                "value": cycles_count,
                "methodology": "Counted unique [Cycle N] entries in daemon log.",
                "disclaimer": disclaimer,
            },
            "files_migrated": {
                "value": migrated,
                "methodology": "Summed Migrated values from daemon log lines.",
                "disclaimer": disclaimer,
            },
            "files_evicted": {
                "value": evicted,
                "methodology": "Summed Evicted values from daemon log lines.",
                "disclaimer": disclaimer,
            },
            "lru_decisions": {
                "value": evicted,
                "methodology": (
                    "Each eviction represents an LRU decision "
                    "(evicted count = LRU decisions)."
                ),
                "disclaimer": disclaimer,
            },
            "tokens_saved_estimate": {
                "value": tokens_saved,
                "methodology": methodology,
                "disclaimer": disclaimer,
            },
            "tokens_saved_range": {
                "value": f"{lower:,} - {upper:,}",
                "methodology": methodology,
                "disclaimer": disclaimer,
            },
        }

    def estimate_hook_calls(self) -> dict:
        """Check if any hook log exists (future use). Return empty stats."""
        return {
            "llm_calls_made": {
                "value": 0,
                "methodology": "Hook call tracking not yet implemented.",
                "disclaimer": "No hook call data available.",
            },
            "tokens_consumed_estimate": {
                "value": 0,
                "methodology": "Hook call tracking not yet implemented.",
                "disclaimer": "No hook call data available.",
            },
            "estimated_cost_usd": {
                "value": "$0.00",
                "methodology": "Hook call tracking not yet implemented.",
                "disclaimer": "No hook call data available.",
            },
        }

    def get_summary(self) -> dict:
        """Aggregate all estimates."""
        combined = self.estimate_daemon_savings()
        combined["hook_calls"] = self.estimate_hook_calls()
        return combined
