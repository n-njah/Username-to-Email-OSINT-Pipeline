#!/usr/bin/env python3
"""
Username-to-Email OSINT Pipeline

Main entry point orchestrating enumeration, pivoting, correlation, and reporting.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone
import uuid

# Local imports (ensure project root is in path)
sys.path.insert(0, str(Path(__file__).parent))
from enumeration import enumerate_usernames
from pivots import (
    gravatar_reverse_lookup,
    pivot_github_to_email,
    search_breaches_by_username,
    extract_contacts_from_profiles,
)
from correlation import consolidate_findings, score_confidence
from outputs import generate_json_report, generate_csv_report, generate_html_report


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("username_to_email")


# Canonical module registry: enumeration engines first, then pivots.
ALL_MODULES = [
    "maigret",
    "sherlock",
    "gravatar",
    "github",
    "breach",
    "profile_scrape",
]

# Subset of ALL_MODULES that are enumeration engines.
ENUMERATION_ENGINES = ["maigret", "sherlock"]


def utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="username_to_email",
        description="Chain username enumeration with email discovery pivots",
    )

    parser.add_argument(
        "--username", "-u",
        type=str,
        required=True,
        help="Target username to investigate"
    )

    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Output file path (default: stdout)"
    )

    parser.add_argument(
        "--format", "-f",
        type=str,
        choices=["json", "csv", "html"],
        default="json",
        help="Output format (default: json)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging with stack traces"
    )

    parser.add_argument(
        "--threads", "-t",
        type=int,
        default=10,
        help="Number of concurrent threads (default: 10)"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)"
    )

    parser.add_argument(
        "--exclude",
        type=str,
        default="",
        help="Comma-separated list of modules to exclude (e.g., 'github,breach')"
    )

    parser.add_argument(
        "--only",
        type=str,
        default="",
        help="Comma-separated list of modules to include only"
    )

    return parser.parse_args()


def build_module_config(args: argparse.Namespace) -> Dict[str, bool]:
    """
    Build module enablement configuration from CLI args.

    `--only` takes precedence over `--exclude`. Unknown module names are
    reported as warnings rather than silently ignored.
    """
    exclude = {m.strip().lower() for m in args.exclude.split(",") if m.strip()}
    only = {m.strip().lower() for m in args.only.split(",") if m.strip()}

    unknown = (exclude | only) - set(ALL_MODULES)
    for name in sorted(unknown):
        logger.warning(f"Unknown module name ignored: '{name}'")

    config: Dict[str, bool] = {}
    for module in ALL_MODULES:
        if only:
            config[module] = module in only
        elif exclude:
            config[module] = module not in exclude
        else:
            config[module] = True

    return config


def enabled_engines(config: Dict[str, bool]) -> List[str]:
    """Return only the enumeration engines that are enabled."""
    return [m for m in ENUMERATION_ENGINES if config.get(m)]


async def run_enumeration(
    username: str,
    config: Dict[str, bool],
    timeout: int
) -> Dict:
    """Run username enumeration phase."""
    engines = enabled_engines(config)

    if not engines:
        logger.warning("No enumeration engines enabled; skipping enumeration phase")
        return {
            "username": username,
            "profiles": {},
            "failed_platforms": [],
            "total_checked": 0,
            "execution_time_ms": 0,
        }

    logger.info(f"Starting enumeration for '{username}' using: {', '.join(engines)}")

    results = await enumerate_usernames(
        username=username,
        enabled_modules=engines,
        timeout=timeout,
    )

    logger.info(
        f"Enumeration complete: {len(results.get('profiles', {}))} profiles found"
    )
    return results


async def run_pivots(
    username: str,
    profiles: Dict[str, str],
    config: Dict[str, bool],
    timeout: int
) -> Dict:
    """Run all enabled pivot modules."""
    pivots_result: Dict[str, Dict] = {}

    # Gravatar pivot
    if config.get("gravatar"):
        logger.info("Running Gravatar pivot...")
        try:
            pivots_result["gravatar"] = await gravatar_reverse_lookup(
                username, timeout=timeout
            )
        except Exception as e:
            logger.error(f"Gravatar pivot failed: {e}")
            pivots_result["gravatar"] = {"emails_found": [], "error": str(e)}

    # GitHub commit extraction
    if config.get("github"):
        github_url = profiles.get("github", "")
        if github_url:
            logger.info("Running GitHub pivot...")
            try:
                pivots_result["github"] = await pivot_github_to_email(
                    username, github_url, timeout=timeout
                )
            except Exception as e:
                logger.error(f"GitHub pivot failed: {e}")
                pivots_result["github"] = {"emails_found": [], "error": str(e)}
        else:
            logger.info("No GitHub profile found; skipping GitHub pivot")

    # Breach index lookup
    if config.get("breach"):
        logger.info("Running breach database lookup...")
        try:
            pivots_result["breach"] = await search_breaches_by_username(username)
        except Exception as e:
            logger.error(f"Breach lookup failed: {e}")
            pivots_result["breach"] = {"emails_found": [], "error": str(e)}

    # Profile scraping
    if config.get("profile_scrape"):
        if profiles:
            logger.info("Running profile scraping...")
            try:
                pivots_result["profile_scrape"] = await extract_contacts_from_profiles(
                    profiles, timeout=timeout
                )
            except Exception as e:
                logger.error(f"Profile scraping failed: {e}")
                pivots_result["profile_scrape"] = {"emails_found": [], "error": str(e)}
        else:
            logger.info("No profiles discovered; skipping profile scraping")

    return pivots_result


async def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Configure logging
    log_level = (
        logging.DEBUG if args.debug
        else (logging.INFO if args.verbose else logging.WARNING)
    )
    for handler in logging.root.handlers:
        handler.setLevel(log_level)
    logging.getLogger("username_to_email").setLevel(log_level)

    scan_id = str(uuid.uuid4())
    timestamp = utc_now_iso()

    logger.info(f"Starting scan {scan_id[:8]}...")
    logger.info(f"Target username: {args.username}")

    try:
        # Build configuration
        module_config = build_module_config(args)
        active = [m for m, v in module_config.items() if v]
        logger.info(f"Enabled modules: {active}")

        if not active:
            logger.error("No modules enabled after applying --only/--exclude. Aborting.")
            return 2

        # Phase 1: Enumeration
        enum_results = await run_enumeration(args.username, module_config, args.timeout)
        profiles = enum_results.get("profiles", {})

        # Phase 2: Pivots
        pivot_results = await run_pivots(
            args.username,
            profiles,
            module_config,
            args.timeout,
        )

        # Phase 3: Correlation
        raw_data = {
            "scan_id": scan_id,
            "timestamp": timestamp,
            "target": args.username,
            "enumeration": enum_results,
            "pivots": pivot_results,
        }

        consolidated = await consolidate_findings(raw_data)
        scored = await score_confidence(consolidated)

        # Build final report
        report = {
            "scan_id": scan_id,
            "timestamp": timestamp,
            "target": args.username,
            "modules_executed": module_config,
            "enumeration": {
                "platforms_found": len(profiles),
                "profiles": profiles,
            },
            "pivots": {
                module: {
                    k: v for k, v in results.items()
                    if k not in ["raw_data", "_metadata"]
                }
                for module, results in pivot_results.items()
            },
            "consolidated": {
                "unique_emails": scored.get("unique_emails", []),
                "highest_confidence": scored.get("max_confidence", 0),
                "sources_correlated": len(scored.get("source_mapping", {})),
            },
            "raw_scored_findings": scored,
        }

        # Render output
        if args.format == "json":
            output_data = generate_json_report(report)
        elif args.format == "csv":
            output_data = generate_csv_report(scored)
        else:  # html
            output_data = generate_html_report(report)

        # Emit output
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output_data, encoding="utf-8")
            logger.info(f"Report written to: {args.output}")
            print(f"[+] Report written to: {args.output}")
        else:
            print(output_data)

        logger.info("Scan completed successfully")
        return 0

    except KeyboardInterrupt:
        logger.warning("Scan interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Fatal error during scan: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)