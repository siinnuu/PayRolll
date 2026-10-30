"""
Health-check routes confirming Flask status and safely reporting database connectivity.
"""

from datetime import datetime, timezone
from flask import Blueprint, jsonify, render_template, request, current_app
from repositories.health_repository import HealthRepository

health_bp = Blueprint("health", __name__)
health_repo = HealthRepository()


@health_bp.route("/health")
def health_check():
    """
    Health-check endpoint.
    Returns JSON if requested via API header or format query param,
    otherwise renders the interactive diagnostics page.
    """
    db_status = health_repo.test_database_connectivity()
    is_healthy = bool(db_status.get("connected"))

    payload = {
        "status": "healthy" if is_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "flask": {
            "status": "online",
            "app_name": current_app.config.get("APP_NAME", "Employee Payroll Management System"),
            "version": current_app.config.get("APP_VERSION", "1.0.0"),
            "module": current_app.config.get("MODULE_NAME", "Module 1"),
            "debug": current_app.debug,
            "testing": current_app.testing,
        },
        "database": {
            "connected": is_healthy,
            "message": db_status.get("message"),
            "host": db_status.get("host"),
            "port": db_status.get("port"),
            "database": db_status.get("database"),
            "user": db_status.get("user"),
            "server_version": db_status.get("server_version"),
            "pool_active": db_status.get("pool_active"),
            "error_code": db_status.get("error_code"),
        },
    }

    # Respond with JSON if client requests it
    wants_json = (
        request.args.get("format") == "json"
        or request.args.get("json") == "1"
        or request.is_json
        or "application/json" in request.headers.get("Accept", "")
    )

    if wants_json:
        status_code = 200 if is_healthy else 503
        return jsonify(payload), status_code

    # Otherwise render modern HTML diagnostics page
    schema_status = health_repo.get_schema_verification() if is_healthy else None
    return render_template(
        "health.html",
        health=payload,
        schema_status=schema_status,
        app_name=current_app.config.get("APP_NAME"),
        app_version=current_app.config.get("APP_VERSION"),
    )


@health_bp.route("/api/health")
def api_health():
    """Explicit JSON-only API health-check endpoint."""
    db_status = health_repo.test_database_connectivity()
    is_healthy = bool(db_status.get("connected"))

    payload = {
        "status": "healthy" if is_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "flask": {
            "status": "online",
            "app_name": current_app.config.get("APP_NAME", "Employee Payroll Management System"),
            "version": current_app.config.get("APP_VERSION", "1.0.0"),
            "debug": current_app.debug,
        },
        "database": {
            "connected": is_healthy,
            "message": db_status.get("message"),
            "host": db_status.get("host"),
            "port": db_status.get("port"),
            "database": db_status.get("database"),
            "user": db_status.get("user"),
            "server_version": db_status.get("server_version"),
            "pool_active": db_status.get("pool_active"),
            "error_code": db_status.get("error_code"),
        },
    }

    status_code = 200 if is_healthy else 503
    return jsonify(payload), status_code
