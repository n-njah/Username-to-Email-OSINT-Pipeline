#!/usr/bin/env python3
"""
Pivots Module

Contains all pivot functions converting usernames to email addresses.
"""

import asyncio
import hashlib
import re
import logging
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse
from dataclasses import dataclass


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pivots")


@dataclass
class EmailFinding:
    """Single email discovery finding."""
    email: str
    source: str
    confidence: int
    context: Optional[str] = None


def generate_gravatar_hash(email: str) -> str:
    """Generate MD5 hash for Gravatar API lookup."""
    return hashlib.md5(email.lower().strip().encode()).hexdigest()


def generate_candidate_emails(username: str, extra_elements: Optional[List[str]] = None) -> List[str]:
    """
    Generate candidate email addresses from username and name fragments.
    
    Args:
        username: The handle to derive candidates from
        extra_elements: Additional strings like first/last names
    
    Returns:
        List of candidate email strings
    """
    candidates = []
    
    # Normalize username
    base = username.replace("_", "").replace(".", "").replace("-", "")
    
    # Common domain list
    domains = [
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
        "icloud.com", "protonmail.com", "aol.com", "live.com"
    ]
    
    # Generate variations
    variations = [base]
    
    # Add numbered variations
    for i in range(10):
        variations.append(f"{base}{i}")
    
    # Add underscore variations
    variations.append(f"{base}_")
    variations.append(f"_ {base}")
    
    # Add extra elements
    if extra_elements:
        for element in extra_elements:
            element_clean = element.replace(" ", "").lower()
            variations.append(f"{base}{element_clean}")
            variations.append(f"{element_clean}{base}")
    
    # Remove duplicates and filter short strings
    variations = list(set(v for v in variations if len(v) > 2))
    
    # Combine with domains
    for var in variations:
        for domain in domains:
            candidates.append(f"{var}@{domain}")
    
    return candidates


async def gravatar_reverse_lookup(
    username: str,
    timeout: int = 10,
    extra_elements: Optional[List[str]] = None
) -> Dict:
    """
    Attempt to discover emails via Gravatar hash reversal.
    
    Uses hashtray-like logic to test candidate hashes against Gravatar.
    
    Args:
        username: Target handle
        timeout: Request timeout
        extra_elements: Name fragments for better candidate generation
    
    Returns:
        Dict with 'emails_found', 'profile_info', 'confidence'
    """
    logger.info(f"Running Gravatar reverse lookup for: {username}")
    
    import aiohttp
    
    # Generate candidate emails
    candidates = generate_candidate_emails(username, extra_elements)
    
    emails_found: List[str] = []
    profile_info: Dict = {}
    successful_hashes = 0
    
    async with aiohttp.ClientSession() as session:
        for candidate in candidates:
            email_hash = generate_gravatar_hash(candidate)
            
            # Check Gravatar for this hash
            url = f"https://www.gravatar.com/avatar/{email_hash}?d=404"
            
            try:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    headers={"User-Agent": "OSINT-Pipeline/1.0"}
                ) as resp:
                    if resp.status == 200:
                        # Success! This hash corresponds to a real email
                        emails_found.append(mask_email(candidate))
                        successful_hashes += 1
                        
                        # Try to fetch profile data
                        profile_url = f"https://www.gravatar.com/{email_hash}"
                        
            except Exception as e:
                logger.debug(f"Gravatar check failed for {candidate}: {e}")
                continue
    
    # Calculate confidence based on hits
    confidence = min(100, successful_hashes * 25)
    
    result = {
        "emails_found": emails_found,
        "successful_hashes": successful_hashes,
        "candidates_tested": len(candidates),
        "profile_info": profile_info,
        "confidence": confidence
    }
    
    logger.info(f"Gravatar lookup complete: {successfu

l_hashes} hits, confidence {confidence}%")
    return result


