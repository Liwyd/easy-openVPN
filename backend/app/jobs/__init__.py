"""Background jobs — APScheduler tasks.

Auto-discovery pattern from Marzban: each .py file in this package
calls scheduler.add_job(...) at module level when imported.  The
scheduler is started by app/__init__.py at application startup.

Jobs are registered with:
- coalesce=True: if multiple runs were missed, only run once
- max_instances=1: prevent overlapping runs of the same job
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

# Module-level scheduler instance — imported by app/__init__.py
scheduler = BackgroundScheduler(
    coalesce=True,
    max_instances=1,
    job_defaults={
        "coalesce": True,
        "max_instances": 1,
    },
)


def register_jobs() -> None:
    """Register all background jobs with the scheduler.

    Called once at application startup.  Each job module is imported
    for its side-effect of adding jobs to the scheduler.
    """
    from app.jobs.enforce_limits import enforce_limits_job
    from app.jobs.reset_periodic_limits import reset_periodic_limits_job
    from app.jobs.sync_usage import sync_usage_job
    from app.jobs.billing import billing_job

    scheduler.add_job(
        sync_usage_job,
        "interval",
        seconds=45,
        id="sync_usage",
        name="Sync usage from OpenVPN management interface",
        replace_existing=True,
    )

    scheduler.add_job(
        enforce_limits_job,
        "interval",
        seconds=60,
        id="enforce_limits",
        name="Enforce data limits, expiry, and time windows",
        replace_existing=True,
    )

    scheduler.add_job(
        reset_periodic_limits_job,
        "cron",
        hour=0,
        minute=5,
        id="reset_periodic_limits",
        name="Reset periodic quota limits (daily near midnight)",
        replace_existing=True,
    )

    scheduler.add_job(
        billing_job,
        "cron",
        hour=1,
        minute=0,
        id="billing",
        name="Daily billing — calculate debt for all sub-admins",
        replace_existing=True,
    )

    logger.info("Background jobs registered: sync_usage, enforce_limits, reset_periodic_limits, billing")
