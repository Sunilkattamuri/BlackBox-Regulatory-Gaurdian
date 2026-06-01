"""
LRR (Legal & Regulatory Requirements) Service.
Handles regulatory monitoring with real RBI scraping, RSS parsing,
obligation extraction, and impact assessment.
"""

import re
import logging
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional

import feedparser
import httpx
from bs4 import BeautifulSoup

from ..config import settings

logger = logging.getLogger(__name__)


class RBIScraper:
    """Scrapes RBI website for regulatory notifications and circulars."""

    def __init__(self):
        self.headers = {
            "User-Agent": settings.SCRAPER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        self.timeout = settings.SCRAPER_TIMEOUT_SECONDS

    def scrape_circulars(self, max_items: int = 20) -> List[Dict[str, Any]]:
        """
        Scrape the RBI circular index page for recent circulars.
        Falls back gracefully if the page structure changes or request fails.
        """
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(settings.RBI_CIRCULAR_URL, headers=self.headers)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            circulars = []

            # RBI typically uses table layouts for circular listings
            # Try multiple selectors to be resilient to layout changes
            rows = (
                soup.select("table.tablebg tr") or
                soup.select("table tr") or
                soup.select(".tableContent tr")
            )

            for row in rows[:max_items]:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    # Try to extract link and title
                    link_tag = row.find("a")
                    if link_tag:
                        title = link_tag.get_text(strip=True)
                        href = link_tag.get("href", "")

                        # Make absolute URL
                        if href and not href.startswith("http"):
                            href = f"https://www.rbi.org.in{href}" if href.startswith("/") else f"https://www.rbi.org.in/Scripts/{href}"

                        # Try to extract date from cells
                        date_text = ""
                        for cell in cells:
                            cell_text = cell.get_text(strip=True)
                            # Look for date patterns
                            date_match = re.search(
                                r"\d{1,2}[-/]\d{1,2}[-/]\d{4}|\w+\s+\d{1,2},?\s+\d{4}",
                                cell_text
                            )
                            if date_match:
                                date_text = date_match.group()
                                break

                        if title and len(title) > 10:
                            circulars.append({
                                "title": title,
                                "link": href,
                                "published_date": date_text or datetime.now().isoformat(),
                                "source": "RBI",
                                "category": self._categorize_circular(title),
                                "summary": title,  # Summary is initially the title; full text fetched later
                            })

            logger.info(f"RBI Scraper: Found {len(circulars)} circulars")
            return circulars

        except httpx.HTTPError as e:
            logger.error(f"HTTP error scraping RBI circulars: {e}")
            return []
        except Exception as e:
            logger.error(f"Error scraping RBI circulars: {e}")
            return []

    def scrape_circular_content(self, url: str) -> Optional[str]:
        """Scrape the full text content of a specific RBI circular page."""
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url, headers=self.headers)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Try to find the main content area
            content_div = (
                soup.find("div", {"id": "divContent"}) or
                soup.find("div", {"class": "content"}) or
                soup.find("div", {"id": "frmMain"}) or
                soup.find("td", {"class": "tableContent"})
            )

            if content_div:
                # Clean up the text
                text = content_div.get_text(separator="\n", strip=True)
                # Remove excessive whitespace
                text = re.sub(r"\n{3,}", "\n\n", text)
                return text

            # Fallback: get all paragraph text
            paragraphs = soup.find_all("p")
            if paragraphs:
                return "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

            return None

        except Exception as e:
            logger.error(f"Error scraping circular content from {url}: {e}")
            return None

    def _categorize_circular(self, title: str) -> str:
        """Categorize a circular based on its title."""
        title_lower = title.lower()
        categories = {
            "Master Direction": ["master direction"],
            "Master Circular": ["master circular"],
            "Notification": ["notification"],
            "Circular": ["circular"],
            "Guidelines": ["guidelines", "guideline"],
            "Press Release": ["press release"],
            "Policy Statement": ["statement on", "policy"],
        }
        for category, keywords in categories.items():
            if any(kw in title_lower for kw in keywords):
                return category
        return "General"


