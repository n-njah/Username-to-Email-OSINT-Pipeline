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
from datetime import datetime
import uuid

# Local imports (ensure src/ is in path)
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
    """Build module enablement configuration from CLI args."""
    exclude = set(m.strip() for m in args.exclude.split(",") if m.strip())
    only = set(m.strip() for m in args.only.split(",") if m.only)

    all_modules = ["maigret", "gravatar", "github", "breach", "profile_scrape"]

    config = {}
    for module in all_modules:
        if only:
            config[module] = module in only
        elif exclude:
            config[module] = module not in exclude
        else:
            config[module] = True

    return config


async def run_enumeration(username: str, config: Dict[str, bool], timeout: int) -> Dict:
    """Run username enumeration phase."""
    logger.info(f"Starting enumeration for username: {username}")
    
    results = await enumerate_usernames(
        username=username,
        enabled_modules=[m for m, enabled in config.items() if enabled],
        timeout=timeout
    )
    
    logger.info(f"Enumeration complete: {len(results.get('profiles', {}))} profiles found")
    return results


async def run_pivots(
    username: str,
    profiles: Dict[str, str],
    config: Dict[str, bool],
    timeout: int
) -> Dict:
    """Run all enabled pivot modules."""
    pivots_result = {}

    # Gravatar pivot
    if config.get("gravatar"):
        logger.info("Running Gravatar pivot...")
        pivots_result["gravatar"] = await gravatar_reverse_lookup(username, timeout)

    # GitHub commit extraction
    if config.get("github") and "github" in profiles:
        logger.info("Running GitHub pivot...")
        pivots_result["github"] = await pivot_github_to_email(
            username, 
            profiles["github"], 
            timeout
        )

    # Breach index lookup
    if config.get("breach"):
        logger.info("Running breach database lookup...")
        pivots_result["breach"] = await search_breaches_by_username(username)

    # Profile scraping
    if config.get("profile_scrape") and profiles:
        logger.info("Running profile scraping...")
        pivots_result["profile_scrape"] = await extract_contacts_from_profiles(
            profiles,
            timeout=timeout
        )

    return pivots_result


async def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.debug else (logging.INFO if args.verbose else logging.WARNING)
    for handler in logging.root.handlers:
        handler.setLevel(log_level)

    scan_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat() + "Z"

    logger.info(f"Starting scan {scan_id[:8]}...")
    logger.info(f"Target username: {args.username}")

    try:
        # Build configuration
        module_config = build_module_config(args)
        logger.info(f"Enabled modules: {[m for m, v in module_config.items() if v]}")

        # Phase 1: Enumeration
        enum_results = await run_enumeration(args.username, module_config, args.timeout)
        profiles = enum_results.get("profiles", {})

        # Phase 2: Pivots
        pivot_results = await run_pivots(
            args.username, 
            profiles, 
            module_config, 
            args.timeout
        )

        # Phase 3: Correlation
        raw_data = {
            "scan_id": scan_id,
            "timestamp": timestamp,
            "target": args.username,
            "enumeration": enum_results,
            "pivots": pivot_results
        }
        
        consolidated = consolidate_findings(raw_data)
        scored = score_confidence(consolidated)

        # Build final report
        report = {
            "scan_id": scan_id,
            "timestamp": timestamp,
            "target": args.username,
            "modules_executed": module_config,
            "enumeration": {
                "platforms_found": len(profiles),
                "profiles": profiles
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
                "sources_correlated": len(scored.get("source_mapping", {}))
            },
            "raw_scored_findings": scored
        }

        # Output
        if args.format == "json":
            output_data = generate_json_report(report)
        elif args.format == "csv":
            output_data = generate_csv_report(scored)
        elif args.format == "html":
            output_data = generate_html_report(report)

        # Write output
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output_data)
            logger.info(f"Report written to: {args.output}")
        else:
            print(output_data)

        logger.info(f"Scan completed successfully")
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