from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from ... import models, schemas
from ...database import get_db
from ...services.lrr_service import lrr_service
from ...services.lrr_scheduler import lrr_scheduler
from datetime import datetime

router = APIRouter()


@router.get("/refresh", response_model=List[schemas.RegulatoryUpdateResponse])
def refresh_updates(db: Session = Depends(get_db)):
    """Fetches new updates, processes obligations, and saves to DB."""
    updates = lrr_service.fetch_latest_updates()
    processed_updates = lrr_service.map_to_policies(updates)

    db_updates = []
    for u in processed_updates:
        # Check for duplicates by link
        existing = db.query(models.RegulatoryUpdate).filter(
            models.RegulatoryUpdate.link == u.get('link', '')
        ).first()
        if existing:
            continue

        pub_date = u.get('published_date', datetime.now().isoformat())
        if isinstance(pub_date, str):
            try:
                pub_date = datetime.fromisoformat(pub_date)
            except ValueError:
                pub_date = datetime.now()

        db_update = models.RegulatoryUpdate(
            title=u['title'],
            source=u.get('source', 'RBI'),
            published_date=pub_date,
            summary=u['summary'],
            link=u.get('link', ''),
            category=u.get('category', 'General'),
            obligations=u.get('obligations'),
            is_processed=True,
        )
        db.add(db_update)
        db_updates.append(db_update)

    db.commit()
    for du in db_updates:
        db.refresh(du)

    return db_updates


