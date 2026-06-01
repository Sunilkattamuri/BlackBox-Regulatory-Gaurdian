"""
MCP Tools for Regulatory Data Access.
Provides tools for fetching, scraping, and searching RBI regulatory data.
"""

import logging
from typing import Optional
from fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_regulatory_tools(mcp: FastMCP):
    """Register all regulatory data tools on the MCP server."""

    @mcp.tool()
    def get_regulatory_updates() -> str:
        """
        Fetch the latest regulatory updates and guidelines from RBI.
        Returns formatted summary of recent notifications, circulars, and master directions.
        """
        try:
            from ..lrr_service import lrr_service
            updates = lrr_service.fetch_latest_updates()

            if not updates:
                return "No recent regulatory updates found."

            formatted = []
            for i, u in enumerate(updates, 1):
                entry = (
                    f"--- Update {i} ---\n"
                    f"Title: {u.get('title', 'N/A')}\n"
                    f"Source: {u.get('source', 'RBI')}\n"
                    f"Category: {u.get('category', 'General')}\n"
                    f"Date: {u.get('published_date', 'N/A')}\n"
                    f"Summary: {u.get('summary', 'N/A')}\n"
                    f"Link: {u.get('link', 'N/A')}"
                )
                formatted.append(entry)

            return f"Found {len(updates)} regulatory update(s):\n\n" + "\n\n".join(formatted)

        except Exception as e:
            logger.error(f"Error fetching regulatory updates: {e}")
            return f"Error fetching regulatory updates: {str(e)}"

    @mcp.tool()
    def scrape_rbi_circular(url: str) -> str:
        """
        Fetch and parse the full text of a specific RBI circular or notification page.
        Provide the full URL of the RBI circular to scrape.
        """
        try:
            from ..lrr_service import lrr_service
            content = lrr_service.scrape_circular_content(url)

            if content:
                # Truncate if very long
                if len(content) > 5000:
                    return content[:5000] + "\n\n[... Content truncated. Full text available in the system.]"
                return content
            return "Could not retrieve content from the specified URL."

        except Exception as e:
            logger.error(f"Error scraping circular: {e}")
            return f"Error scraping circular: {str(e)}"

    @mcp.tool()
    def search_rbi_archive(
        query: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> str:
        """
        Search the RBI notification archive for circulars matching a query.
        Optionally filter by date range (format: YYYY-MM-DD).

        Args:
            query: Search terms (e.g., 'digital lending', 'capital adequacy', 'KYC norms').
            date_from: Optional start date for filtering (YYYY-MM-DD).
            date_to: Optional end date for filtering (YYYY-MM-DD).
        """
        try:
            from ..lrr_service import lrr_service
            results = lrr_service.search_updates(query, date_from, date_to)

            if not results:
                return f"No regulatory updates found matching '{query}'."

            formatted = []
            for i, r in enumerate(results, 1):
                entry = (
                    f"{i}. {r.get('title', 'N/A')}\n"
                    f"   Date: {r.get('published_date', 'N/A')}\n"
                    f"   Link: {r.get('link', 'N/A')}"
                )
                formatted.append(entry)

            return f"Found {len(results)} result(s) for '{query}':\n\n" + "\n".join(formatted)

        except Exception as e:
            logger.error(f"Error searching archive: {e}")
            return f"Error searching archive: {str(e)}"

    @mcp.tool()
    def get_regulatory_timeline(category: str) -> str:
        """
        Get a chronological timeline of regulatory changes for a specific category.

        Args:
            category: Regulation category (e.g., 'Digital Lending', 'KYC', 'Capital Adequacy',
                      'Investment Portfolio', 'Priority Sector Lending').
        """
        try:
            from ..lrr_service import lrr_service
            updates = lrr_service.search_updates(category)

            if not updates:
                return f"No regulatory timeline found for category '{category}'."

            # Sort by date
            sorted_updates = sorted(
                updates,
                key=lambda x: x.get("published_date", ""),
                reverse=True,
            )

            timeline = [f"📋 Regulatory Timeline: {category}\n{'=' * 50}"]
            for u in sorted_updates[:20]:  # Last 20 entries
                timeline.append(
                    f"📅 {u.get('published_date', 'N/A')}\n"
                    f"   📄 {u.get('title', 'N/A')}\n"
                    f"   🔗 {u.get('link', 'N/A')}"
                )

            return "\n\n".join(timeline)

        except Exception as e:
            logger.error(f"Error getting timeline: {e}")
            return f"Error getting regulatory timeline: {str(e)}"
