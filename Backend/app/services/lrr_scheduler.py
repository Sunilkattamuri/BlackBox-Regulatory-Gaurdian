"""
LRR Background Scheduler.
Runs periodic regulatory monitoring using APScheduler within the FastAPI process.
"""

import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..config import settings

logger = logging.getLogger(__name__)


class LRRScheduler:
    """
    Background scheduler for automated regulatory monitoring.
    Periodically polls RBI sources, extracts obligations, and stores results.
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.last_run_at: Optional[datetime] = None
        self.last_run_status: Optional[str] = None
        self.updates_found_last_run: int = 0

    def start_monitoring(self):
        """Start the background monitoring job."""
        if self.is_running:
            logger.warning("LRR monitoring is already running")
            return

        interval_hours = settings.LRR_POLL_INTERVAL_HOURS

        self.scheduler.add_job(
            self._run_monitoring_cycle,
            trigger=IntervalTrigger(hours=interval_hours),
            id="lrr_monitoring",
            name="LRR Regulatory Monitoring",
            replace_existing=True,
            next_run_time=None,  # Don't run immediately on startup
        )

        if not self.scheduler.running:
            self.scheduler.start()

        self.is_running = True
        logger.info(
            f"LRR monitoring started. Polling every {interval_hours} hour(s). "
            f"Next run at: {self._get_next_run_time()}"
        )

    def stop_monitoring(self):
        """Stop the background monitoring job."""
        if not self.is_running:
            logger.warning("LRR monitoring is not running")
            return

        try:
            self.scheduler.remove_job("lrr_monitoring")
        except Exception:
            pass

        self.is_running = False
        logger.info("LRR monitoring stopped")

    def trigger_immediate_run(self):
        """Trigger an immediate monitoring run (outside the regular schedule)."""
        import asyncio
        asyncio.create_task(self._run_monitoring_cycle())

    async def _run_monitoring_cycle(self):
        """
        Execute a complete LRR monitoring cycle:
        1. Fetch latest updates from RBI
        2. Detect new/changed regulations
        3. Extract obligations from new updates
        4. Assess impact on internal policies
        5. Store results in database
        6. Generate compliance report if critical findings
        """
        from ..database import SessionLocal
        from .. import models
        from .lrr_service import lrr_service

        logger.info("LRR Monitoring Cycle: Starting...")
        run_start = datetime.now()

        db = SessionLocal()
        monitoring_run = models.MonitoringRun(
            started_at=run_start,
            status="running",
            source="rbi",
        )
        db.add(monitoring_run)
        db.commit()
        db.refresh(monitoring_run)

        errors = []
        updates_found = 0
        obligations_extracted = 0

        try:
            # Step 1: Fetch latest updates
            logger.info("LRR Cycle Step 1: Fetching updates...")
            new_updates = lrr_service.fetch_latest_updates()

            # Step 2: Detect changes against existing DB entries
            existing_links = set()
            existing_records = db.query(models.RegulatoryUpdate.link).all()
            existing_links = {r.link for r in existing_records if r.link}

            genuinely_new = lrr_service.detect_changes(new_updates, existing_links)
            updates_found = len(genuinely_new)
            logger.info(f"LRR Cycle Step 2: {updates_found} new update(s) detected")

            # Step 3: Process each new update
            for update in genuinely_new:
                try:
                    # Store the regulatory update
                    pub_date = update.get("published_date", datetime.now().isoformat())
                    if isinstance(pub_date, str):
                        try:
                            pub_date = datetime.fromisoformat(pub_date)
                        except ValueError:
                            pub_date = datetime.now()

                    db_update = models.RegulatoryUpdate(
                        title=update.get("title", "Untitled"),
                        source=update.get("source", "RBI"),
                        published_date=pub_date,
                        summary=update.get("summary", ""),
                        link=update.get("link", ""),
                        category=update.get("category", "General"),
                        full_text=update.get("full_text"),
                        is_processed=False,
                    )
                    db.add(db_update)
                    db.commit()
                    db.refresh(db_update)

                    # Step 3a: Try to get full text for better obligation extraction
                    full_text = update.get("summary", "")
                    if update.get("link"):
                        scraped_content = lrr_service.scrape_circular_content(update["link"])
                        if scraped_content:
                            full_text = scraped_content
                            db_update.full_text = full_text[:10000]  # Limit storage

                    # Step 3b: Extract obligations
                    obligations = lrr_service.extract_obligations(full_text)
                    logger.info(
                        f"LRR Cycle Step 3: Extracted {len(obligations)} obligation(s) "
                        f"from '{update.get('title', '')[:50]}...'"
                    )

                    for ob in obligations:
                        db_obligation = models.Obligation(
                            regulatory_update_id=db_update.id,
                            text=ob["text"][:2000],
                            deadline=ob.get("deadline"),
                            severity=ob.get("severity", "medium"),
                            category=ob.get("category"),
                            affected_entity=ob.get("affected_entity"),
                            status="pending",
                        )
                        db.add(db_obligation)
                        obligations_extracted += 1

                    # Step 3c: Assess impact
                    if obligations:
                        assessments = lrr_service.assess_impact(obligations)
                        db.commit()

                        # Store impact assessments
                        # Get the obligations we just created
                        recent_obligations = (
                            db.query(models.Obligation)
                            .filter(models.Obligation.regulatory_update_id == db_update.id)
                            .all()
                        )

                        for i, assessment in enumerate(assessments):
                            if i < len(recent_obligations):
                                db_impact = models.ImpactAssessment(
                                    obligation_id=recent_obligations[i].id,
                                    affected_policies=assessment.get("affected_policies"),
                                    risk_level=assessment.get("risk_level", "medium"),
                                    action_items=assessment.get("action_items"),
                                    estimated_effort=assessment.get("estimated_effort"),
                                    affected_departments=assessment.get("affected_departments"),
                                    assessment_notes=f"Auto-assessed from: {update.get('title', '')[:100]}",
                                )
                                db.add(db_impact)

                    # Mark update as processed
                    db_update.is_processed = True
                    db_update.obligations = [
                        {"text": ob["text"][:200], "severity": ob.get("severity")}
                        for ob in obligations
                    ]
                    db.commit()

                except Exception as e:
                    logger.error(f"Error processing update '{update.get('title', '')[:50]}': {e}")
                    errors.append(str(e))
                    db.rollback()

            # Step 4: Generate compliance report if critical findings
            critical_count = (
                db.query(models.Obligation)
                .filter(models.Obligation.severity.in_(["critical", "high"]))
                .filter(models.Obligation.status == "pending")
                .count()
            )

            if critical_count > 0 and updates_found > 0:
                report = models.ComplianceReport(
                    title=f"LRR Monitoring Report - {run_start.strftime('%Y-%m-%d %H:%M')}",
                    report_type="full_cycle",
                    content={
                        "run_timestamp": run_start.isoformat(),
                        "updates_found": updates_found,
                        "obligations_extracted": obligations_extracted,
                        "critical_findings": critical_count,
                        "summary": (
                            f"Monitoring cycle completed. Found {updates_found} new regulatory update(s), "
                            f"extracted {obligations_extracted} obligation(s), "
                            f"of which {critical_count} are critical/high severity."
                        ),
                    },
                    summary=(
                        f"Found {updates_found} new updates with {obligations_extracted} obligations. "
                        f"{critical_count} critical/high severity items require immediate attention."
                    ),
                    total_obligations=obligations_extracted,
                    critical_findings=critical_count,
                )
                db.add(report)

            # Update monitoring run record
            monitoring_run.completed_at = datetime.now()
            monitoring_run.status = "completed" if not errors else "partial"
            monitoring_run.updates_found = updates_found
            monitoring_run.obligations_extracted = obligations_extracted
            monitoring_run.errors = errors if errors else None
            db.commit()

            self.last_run_at = run_start
            self.last_run_status = monitoring_run.status
            self.updates_found_last_run = updates_found

            logger.info(
                f"LRR Monitoring Cycle: Completed. "
                f"Updates: {updates_found}, Obligations: {obligations_extracted}, "
                f"Errors: {len(errors)}"
            )

        except Exception as e:
            logger.error(f"LRR Monitoring Cycle failed: {e}")
            monitoring_run.completed_at = datetime.now()
            monitoring_run.status = "failed"
            monitoring_run.errors = [str(e)]
            db.commit()
            self.last_run_status = "failed"

        finally:
            db.close()

    def get_status(self) -> dict:
        """Get current monitoring status."""
        next_run = self._get_next_run_time()
        return {
            "is_running": self.is_running,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_run_status": self.last_run_status,
            "updates_found_last_run": self.updates_found_last_run,
            "next_run_at": next_run,
            "poll_interval_hours": settings.LRR_POLL_INTERVAL_HOURS,
        }

    def _get_next_run_time(self) -> Optional[str]:
        """Get the next scheduled run time."""
        try:
            job = self.scheduler.get_job("lrr_monitoring")
            if job and job.next_run_time:
                return job.next_run_time.isoformat()
        except Exception:
            pass
        return None


# Singleton instance
lrr_scheduler = LRRScheduler()