class RSSFeedMonitor:
    """Monitors RBI RSS feeds for structured regulatory updates."""

    def __init__(self):
        self.feed_url = settings.RBI_RSS_URL

    def fetch_feed(self) -> List[Dict[str, Any]]:
        """Parse the RBI RSS feed for recent entries."""
        try:
            feed = feedparser.parse(self.feed_url)

            if feed.bozo and not feed.entries:
                logger.warning(f"RSS feed parsing error: {feed.bozo_exception}")
                return []

            entries = []
            for entry in feed.entries[:20]:
                published = entry.get("published", "")
                try:
                    pub_date = datetime(*entry.published_parsed[:6]).isoformat() if hasattr(entry, "published_parsed") and entry.published_parsed else datetime.now().isoformat()
                except Exception:
                    pub_date = datetime.now().isoformat()

                entries.append({
                    "title": entry.get("title", "No Title"),
                    "summary": entry.get("summary", entry.get("description", "")),
                    "link": entry.get("link", ""),
                    "published_date": pub_date,
                    "source": "RBI",
                    "category": "RSS Feed",
                })

            logger.info(f"RSS Monitor: Fetched {len(entries)} entries from feed")
            return entries

        except Exception as e:
            logger.error(f"Error fetching RSS feed: {e}")
            return []