async def pivot_github_to_email(
    username: str,
    github_profile_url: str,
    timeout: int = 30
) -> Dict:
    """
    Extract emails from GitHub commit metadata.
    
    Walks through user's commits and parses .patch endpoints for
    author/committer email fields.
    
    Args:
        username: GitHub handle
        github_profile_url: Profile URL (may be None if not found)
        timeout: Request timeout
    
    Returns:
        Dict with 'emails_found', 'commits_checked', 'repos_touched'
    """
    logger.info(f"Running GitHub pivot for: {username}")
    
    import aiohttp
    
    emails_found: Set[str] = set()
    commits_checked = 0
    repos_touched: Set[str] = set()
    
    # GitHub API base
    api_base = "https://api.github.com"
    
    async with aiohttp.ClientSession() as session:
        try:
            # Step 1: Get user's events/commits
            events_url = f"{api_base}/users/{username}/events/public"
            
            async with session.get(
                events_url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                headers={
                    "User-Agent": "OSINT-Pipeline/1.0",
                    "Authorization": f"token {get_github_token()}"
                }
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"GitHub API returned {resp.status}")
                    return {"emails_found": [], "commits_checked": 0, "repos_touched": []}
                
                events = await resp.json()
            
            # Step 2: Process PushEvents for commit data
            for event in events[:50]:  # Limit to first 50 events
                if event.get("type") != "PushEvent":
                    continue
                
                repo_name = event.get("repo", {}).get("name", "")
                if repo_name:
                    repos_touched.add(repo_name)
                
                payload = event.get("payload", {})
                for commit in payload.get("commits", [])[:10]:  # First 10 commits per push
                    author_email = commit.get("author", {}).get("email")
                    if author_email and not author_email.endswith("@users.noreply.github.com"):
                        emails_found.add(author_email)
                    commits_checked += 1
            
            # Step 3: If we found repos, try .patch endpoint method
            for repo in list(repos_touched)[:5]:  # Limit processing
                try:
                    owner, repo_name = repo.split("/", 1)
                    patch_url = f"{api_base}/repos/{owner}/{repo_name}/commits?per_page=5"
                    
                    async with session.get(
                        patch_url,
                        timeout=aiohttp.ClientTimeout(total=timeout)
                    ) as resp:
                        if resp.status == 200:
                            commits = await resp.json()
                            for commit in commits:
                                commit_sha = commit.get("sha", "")
                                patch_full = f"{api_base}/repos/{owner}/{repo_name}/commits/{commit_sha}.patch"
                                
                                async with session.get(patch_full) as patch_resp:
                                    if patch_resp.status == 200:
                                        patch_content = await patch_resp.text()
                                        extracted = extract_email_from_patch(patch_content)
                                        for email in extracted:
                                            if not email.endswith("@users.noreply.github.com"):
                                                emails_found.add(email)
                                        commits_checked += 1
                except Exception as e:
                    logger.debug(f"Patch extraction failed for {repo}: {e}")
                    continue
                    
        except Exception as e:
            logger.exception(f"GitHub pivot failed: {e}")
    
    result = {
        "emails_found": list(emails_found),
        "commits_checked": commits_checked,
        "repos_touched": list(repos_touched),
        "confidence": min(100, len(emails_found) * 50)
    }
    
    logger.info(f"GitHub pivot complete: {len(emails_found)} emails from {commits_checked} commits")
    return result


def extract_email_from_patch(patch_content: str) -> List[str]:
    """
    Parse email addresses from Git patch content.
    
    Args:
        patch_content: Raw .patch file text
    
    Returns:
        List of extracted email addresses
    """
    # Match author/committer lines
    email_pattern = r"(?:Author|Committer):\s*[^(]*\(([^)]+@[^)]+)\)"
    emails = re.findall(email_pattern, patch_content)
    
    # Also match generic email patterns in patch
    generic_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    emails.extend(re.findall(generic_pattern, patch_content))
    
    return list(set(emails))


async def search_breaches_by_username(
    username: str,
    api_key: Optional[str] = None
) -> Dict:
    """
    Query breach databases for username-indexed records.
    
    Note: This requires external API access to services like IntelX,
    DeHashed, etc. Placeholder implementation provided.
    
    Args:
        username: Target handle to search
        api_key: External API key if configured
    
    Returns:
        Dict with 'emails_found', 'breach_records', 'sources'
    """
    logger.info(f"Running breach lookup for: {username}")
    
    # Placeholder - implement based on chosen breach service API
    # This is where you'd integrate with IntelX, DeHashed, HaveIBeenPwned, etc.
    
    result = {
        "emails_found": [],
        "breach_records": [],
        "sources_checked": [],
        "confidence": 0,
        "_note": "Breach API integration required - see documentation"
    }
    
    return result