@router.get("/", response_model=List[schemas.RegulatoryUpdateResponse])
def get_updates(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """List regulatory updates from DB."""
    updates = db.query(models.RegulatoryUpdate).order_by(
        models.RegulatoryUpdate.fetched_at.desc()
    ).offset(skip).limit(limit).all()
    return updates


# --- Monitoring Control ---

@router.post("/start-monitoring")
def start_monitoring():
    """Start the background LRR monitoring scheduler."""
    lrr_scheduler.start_monitoring()
    return {
        "status": "started",
        "message": f"Monitoring started. Polling every {lrr_scheduler.get_status()['poll_interval_hours']} hours.",
    }


@router.post("/stop-monitoring")
def stop_monitoring():
    """Stop the background LRR monitoring scheduler."""
    lrr_scheduler.stop_monitoring()
    return {"status": "stopped", "message": "Monitoring stopped."}


@router.get("/monitoring-status", response_model=schemas.MonitoringStatusResponse)
def get_monitoring_status():
    """Get current monitoring status."""
    status = lrr_scheduler.get_status()
    return schemas.MonitoringStatusResponse(
        is_running=status["is_running"],
        last_run_at=datetime.fromisoformat(status["last_run_at"]) if status.get("last_run_at") else None,
        last_run_status=status.get("last_run_status"),
        updates_found_last_run=status.get("updates_found_last_run", 0),
        next_run_at=datetime.fromisoformat(status["next_run_at"]) if status.get("next_run_at") else None,
        poll_interval_hours=status.get("poll_interval_hours", 6),
    )


# --- Obligations ---

@router.get("/obligations", response_model=List[schemas.ObligationResponse])
def get_obligations(
    status: str = None,
    severity: str = None,
    category: str = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """List obligations with optional filters."""
    query = db.query(models.Obligation)

    if status:
        query = query.filter(models.Obligation.status == status)
    if severity:
        query = query.filter(models.Obligation.severity == severity)
    if category:
        query = query.filter(models.Obligation.category.ilike(f"%{category}%"))

    obligations = query.order_by(
        models.Obligation.created_at.desc()
    ).offset(skip).limit(limit).all()
    return obligations


@router.put("/obligations/{obligation_id}/status")
def update_obligation_status(
    obligation_id: int,
    status_update: schemas.ObligationStatusUpdate,
    db: Session = Depends(get_db),
):
    """Update an obligation's status."""
    obligation = db.query(models.Obligation).filter(
        models.Obligation.id == obligation_id
    ).first()

    if not obligation:
        raise HTTPException(status_code=404, detail="Obligation not found")

    obligation.status = status_update.status.value
    db.commit()
    db.refresh(obligation)
    return {"message": f"Obligation {obligation_id} updated to '{status_update.status.value}'"}


@router.get("/obligations/{obligation_id}/impact", response_model=List[schemas.ImpactAssessmentResponse])
def get_obligation_impact(obligation_id: int, db: Session = Depends(get_db)):
    """Get impact assessments for a specific obligation."""
    assessments = db.query(models.ImpactAssessment).filter(
        models.ImpactAssessment.obligation_id == obligation_id
    ).all()

    if not assessments:
        raise HTTPException(status_code=404, detail="No impact assessments found for this obligation")

    return assessments


# --- Full LRR Cycle ---

@router.post("/run-full-cycle", response_model=schemas.LRRCycleResponse)
async def run_full_cycle(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Trigger a complete LRR cycle: fetch → extract → assess → report.
    Runs synchronously for immediate feedback.
    """
    from ...services.lrr_scheduler import lrr_scheduler
    import asyncio

    # Create a monitoring run record
    run = models.MonitoringRun(status="running", source="rbi")
    db.add(run)
    db.commit()
    db.refresh(run)

    errors = []
    updates_found = 0
    obligations_extracted = 0
    impact_count = 0
    report_id = None

    try:
        # Step 1: Fetch updates
        new_updates = lrr_service.fetch_latest_updates()

        # Step 2: Detect changes
        existing_links = set()
        existing_records = db.query(models.RegulatoryUpdate.link).all()
        existing_links = {r.link for r in existing_records if r.link}
        genuinely_new = lrr_service.detect_changes(new_updates, existing_links)
        updates_found = len(genuinely_new)

        # Step 3: Process each new update
        for update in genuinely_new:
            try:
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
                    is_processed=False,
                )
                db.add(db_update)
                db.commit()
                db.refresh(db_update)

                # Extract obligations
                text = update.get("summary", "")
                obligations = lrr_service.extract_obligations(text)

                for ob in obligations:
                    db_ob = models.Obligation(
                        regulatory_update_id=db_update.id,
                        text=ob["text"][:2000],
                        deadline=ob.get("deadline"),
                        severity=ob.get("severity", "medium"),
                        category=ob.get("category"),
                        affected_entity=ob.get("affected_entity"),
                        status="pending",
                    )
                    db.add(db_ob)
                    obligations_extracted += 1

                db.commit()

                # Assess impact
                if obligations:
                    assessments = lrr_service.assess_impact(obligations)
                    recent_obs = db.query(models.Obligation).filter(
                        models.Obligation.regulatory_update_id == db_update.id
                    ).all()

                    for i, assessment in enumerate(assessments):
                        if i < len(recent_obs):
                            db_impact = models.ImpactAssessment(
                                obligation_id=recent_obs[i].id,
                                affected_policies=assessment.get("affected_policies"),
                                risk_level=assessment.get("risk_level", "medium"),
                                action_items=assessment.get("action_items"),
                                estimated_effort=assessment.get("estimated_effort"),
                                affected_departments=assessment.get("affected_departments"),
                            )
                            db.add(db_impact)
                            impact_count += 1

                db_update.is_processed = True
                db.commit()

            except Exception as e:
                errors.append(str(e))
                db.rollback()

        # Step 4: Generate report
        if updates_found > 0:
            report = models.ComplianceReport(
                title=f"LRR Full Cycle Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                report_type="full_cycle",
                content={
                    "updates_found": updates_found,
                    "obligations_extracted": obligations_extracted,
                    "impact_assessments": impact_count,
                },
                summary=f"Found {updates_found} new updates, {obligations_extracted} obligations, {impact_count} impact assessments.",
                total_obligations=obligations_extracted,
                critical_findings=db.query(models.Obligation).filter(
                    models.Obligation.severity.in_(["critical", "high"])
                ).count(),
            )
            db.add(report)
            db.commit()
            db.refresh(report)
            report_id = report.id

        # Update monitoring run
        run.completed_at = datetime.now()
        run.status = "completed" if not errors else "partial"
        run.updates_found = updates_found
        run.obligations_extracted = obligations_extracted
        run.errors = errors if errors else None
        db.commit()

    except Exception as e:
        run.completed_at = datetime.now()
        run.status = "failed"
        run.errors = [str(e)]
        db.commit()
        errors.append(str(e))

    return schemas.LRRCycleResponse(
        monitoring_run_id=run.id,
        updates_found=updates_found,
        obligations_extracted=obligations_extracted,
        impact_assessments_created=impact_count,
        report_id=report_id,
        summary=f"Cycle completed: {updates_found} updates, {obligations_extracted} obligations, {impact_count} impacts.",
        errors=errors,
    )


# --- Reports ---

@router.get("/reports", response_model=List[schemas.ComplianceReportResponse])
def get_reports(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    """List generated compliance reports."""
    reports = db.query(models.ComplianceReport).order_by(
        models.ComplianceReport.generated_at.desc()
    ).offset(skip).limit(limit).all()
    return reports


# --- Dashboard Stats ---

@router.get("/dashboard-stats", response_model=schemas.LRRDashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get aggregated statistics for the LRR dashboard."""
    total_updates = db.query(models.RegulatoryUpdate).count()
    total_obligations = db.query(models.Obligation).count()
    pending = db.query(models.Obligation).filter(models.Obligation.status == "pending").count()
    critical = db.query(models.Obligation).filter(models.Obligation.severity == "critical").count()
    high = db.query(models.Obligation).filter(models.Obligation.severity == "high").count()
    total_impacts = db.query(models.ImpactAssessment).count()
    total_reports = db.query(models.ComplianceReport).count()

    last_run = db.query(models.MonitoringRun).order_by(
        models.MonitoringRun.started_at.desc()
    ).first()

    return schemas.LRRDashboardStats(
        total_regulatory_updates=total_updates,
        total_obligations=total_obligations,
        pending_obligations=pending,
        critical_obligations=critical,
        high_risk_obligations=high,
        total_impact_assessments=total_impacts,
        total_reports=total_reports,
        monitoring_active=lrr_scheduler.is_running,
        last_monitoring_run=last_run.started_at if last_run else None,
    )


# --- Monitoring Runs ---

@router.get("/monitoring-runs", response_model=List[schemas.MonitoringRunResponse])
def get_monitoring_runs(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    """List monitoring run history."""
    runs = db.query(models.MonitoringRun).order_by(
        models.MonitoringRun.started_at.desc()
    ).offset(skip).limit(limit).all()
    return runs
