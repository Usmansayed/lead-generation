"""Shared keyword matching utility for all lead scraper actors.

Provides intelligent fuzzy keyword matching that goes beyond exact substring
matching. Used by all 15 actors for consistent lead discovery.
"""

import re
from typing import Any

# Common synonyms for lead generation terms
SYNONYMS = {
    'developer': ['dev', 'engineer', 'programmer', 'coder', 'software'],
    'hiring': ['hire', 'recruiting', 'looking for', 'seeking', 'need', 'wanted'],
    'freelance': ['freelancer', 'contract', 'contractor', 'consultant', 'gig'],
    'startup': ['start-up', 'early stage', 'early-stage', 'founded', 'launch'],
    'cofounder': ['co-founder', 'cofounder', 'co founder', 'technical founder'],
    'remote': ['work from home', 'wfh', 'distributed', 'anywhere'],
    'fullstack': ['full-stack', 'full stack', 'fullstack'],
    'frontend': ['front-end', 'front end', 'frontend', 'react', 'vue', 'angular'],
    'backend': ['back-end', 'back end', 'backend', 'api', 'server'],
    'mobile': ['ios', 'android', 'react native', 'flutter'],
    'web': ['website', 'webapp', 'web app', 'web application'],
    'python': ['django', 'flask', 'fastapi'],
    'javascript': ['js', 'typescript', 'ts', 'node', 'nodejs'],
    'budget': ['pay', 'salary', 'compensation', 'rate', '$'],
    'urgent': ['asap', 'immediately', 'right away', 'quick', 'fast'],
    'help': ['assist', 'support', 'guidance', 'advice'],
    'build': ['create', 'develop', 'make', 'implement', 'design'],
    'project': ['app', 'application', 'platform', 'tool', 'product', 'mvp', 'saas'],
}

# Lead signal words - any of these in text suggest a potential lead
LEAD_SIGNAL_WORDS = [
    'hiring', 'hire', 'looking for', 'seeking', 'need',
    'developer', 'engineer', 'programmer', 'designer',
    'freelance', 'contract', 'consultant',
    'cofounder', 'co-founder', 'technical founder',
    'help wanted', 'job', 'opportunity', 'position',
    'project', 'build', 'create', 'develop',
    'budget', 'pay', 'compensation', 'salary', 'rate',
    'startup', 'saas', 'mvp', 'prototype',
    'remote', 'full-time', 'part-time',
    'urgent', 'asap', 'immediately',
]


def smart_matches_keywords(text: str, keywords: list[str],
                           use_signals: bool = True,
                           min_word_matches: int = 1) -> tuple[bool, list[str]]:
    """Smart keyword matching with fuzzy, word-level, and synonym support.

    Args:
        text: The text to search in
        keywords: List of keyword phrases to match
        use_signals: If True, also match against built-in lead signal words
        min_word_matches: Minimum number of word matches required

    Returns:
        Tuple of (matched: bool, matched_keywords: list[str])
    """
    if not text:
        return False, []

    # If no keywords provided, match everything (scrape all)
    if not keywords:
        return True, ['<all>']

    text_lower = text.lower()
    text_words = set(re.findall(r'\b\w+\b', text_lower))
    matched = []

    for keyword in keywords:
        keyword_lower = keyword.lower().strip()

        # Strategy 1: Exact substring match (original behavior)
        if keyword_lower in text_lower:
            matched.append(keyword)
            continue

        # Strategy 2: Word-level matching
        keyword_words = set(re.findall(r'\b\w+\b', keyword_lower))
        # Remove very short/common words
        keyword_words = {w for w in keyword_words if len(w) > 2}

        if keyword_words:
            common_words = keyword_words & text_words
            # Match if enough words from the keyword are present
            match_ratio = len(common_words) / len(keyword_words) if keyword_words else 0
            if match_ratio >= 0.5 and len(common_words) >= min_word_matches:
                matched.append(keyword)
                continue

        # Strategy 3: Synonym matching
        for word in keyword_words:
            # Check if any synonym of this keyword word appears in text
            if word in SYNONYMS:
                for synonym in SYNONYMS[word]:
                    if synonym in text_lower:
                        matched.append(keyword)
                        break
                if keyword in matched:
                    break
            # Also check reverse: is this word a synonym of something?
            for base_word, syns in SYNONYMS.items():
                if word in syns and base_word in text_lower:
                    matched.append(keyword)
                    break
            if keyword in matched:
                break

    # Strategy 4: If no keyword matches but signals enabled, check for lead signals
    if not matched and use_signals:
        signal_matches = []
        for signal in LEAD_SIGNAL_WORDS:
            if signal in text_lower:
                signal_matches.append(f'[signal:{signal}]')
        if len(signal_matches) >= 2:  # Need at least 2 signal words
            matched = signal_matches[:3]  # Return top 3

    # Deduplicate
    matched = list(dict.fromkeys(matched))

    return len(matched) > 0, matched


def calculate_base_quality_score(text: str, platform: str = 'generic') -> float:
    """Calculate a base quality score for any content based on lead signals.

    Returns a score from 0-100.
    """
    if not text:
        return 0

    text_lower = text.lower()
    score = 10  # Base score for any content

    # Hiring/opportunity signals (+30 max)
    hiring_words = ['hiring', 'hire', 'job', 'position', 'opportunity', 'opening',
                    'looking for', 'seeking', 'need', 'wanted', 'join our team']
    hiring_matches = sum(1 for w in hiring_words if w in text_lower)
    score += min(30, hiring_matches * 10)

    # Budget/compensation signals (+20 max)
    budget_words = ['$', 'budget', 'salary', 'pay', 'rate', 'compensation',
                    'equity', 'per hour', '/hr', 'k/year']
    budget_matches = sum(1 for w in budget_words if w in text_lower)
    score += min(20, budget_matches * 10)

    # Urgency signals (+15 max)
    urgency_words = ['urgent', 'asap', 'immediately', 'right away', 'fast',
                     'quick turnaround', 'deadline']
    urgency_matches = sum(1 for w in urgency_words if w in text_lower)
    score += min(15, urgency_matches * 15)

    # Contact information (+10)
    if re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text_lower):
        score += 10
    if any(w in text_lower for w in ['dm me', 'contact', 'reach out', 'email me',
                                       'message me', 'apply']):
        score += 5

    # Project/Technical signals (+15 max)
    tech_words = ['developer', 'engineer', 'designer', 'architect', 'devops',
                  'frontend', 'backend', 'fullstack', 'mobile', 'web',
                  'python', 'javascript', 'react', 'node', 'api', 'saas', 'mvp']
    tech_matches = sum(1 for w in tech_words if w in text_lower)
    score += min(15, tech_matches * 5)

    # Content length bonus (longer = more detail = better lead)
    if len(text) > 500:
        score += 5
    if len(text) > 1000:
        score += 5

    return min(100, score)