def extract_email_from_patch(patch_content: str) -> List[str]:
    """
    Parse email addresses from Git patch content.
    
    Args:
        patch_content: Raw .patch file text
    
    Returns:
        List of extracted email addresses
    """
    # Match author/committer lines
    email_pattern = r"(?:Author|Committer):\s*[^(]*\(([^)]+@[^)]+)\)"
    emails = re.findall(email_pattern, patch_content)
    
    # Also match generic email patterns in patch
    generic_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    emails.extend(re.findall(generic_pattern, patch_content))
    
    return list(set(emails))


async def extract_contacts_from_profiles(
    profiles: Dict[str, str],
    timeout: int = 30
) -> Dict:
    """
    Scrape contact information from discovered profile URLs.
    
    Args:
        profiles: Dict mapping platform to profile URL
        timeout: Request timeout
    
    Returns:
        Dict with 'emails_found', 'contacts_extracted'
    """
    logger.info(f"Scraping contacts from {len(profiles)} profiles")
    
    import aiohttp
    from bs4 import BeautifulSoup
    
    emails_found: List[str] = []
    contacts: Dict[str, str] = {}
    
    # Email regex pattern
    email_regex = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    
    async with aiohttp.ClientSession() as session:
        for platform, url in profiles.items():
            try:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    headers={"User-Agent": "OSINT-Pipeline/1.0"}
                ) as resp:
                    if resp.status != 200:
                        continue
                    
                    html = await resp.text()
                    
                    # Parse with BeautifulSoup
                    soup = BeautifulSoup(html, "html.parser")
                    
                    # Extract visible text
                    text_content = soup.get_text(separator=" ")
                    
                    # Find all emails in page
                    page_emails = email_regex.findall(text_content)
                    
                    # Filter out obvious non-personal emails
                    filtered = [
                        e for e in page_emails 
                        if not any(x in e.lower() for x in ["support@", "admin@", "info@", "noreply@"])
                    ]
                    
                    emails_found.extend(filtered)
                    
                    # Extract other contact info
                    contacts[platform] = {
                        "emails": list(set(filtered)),
                        "bio": _extract_bio(soup),
                        "links": _extract_links(soup)
                    }
                    
            except Exception as e:
                logger.debug(f"Profile scrape failed for {platform}: {e}")
                continue
    
    result = {
        "emails_found": list(set(emails_found)),
        "contacts_extracted": contacts,
        "profiles_processed": len(profiles)
    }
    
    logger.info(f"Profile scraping complete: {len(set(emails_found))} unique emails")
    return result


def _extract_bio(soup: BeautifulSoup) -> Optional[str]:
    """Extract bio text from parsed HTML."""
    selectors = [
        "[class*='bio']",
        "[class*='description']",
        "[class*='about']",
        "meta[name='description']",
        ".bio",
        ".description"
    ]
    
    for selector in selectors:
        try:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)[:280]
        except Exception:
            continue
    
    return None


def _extract_links(soup: BeautifulSoup) -> List[str]:
    """Extract external links from parsed HTML."""
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith(("http://", "https://")):
            links.append(href)
    return list(set(links))[:10]


def mask_email(email: str) -> str:
    """Partially mask email for safe display."""
    if "@" not in email:
        return email
    
    local, domain = email.rsplit("@", 1)
    masked_local = local[:2] + "*" * (len(local) - 2) if len(local) > 2 else local
    return f"{masked_local}@{domain}"


def get_github_token() -> Optional[str]:
    """Retrieve GitHub token from environment."""
    import os
    return os.environ.get("GITHUB_TOKEN")


# MCP integration hook
async def mpc_pivot(source_type: str, target: str, context: dict) -> dict:
    """
    MCP-compatible pivot entry point.
    
    Args:
        source_type: 'gravatar', 'github', 'breach', 'scrape'
        target: Username or email depending on source
        context: Additional context (API keys, tokens, etc.)
    
    Returns:
        Pivot results dict
    """
    if source_type == "gravatar":
        return await gravatar_reverse_lookup(target, extra_elements=context.get("names"))
    elif source_type == "github":
        return await pivot_github_to_email(target, context.get("github_url", ""))
    elif source_type == "breach":
        api_key = context.get("breach_api_key")
        return await search_breaches_by_username(target, api_key)
    elif source_type == "scrape":
        profiles = context.get("profiles", {})
        return await extract_contacts_from_profiles(profiles)
    else:
        raise ValueError(f"Unknown pivot source type: {source_type}")