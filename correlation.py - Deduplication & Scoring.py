#!/usr/bin/env python3
"""
Correlation Module

Deduplicates findings and assigns confidence scores across all sources.
"""

import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict
from difflib import SequenceMatcher


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("correlation")


@dataclass
class Finding:
    """Individual email discovery record."""
    email: str
    source: str
    platform_context: Optional[str] = None
    raw_data: Optional[dict] = None


@dataclass
class ScoredFinding:
    """Finding with confidence score and metadata."""
    email: str
    confidence: int
    sources: List[str] = field(default_factory=list)
    first_seen: Optional[str] = None
    evidence_chain: List[Dict] = field(default_factory=list)


def normalize_email(email: str) -> str:
    """
    Normalize email for deduplication.
    
    Handles case normalization, removes dots (Gmail), and subaddresses.
    """
    email = email.lower().strip()
    
    # Gmail ignores dots
    if "@gmail.com" in email:
        local, domain = email.split("@")
        local = local.replace(".", "")
        email = f"{local}@gmail.com"
    
    # Remove subaddress (+tag)
    if "+" in email:
        local, domain = email.split("@")
        local = local.split("+")[0]
        email = f"{local}@{domain}"
    
    return email


def levenshtein_similarity(a: str, b: str) -> float:
    """Calculate string similarity using difflib."""
    return SequenceMatcher(None, a, b).ratio()


async def consolidate_findings(raw_data: Dict) -> Dict:
    """
    Merge findings from all pivot modules.
    
    Args:
        raw_data: Consolidated output from enumeration + pivots
    
    Returns:
        Dict with deduplicated email list and source mappings
    """
    logger.info("Starting findings consolidation")
    
    all_finding

s: List[Finding] = []
    email_sources: Dict[str, Set[str]] = defaultdict(set)
    
    # Extract from enumeration (indirect)
    enum_data = raw_data.get("enumeration", {})
    profiles = enum_data.get("profiles", {})
    
    # Extract from each pivot
    pivots = raw_data.get("pivots", {})
    
    if "gravatar" in pivots:
        for email in pivots["gravatar"].get("emails_found", []):
            finding = Finding(
                email=email,
                source="gravatar",
                platform_context="hash_reversal"
            )
            all_findings.append(finding)
            normalized = normalize_email(email)
            email_sources[normalized].add("gravatar")
    
    if "github" in pivots:
        for email in pivots["github"].get("emails_found", []):
            finding = Finding(
                email=email,
                source="github",
                platform_context=f"{pivots['github'].get('commits_checked', 0)} commits checked"
            )
            all_findings.append(finding)
            normalized = normalize_email(email)
            email_sources[normalized].add("github")
    
    if "breach" in pivots:
        for email in pivots["breach"].get("emails_found", []):
            finding = Finding(
                email=email,
                source="breach",
                platform_context=f"{len(pivots['breach'].get('breach_records', []))} breaches"
            )
            all_findings.append(finding)
            normalized = normalize_email(email)
            email_sources[normalized].add("breach")
    
    if "profile_scrape" in pivots:
        for email in pivots["profile_scrape"].get("emails_found", []):
            finding = Finding(
                email=email,
                source="profile_scrape",
                platform_context="web_extraction"
            )
            all_findings.append(finding)
            normalized = normalize_email(email)
            email_sources[normalized].add("profile_scrape")
    
    # Deduplicate
    unique_emails = list(email_sources.keys())
    
    result = {
        "total_findings": len(all_findings),
        "unique_emails": unique_emails,
        "source_mapping": {email: list(sources) for email, sources in email_sources.items()},
        "findings": [
            {
                "email": f.email,
                "source": f.source,
                "platform_context": f.platform_context
            }
            for f in all_findings
        ],
        "consolidated": {
            "emails_with_multiple_sources": [
                email for email, sources in email_sources.items()
                if len(sources) > 1
            ]
        }
    }
    
    logger.info(
        f"Consolidation complete: "
        f"{len(unique_emails)} unique emails from {len(all_findings)} total findings"
    )
    
    return result


