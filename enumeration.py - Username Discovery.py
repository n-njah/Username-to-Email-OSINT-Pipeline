#!/usr/bin/env python3
"""
Enumeration Module

Wraps Maigret and Sherlock for cross-platform username discovery.
"""

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
import json
import os


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("enumeration")


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
    
    try:
        maigret_cmd = [
            "maigret",
            username,
            "--json",
            f"--timeout={timeout}",
            "--no-progress-bar",
        ]
        
        # Add site filters if specified
        if enabled_sites:
            for site in enabled_sites:
                maigret_cmd.extend(["--site", site])
        
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        proc = await asyncio.create_subprocess_exec(
            *maigret_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout * 10  # Overall timeout much higher
        )
        
        if proc.returncode != 0:
            logger.warning(f"Maigret exited with code {proc.returncode}: {stderr.decode()}")
            return {}
        
        data = json.loads(stdout.decode())
        
        # Parse Maigret's JSON output
        profiles = {}
        results = data.get("results", {})
        
        for platform, info in results.items():
            if info.get("status", {}).get("code") == 200:
                url = info.get("url_main") or info.get("url_user")
                if url:
                    profiles[platform.lower()] = url
        
        logger.info(f"Maigret found {len(profiles)} profiles")
        return profiles
        
    except FileNotFoundError:
        logger.error("Maigret not installed. Run: pip install maigret")
        return {}
    except asyncio.TimeoutError:
        logger.error("Maigret execution timed out")
        return {}
    except Exception as e:
        logger.exception(f"Maigret execution failed: {e}")
        return {}


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
    
    try:
        sherlock_cmd = [
            "sherlock",
            username,
            "--json",
            "--silent",
        ]
        
        if enabled_sites:
            for site in enabled_sites:
                sherlock_cmd.extend(["--site", site])
        
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        proc = await asyncio.create_subprocess_exec(
            *sherlock_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout * 10
        )
        
        if proc.returncode not in [0, 1]:  # Exit 1 means some sites not found, which is normal
            logger.warning(f"Sherlock exited with code {proc.returncode}: {stderr.decode()}")
            return {}
        
        data = json.loads(stdout.decode())
        
        profiles = {}
        for platform, info in data.get(username, {}).items():
            if info.get("exist") is True:
                profiles[platform.lower()] = info.get("url")
        
        logger.info(f"Sherlock found {len(profiles)} profiles")
        return profiles
        
    except FileNotFoundError:
        logger.error("Sherlock not installed. Run: pip install sherlock-project")
        return {}
    except asyncio.TimeoutError:
        logger.error("Sherlock execution timed out")
        return {}
    except Exception as e:
        logger.exception(f"Sherlock execution failed: {e}")
        return {}


async def enumerate_usernames(
    username: str,
    enabled_modules: Optional[List[str]] = None,
    timeout: int = 30
) -> EnumerationResult:
    """
    Main enumeration orchestration.
    
    Args:
        username: Target handle to enumerate
        enabled_modules: ['maigret', 'sherlock'] - which engines to use
        timeout: Per-request timeout in seconds
    
    Returns:
        EnumerationResult with all discovered profiles
    """
    import time
    start_time = time.time()
    
    # Determine which engines to run
    engines = enabled_modules or ["maiglet", "sherlock"]
    
    all_profiles: Dict[str, str] = {}
    failed_platforms: Set[str] = set()
    total_checked = 0
    
    # Run Maigret
    if "maigret" in engines:
        profiles = await run_maigret(username, timeout)
        all_profiles.update(profiles)
        total_checked += len(profiles)
    
    # Run Sherlock
    if "sherlock" in engines:
        profiles = await run_sherlock(username, timeout)
        all_profiles.update(profiles)  # Sherlock may have different platform names
        total_checked += len(profiles)
    
    execution_time = int((time.time() - start_time) * 1000)
    
    result = EnumerationResult(
        username=username,
        profiles=all_profiles,
        failed_platforms=list(failed_platforms),
        total_checked=total_checked,
        execution_time_ms=execution_time
    )
    
    logger.info(
        f"Enumeration complete in {execution_time}ms: "
        f"{len(all_profiles)} unique profiles found"
    )
    
    # Convert to dict for API compatibility
    return {
        "username": result.username,
        "profiles": result.profiles,
        "failed_platforms": result.failed_platforms,
        "total_checked": result.total_checked,
        "execution_time_ms": result.execution_time_ms
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
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                allow_redirects=True
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
        config: Optional config dict with 'timeout', 'engines' keys
    
    Returns:
        Serialized EnumerationResult
    """
    timeout = config.get("timeout", 30) if config else 30
    engines = config.get("engines", ["maigret", "sherlock"]) if config else ["maigret", "sherlock"]
    
    result = await enumerate_usernames(target, engines, timeout)
    return result