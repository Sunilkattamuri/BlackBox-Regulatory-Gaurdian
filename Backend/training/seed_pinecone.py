"""
Seeding Script for Pinecone.
Generates embeddings and uploads the default set of internal policies to the Pinecone index.
"""

import os
import sys
import logging

# Ensure Backend/ is in path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("seed_pinecone")

from app.services.vector_store_service import vector_store_service
from app.services.mcp_tools.policy_tools import INTERNAL_POLICIES


def main():
    logger.info("=" * 60)
    logger.info("🌲 Pinecone Vector DB Seeding Script 🌲")
    logger.info("=" * 60)

    # 1. Verify Pinecone Configuration
    if not vector_store_service.is_configured():
        logger.error(
            "Pinecone is NOT configured in your .env file.\n"
            "Please open 'Backend/.env' and fill in your PINECONE_API_KEY.\n"
            "Aborting seeding."
        )
        sys.exit(1)

    logger.info("Pinecone configuration detected.")

    # 2. Prepare policies to seed
    policies_list = []
    for policy_id, p in INTERNAL_POLICIES.items():
        policies_list.append({
            "id": p["id"],
            "name": p["name"],
            "version": p["version"],
            "department": p["department"],
            "categories": p["categories"],
            "summary": p["summary"],
            "last_updated": p["last_updated"],
            "regulatory_references": p["regulatory_references"]
        })

    logger.info(f"Loaded {len(policies_list)} default policies to index.")

    # 3. Seed into Pinecone
    logger.info("Starting indexing and upserting vectors. This may take a minute...")
    success = vector_store_service.upsert_policies(policies_list)

    if success:
        logger.info("=" * 60)
        logger.info("✅ Pinecone Vector DB seeded successfully!")
        logger.info(f"Indexed {len(policies_list)} internal policies in '{vector_store_service.get_pinecone_index().name}' index.")
        logger.info("=" * 60)
    else:
        logger.error("❌ Seeding failed. Please check the logs above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