class LRRService:
    """
    Orchestrates regulatory monitoring: scraping, RSS, obligation extraction,
    change detection, and policy mapping.
    """

    def __init__(self):
        self.scraper = RBIScraper()
        self.rss_monitor = RSSFeedMonitor()
        self._cached_updates: List[Dict[str, Any]] = []
        self._last_fetch: Optional[datetime] = None

        # Fallback mock data for when scraping fails
        self._mock_rbi_feed = [
            {
                "title": "Master Direction - Classification, Valuation and Operation of Investment Portfolio of Commercial Banks (Directions), 2023",
                "summary": "Updated guidelines on how commercial banks should classify and value their investment portfolios. Banks are required to classify their entire investment portfolio into three categories: Held to Maturity (HTM), Available for Sale (AFS), and Fair Value through Profit or Loss (FVTPL). Monthly mark-to-market valuation is mandatory for AFS and FVTPL categories.",
                "link": "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12534",
                "published_date": datetime.now().isoformat(),
                "source": "RBI",
                "category": "Master Direction",
            },
            {
                "title": "Guidelines on Default Loss Guarantee (DLG) in Digital Lending",
                "summary": "Regulatory framework for Default Loss Guarantee arrangements in digital lending. DLG shall not exceed 5% of the amount of that loan portfolio. The DLG arrangement must be backed by a cash deposit or bank guarantee in favour of the RE. All regulated entities shall ensure that digital lending apps recommended by them are registered on their website.",
                "link": "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12527",
                "published_date": datetime.now().isoformat(),
                "source": "RBI",
                "category": "Guidelines",
            },
            {
                "title": "Framework for Recognition of Self-Regulatory Organisations (SROs) for FinTech Sector",
                "summary": "RBI introduces a framework for establishing Self-Regulatory Organisations in the FinTech sector. FinTech entities shall comply with the code of conduct formulated by the SRO-FT. The SRO-FT must have a minimum net worth of Rs 2 crore. All FinTech entities operating in areas covered by the SRO-FT shall mandatorily become members within 6 months.",
                "link": "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12610",
                "published_date": datetime.now().isoformat(),
                "source": "RBI",
                "category": "Framework",
            },
            {
                "title": "Revised Regulatory Framework for Urban Co-operative Banks (UCBs)",
                "summary": "Comprehensive revision of the regulatory framework applicable to Urban Co-operative Banks. UCBs are required to maintain CRAR of 9% by March 2026. Tier-1 UCBs must limit exposure to a single borrower to 15% of Tier 1 capital. Enhanced reporting requirements with quarterly submission of financial data to RBI.",
                "link": "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12600",
                "published_date": datetime.now().isoformat(),
                "source": "RBI",
                "category": "Master Direction",
            },
        ]

    def fetch_latest_updates(self) -> List[Dict[str, Any]]:
        """
        Fetch latest regulatory updates. Tries RSS first, then scraping,
        then falls back to mock data.
        """
        updates = []

        # 1. Try RSS feed first (most structured)
        rss_updates = self.rss_monitor.fetch_feed()
        if rss_updates:
            updates.extend(rss_updates)
            logger.info(f"LRR: Got {len(rss_updates)} updates from RSS feed")

        # 2. Try web scraping for additional circulars
        scraped = self.scraper.scrape_circulars()
        if scraped:
            # Deduplicate against RSS results
            existing_links = {u["link"] for u in updates}
            new_scraped = [s for s in scraped if s["link"] not in existing_links]
            updates.extend(new_scraped)
            logger.info(f"LRR: Got {len(new_scraped)} additional updates from scraping")

        # 3. Fallback to mock data if both sources fail
        if not updates:
            logger.warning("LRR: All sources failed, using mock data")
            updates = self._mock_rbi_feed.copy()

        self._cached_updates = updates
        self._last_fetch = datetime.now()

        return updates

    def detect_changes(
        self,
        new_updates: List[Dict[str, Any]],
        existing_links: set,
    ) -> List[Dict[str, Any]]:
        """Identify genuinely new updates by comparing against existing data."""
        new_items = []
        for update in new_updates:
            link = update.get("link", "")
            # Use link as unique identifier
            if link and link not in existing_links:
                # Also check by title hash as backup
                title_hash = hashlib.md5(update.get("title", "").encode()).hexdigest()
                update["title_hash"] = title_hash
                new_items.append(update)

        logger.info(f"LRR: Detected {len(new_items)} new update(s) out of {len(new_updates)}")
        return new_items

    def extract_obligations(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract actionable obligations from regulatory text using NLP rules.
        Identifies mandatory requirements, deadlines, and affected entities.
        """
        if not text:
            return []

        obligation_indicators = [
            "shall", "must", "required to", "obligated to",
            "mandatory", "is required", "are required",
            "shall ensure", "shall comply", "shall submit",
            "shall be liable", "penalty for non-compliance",
        ]

        sentences = re.split(r'[.!?]+', text)
        obligations = []

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:
                continue

            sentence_lower = sentence.lower()

            for indicator in obligation_indicators:
                if indicator in sentence_lower:
                    # Determine severity
                    severity = "medium"
                    if any(w in sentence_lower for w in ["penalty", "non-compliance", "liable", "revoke", "cancel"]):
                        severity = "critical"
                    elif any(w in sentence_lower for w in ["shall ensure", "mandatory", "must"]):
                        severity = "high"
                    elif any(w in sentence_lower for w in ["may", "should consider", "recommended"]):
                        severity = "low"

                    # Extract deadline
                    deadline = None
                    deadline_patterns = [
                        r"within\s+(\d+\s+(?:days?|months?|weeks?|years?))",
                        r"by\s+((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})",
                        r"not\s+later\s+than\s+([\w\s,]+\d{4})",
                        r"effective\s+from\s+([\w\s,]+\d{4})",
                        r"before\s+(March|June|September|December)\s+\d{1,2},?\s+\d{4}",
                    ]
                    for dp in deadline_patterns:
                        dm = re.search(dp, sentence, re.IGNORECASE)
                        if dm:
                            deadline = dm.group(1).strip()
                            break

                    # Determine affected entity
                    entity = None
                    entity_patterns = [
                        (r"((?:commercial|scheduled|cooperative)\s+banks?)", None),
                        (r"(NBFCs?)", None),
                        (r"((?:all\s+)?regulated\s+entities)", None),
                        (r"(payment\s+(?:banks?|aggregators?))", None),
                        (r"(housing\s+finance\s+companies)", None),
                        (r"(urban\s+co-?operative\s+banks?|UCBs?)", None),
                    ]
                    for ep, _ in entity_patterns:
                        em = re.search(ep, sentence, re.IGNORECASE)
                        if em:
                            entity = em.group(1).strip()
                            break

                    # Determine category
                    category = self._categorize_obligation(sentence)

                    obligations.append({
                        "text": sentence,
                        "severity": severity,
                        "deadline": deadline,
                        "affected_entity": entity,
                        "category": category,
                        "indicator": indicator,
                    })
                    break  # One indicator per sentence

        return obligations

    def assess_impact(self, obligations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Assess the impact of obligations on internal policies.
        Maps obligations to affected policies and determines risk level.
        """
        from .mcp_tools.policy_tools import CATEGORY_POLICY_MAP, INTERNAL_POLICIES

        assessments = []
        for obligation in obligations:
            category = obligation.get("category", "").lower()
            severity = obligation.get("severity", "medium")

            # Find affected policies
            affected_policy_ids = set()
            for cat, pids in CATEGORY_POLICY_MAP.items():
                if cat in category or category in cat:
                    affected_policy_ids.update(pids)

            # Also check obligation text for policy keywords
            ob_text_lower = obligation.get("text", "").lower()
            for cat, pids in CATEGORY_POLICY_MAP.items():
                if cat in ob_text_lower:
                    affected_policy_ids.update(pids)

            affected_policies = []
            affected_departments = set()
            for pid in affected_policy_ids:
                if pid in INTERNAL_POLICIES:
                    p = INTERNAL_POLICIES[pid]
                    affected_policies.append(p["name"])
                    affected_departments.add(p["department"])

            # Determine risk level based on severity and number of affected policies
            risk_level = severity
            if len(affected_policies) > 2 and severity in ("medium", "high"):
                risk_level = "critical"

            # Generate action items
            action_items = []
            if affected_policies:
                action_items.append({
                    "action": f"Review and update: {', '.join(affected_policies[:3])}",
                    "priority": severity,
                })
            action_items.append({
                "action": "Conduct gap analysis against current compliance status",
                "priority": "high" if severity in ("critical", "high") else "medium",
            })
            if obligation.get("deadline"):
                action_items.append({
                    "action": f"Set compliance deadline tracker: {obligation['deadline']}",
                    "priority": "high",
                })

            # Estimate effort
            effort_map = {
                "critical": "2-4 weeks",
                "high": "1-2 weeks",
                "medium": "3-5 days",
                "low": "1-2 days",
            }

            assessments.append({
                "obligation_text": obligation["text"][:200],
                "affected_policies": affected_policies,
                "affected_departments": list(affected_departments),
                "risk_level": risk_level,
                "action_items": action_items,
                "estimated_effort": effort_map.get(risk_level, "1 week"),
            })

        return assessments

    def map_to_policies(self, updates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Map fetched updates to internal policies with obligation extraction."""
        mapped_updates = []
        for update in updates:
            text = update.get("summary", "") + " " + update.get("full_text", "")
            obligations = self.extract_obligations(text)

            mapped_update = update.copy()
            mapped_update["obligations"] = [
                {
                    "policy": ob.get("category", "General Compliance"),
                    "impact": ob.get("severity", "medium").capitalize(),
                    "action": ob.get("text", "")[:150],
                    "deadline": ob.get("deadline"),
                }
                for ob in obligations
            ]

            # If no obligations found, add a generic one
            if not mapped_update["obligations"]:
                mapped_update["obligations"] = [{
                    "policy": "General Compliance",
                    "impact": "Low",
                    "action": "Review for general applicability.",
                }]

            mapped_updates.append(mapped_update)

        return mapped_updates

    def scrape_circular_content(self, url: str) -> Optional[str]:
        """Scrape the full text of a specific circular."""
        return self.scraper.scrape_circular_content(url)

    def search_updates(
        self,
        query: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search cached updates by query and optional date range."""
        if not self._cached_updates:
            self.fetch_latest_updates()

        query_lower = query.lower()
        results = []

        for update in self._cached_updates:
            title = update.get("title", "").lower()
            summary = update.get("summary", "").lower()
            category = update.get("category", "").lower()

            if query_lower in title or query_lower in summary or query_lower in category:
                results.append(update)

        return results

    def _categorize_obligation(self, text: str) -> str:
        """Categorize an obligation based on its text content."""
        text_lower = text.lower()
        categories = {
            "Capital Adequacy": ["capital", "crar", "tier 1", "tier 2", "rwa", "basel"],
            "KYC/AML": ["kyc", "aml", "customer due diligence", "identity", "pml"],
            "Digital Lending": ["digital lending", "fintech", "dlg", "digital loan"],
            "Investment": ["investment", "valuation", "trading book", "htM", "afs"],
            "Priority Sector": ["priority sector", "psl", "agriculture", "msme"],
            "Interest Rate": ["interest rate", "mclr", "eblr", "repo rate"],
            "Outsourcing": ["outsourcing", "third party", "vendor"],
            "Reporting": ["reporting", "submission", "returns", "filing"],
            "Risk Management": ["risk", "stress test", "exposure", "concentration"],
            "Governance": ["board", "governance", "audit", "committee"],
        }
        for category, keywords in categories.items():
            if any(kw in text_lower for kw in keywords):
                return category
        return "General Compliance"


# Singleton instance
lrr_service = LRRService()
