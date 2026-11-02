#!/usr/bin/env python3
"""
Enumeration Module

Wraps Maigret and Sherlock for cross-platform username discovery.
"""

import asyncio
import logging
import json
import os
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("enumeration")


# Valid engine identifiers
VALID_ENGINES = ("maigret", "sherlock")


@dataclass
class ProfileResult:
    """Single profile discovery result."""
    platform: str
    url: str
    status_code: Optional[int] = None
    exists: bool = True


@dataclass
class EnumerationResult:
    """Complete enumeration batch result."""
    username: str
    profiles: Dict[str, str]
    failed_platforms: List[str]
    total_checked: int
    execution_time_ms: int


async def _run_subprocess(
    cmd: List[str],
    timeout: int,
    label: str
) -> Optional[str]:
    """
    Run a subprocess and return stdout, or None on failure.

    Shared helper so Maigret and Sherlock handle errors identically.
    """
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
    except FileNotFoundError:
        logger.error(f"{label} not installed or not on PATH")
        return None

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=max(timeout * 10, 60),
        )
    except asyncio.TimeoutError:
        logger.error(f"{label} execution timed out")
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        return None

    if stderr:
        logger.debug(f"{label} stderr: {stderr.decode(errors='replace')[:500]}")

    if stdout:
        return stdout.decode(errors="replace")

    logger.warning(f"{label} produced no stdout (exit code {proc.returncode})")
    return None


async def run_maigret(
    username: str,
    timeout: int = 30,
    enabled_sites: Optional[List[str]] = None
) -> Dict[str, str]:
    """
    Run Maigret enumeration and parse results.

    Args:
        username: Target handle to search
        timeout: Request timeout per site
        enabled_sites: Optional whitelist of sites to check

    Returns:
        Dict mapping platform name to profile URL
    """
    logger.info(f"Running Maigret for username: {username}")

    cmd = [
        "maigret",
        username,
        "--json", "simple",
        f"--timeout={timeout}",
        "--no-progressbar",
    ]

    if enabled_sites:
        for site in enabled_sites:
            cmd.extend(["--site", site])

    stdout = await _run_subprocess(cmd, timeout, "Maigret")
    if not stdout:
        return {}

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Maigret JSON output: {e}")
        return {}

    profiles: Dict[str, str] = {}

    # Maigret's schema varies by version: handle both shapes.
    if isinstance(data, dict) and "sites" in data:
        # --json simple format: {"sites": {"SiteName": {"url_user": ..., "status": {...}}}}
        for platform, info in data.get("sites", {}).items():
            if not isinstance(info, dict):
                continue
            status = info.get("status", {})
            code = status.get("code") if isinstance(status, dict) else None
            if code == 200 or info.get("exists") is True:
                url = info.get("url_user") or info.get("url_main")
                if url:
                    profiles[platform.lower()] = url
    else:
        # Fallback: nested results format
        for platform, info in (data.get("results") or {}).items():
            if not isinstance(info, dict):
                continue
            status = info.get("status", {})
            code = status.get("code") if isinstance(status, dict) else None
            if code == 200:
                url = info.get("url_main") or info.get("url_user")
                if url:
                    profiles[platform.lower()] = url

    logger.info(f"Maigret found {len(profiles)} profiles")
    return profiles


async def run_sherlock(
    username: str,
    timeout: int = 30,
    enabled_sites: Optional[List[str]] = None
) -> Dict[str, str]:
    """
    Run Sherlock enumeration and parse results.

    Args:
        username: Target handle to search
        timeout: Request timeout per site
        enabled_sites: Optional whitelist of sites to check

    Returns:
        Dict mapping platform name to profile URL
    """
    logger.info(f"Running Sherlock for username: {username}")

    cmd = [
        "sherlock",
        username,
        "--json",
        "--print-found",
        "--no-color",
    ]

    if enabled_sites:
        for site in enabled_sites:
            cmd.extend(["--site", site])

    stdout = await _run_subprocess(cmd, timeout, "Sherlock")
    if not stdout:
        return {}

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Sherlock JSON output: {e}")
        return {}

    profiles: Dict[str, str] = {}
    user_block = data.get(username, data) if isinstance(data, dict) else {}

    for platform, info in (user_block or {}).items():
        if not isinstance(info, dict):
            continue
        if info.get("exists") is True or info.get("exist") is True:
            url = info.get("url_user") or info.get("url")
            if url:
                profiles[platform.lower()] = url

    logger.info(f"Sherlock found {len(profiles)} profiles")
    return profiles


async def enumerate_usernames(
    username: str,
    enabled_modules: Optional[List[str]] = None,
    timeout: int = 30
) -> Dict:
    """
    Main enumeration orchestration.

    Args:
        username: Target handle to enumerate
        enabled_modules: Subset of ('maigret', 'sherlock'); unknown names ignored
        timeout: Per-request timeout in seconds

    Returns:
        Serialized EnumerationResult
    """
    start_time = time.time()

    # Filter to valid engines only. If caller passed pivot names, ignore them.
    requested = enabled_modules if enabled_modules is not None else list(VALID_ENGINES)
    engines = [e for e in requested if e in VALID_ENGINES]

    ignored = [e for e in requested if e not in VALID_ENGINES]
    if ignored:
        logger.debug(f"Ignoring non-enumeration modules: {ignored}")

    if not engines:
        logger.warning("No valid enumeration engines requested")
        return {
            "username": username,
            "profiles": {},
            "failed_platforms": [],
            "total_checked": 0,
            "execution_time_ms": 0,
        }

    all_profiles: Dict[str, str] = {}
    failed_platforms: Set[str] = set()

    for engine in engines:
        try:
            if engine == "maigret":
                found = await run_maigret(username, timeout)
            else:
                found = await run_sherlock(username, timeout)
            all_profiles.update(found)
        except Exception as e:
            logger.error(f"{engine} raised an exception: {e}")
            failed_platforms.add(engine)

    execution_time = int((time.time() - start_time) * 1000)

    result = EnumerationResult(
        username=username,
        profiles=all_profiles,
        failed_platforms=sorted(failed_platforms),
        total_checked=len(all_profiles),
        execution_time_ms=execution_time,
    )

    logger.info(
        f"Enumeration complete in {execution_time}ms: "
        f"{len(all_profiles)} unique profiles found"
    )

    return {
        "username": result.username,
        "profiles": result.profiles,
        "failed_platforms": result.failed_platforms,
        "total_checked": result.total_checked,
        "execution_time_ms": result.execution_time_ms,
    }


async def validate_profile(url: str, timeout: int = 10) -> Optional[int]:
    """
    Verify that a discovered profile URL actually resolves.

    Args:
        url: Profile URL to validate
        timeout: Request timeout

    Returns:
        HTTP status code if accessible, None if not
    """
    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                allow_redirects=True,
            ) as resp:
                return resp.status
    except Exception as e:
        logger.debug(f"Profile validation failed for {url}: {e}")
        return None


# Integration hook for MCP agents
async def mpc_enumerate(target: str, config: Optional[dict] = None) -> dict:
    """
    MCP-compatible enumeration entry point.

    Args:
        target: Username string
        config: Optional dict with 'timeout' and 'engines' keys

    Returns:
        Serialized EnumerationResult
    """
    config = config or {}
    timeout = config.get("timeout", 30)
    engines = config.get("engines", list(VALID_ENGINES))

    return await enumerate_usernames(target, engines, timeout)