async def score_confidence(con

solidated: Dict) -> Dict:
    """
    Assign confidence scores to each email based on evidence quality.
    
    Scoring factors:
    - Number of sources confirming the same email
    - Quality of source (direct extraction vs inferred)
    - Context richness (more context = higher confidence)
    
    Args:
        consolidated: Output from consolidate_findings
    
    Returns:
        Dict with scored findings and max confidence
    """
    logger.info("Calculating confidence scores")
    
    # Source quality weights
    source_weights = {
        "gravatar": 0.7,      # Direct hash match = high confidence
        "github": 0.8,        # Commit metadata = very high confidence
        "breach": 0.6,        # Leaked data = moderate-high
        "profile_scrape": 0.4  # Web scraping = moderate (could be stale)
    }
    
    scored_findings = []
    source_mapping = consolidated.get("source_mapping", {})
    findings = consolidated.get("findings", [])
    
    # Build evidence chain per email
    email_evidence: Dict[str, List[Dict]] = defaultdict(list)
    
    for finding in findings:
        email = normalize_email(finding["email"])
        email_evidence[email].append({
            "source": finding["source"],
            "context": finding.get("platform_context"),
            "weight": source_weights.get(finding["source"], 0.5)
        })
    
    # Calculate scores
    for email in consolidated.get("unique_emails", []):
        evidence = email_evidence.get(email, [])
        
        if not evidence:
            continue
        
        # Base score from source quality
        base_score = sum(e["weight"] for e in evidence) / len(evidence)
        
        # Multiplier for multiple sources
        source_count = len(source_mapping.get(email, []))
        multiplier = 1 + (0.2 * (source_count - 1))  # +20% per additional source
        
        # Cap at 100
        confidence = min(100, int(base_score * 100 * multiplier))
        
        scored = ScoredFinding(
            email=email,
            confidence=confidence,
            sources=[e["source"] for e in evidence],
            evidence_chain=evidence
        )
        
        scored_findings.append({
            "email": email,
            "confidence": confidence,
            "sources": scored.sources,
            "evidence_count": len(evidence)
        })
    
    # Sort by confidence descending
    scored_findings.sort(key=lambda x: x["confidence"], reverse=True)
    
    # Build result
    max_confidence = scored_findings[0]["confidence"] if scored_findings else 0
    
    result = {
        "unique_emails": [sf["email"] for sf in scored_findings],
        "max_confidence": max_confidence,
        "scored_findings": scored_findings,
        "source_mapping": source_mapping
    }
    
    logger.info(f"Confidence scoring complete: max score {max_confidence}%")
    return result


def calculate_similarity_scores(findings: List[Dict]) -> List[Dict]:
    """
    Calculate similarity between email variants for fuzzy deduplication.
    
    Useful when same person uses slight variations.
    
    Args:
        findings: List of finding dicts with 'email' keys
    
    Returns:
        List of similar email pairs with similarity scores
    """
    emails = [normalize_email(f["email"]) for f in findings]
    similar_pairs = []
    
    for i, email_a in enumerate(emails):
        for email_b in emails[i+1:]:
            sim = levenshtein_similarity(email_a, email_b)
            if sim > 0.7:  # Threshold for "similar"
                similar_pairs.append({
                    "email_a": email_a,
                    "email_b": email_b,
                    "similarity": round(sim, 2)
                })
    
    return similar_pairs


def generate_summary_stats(scored: Dict) -> Dict:
    """
    Generate summary statistics for reporting.
    
    Args:
        scored: Output from score_confidence
    
    Returns:
        Dict with aggregate statistics
    """
    findings = scored.get("scored_findings", [])
    
    if not findings:
        return {
            "total_emails": 0,
            "avg_confidence": 0,
            "high_confidence_count": 0,
            "multi_source_count": 0
        }
    
    confidences = [f["confidence"] for f in findings]
    
    return {
        "total_emails": len(findings),
        "avg_confidence": round(sum(confidences) / len(confidences), 1),
        "high_confidence_count": len([c for c in confidences if c >= 75]),
        "medium_confidence_count": len([c for c in confidences if 50 <= c < 75]),
        "low_confidence_count": len([c for c in confidences if c < 50]),
        "multi_source_count": len([f for f in findings if len(f.get("sources", [])) > 1])
    }


# MCP integration hook
async def mpc_correlate(findings: list) -> dict:
    """
    MCP-compatible correlation entry point.
    
    Args:
        findings: List of finding dicts from various sources
    
    Returns:
        Consolidated and scored results
    """
    # Build raw_data structure expected by consolidate_findings
    raw_data = {
        "enumeration": {"profiles": {}},
        "pivots": {}
    }
    
    # Parse findings into pivot structure
    source_groups = defaultdict(list)
    for f in findings:
        source_groups[f.get("source", "unknown")].append(f.get("email"))
    
    for source, emails in source_groups.items():
        raw_data["pivots"][source] = {"emails_found": emails}
    
    consolidated = await consolidate_findings(raw_data)
    scored = await score_confidence(consolidated)
    
    return scored