"""
Health-check routes confirming Flask status and database connectivity safely.
Public endpoints return minimal responses and do not expose sensitive internal configuration.
Detailed diagnostics are restricted to authenticated administrators.
"""

from datetime import datetime, timezone
from flask import Blueprint, jsonify, render_template, request, current_app, session
from repositories.health_repository import HealthRepository

health_bp = Blueprint("health", __name__)
health_repo = HealthRepository()


@health_bp.route("/health")
def health_check():
    """
    Health-check endpoint.
    Public requests return minimal, non-sensitive status.
    Authenticated administrators may receive detailed diagnostics.
    """
    db_status = health_repo.test_database_connectivity()
    is_healthy = bool(db_status.get("connected"))
    is_admin = session.get("role") == "ADMIN"

    # Base public payload - strictly minimal, no credentials or network topology
    payload = {
        "status": "healthy" if is_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "flask": {
            "status": "online",
        },
        "database": {
            "connected": is_healthy,
        },
    }

    # Only include detailed diagnostics if user is an authenticated administrator
    if is_admin:
        payload["flask"]["app_name"] = current_app.config.get("APP_NAME")
        payload["flask"]["version"] = current_app.config.get("APP_VERSION")
        payload["flask"]["debug"] = current_app.debug
        payload["database"]["pool_active"] = db_status.get("pool_active")
        payload["database"]["message"] = db_status.get("message")

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

    # Render HTML diagnostics page without exposing database credentials
    schema_status = None
    if is_admin and is_healthy:
        schema_status = health_repo.get_schema_verification()

    return render_template(
        "health.html",
        health=payload,
        is_healthy=is_healthy,
        is_admin=is_admin,
        schema_status=schema_status,
        app_name=current_app.config.get("APP_NAME"),
        app_version=current_app.config.get("APP_VERSION"),
    )


@health_bp.route("/api/health")
def api_health():
    """
    Minimal public JSON health-check endpoint for external monitoring.
    Returns only minimal status (e.g. {"status": "ok"}).
    Never exposes internal host, port, credentials, or schema.
    """
    db_status = health_repo.test_database_connectivity()
    is_healthy = bool(db_status.get("connected"))

    # Administrator can request detailed view if authenticated
    if session.get("role") == "ADMIN" and request.args.get("detailed") in ("1", "true"):
        return jsonify({
            "status": "ok" if is_healthy else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database_connected": is_healthy,
            "pool_active": db_status.get("pool_active"),
        }), (200 if is_healthy else 503)

    # Standard public minimal response
    status_code = 200 if is_healthy else 503
    return jsonify({"status": "ok" if is_healthy else "degraded"}), status_code
