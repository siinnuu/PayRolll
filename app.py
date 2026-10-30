"""
Application factory and main entry point for Employee Payroll Management System.
Implements create_app() factory pattern, blueprint registration, CSRF protection,
and user management CLI commands.
"""

import os
from typing import Optional, Union
from decimal import Decimal
import click
from flask import Flask, render_template, session, request
from config import config_by_name, Config
from extensions import db
from utils.csrf import generate_csrf_token, csrf_protect_request
from modules.core import core_bp
from modules.health import health_bp
from modules.auth import auth_bp
from modules.dashboard import dashboard_bp
from modules.common import common_bp
from modules.employees import employees_bp
from modules.attendance import attendance_bp
from modules.salary import salary_bp
from modules.payroll import payroll_bp
from modules.payments import payments_bp
from modules.reports import reports_bp


def create_app(config_name: Optional[Union[str, type]] = None) -> Flask:
    """
    Application factory for initializing the Flask app instance.
    
    Args:
        config_name: Configuration key name ('development', 'testing', 'production')
                     or a custom configuration class.
    
    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)

    # Determine configuration class
    if config_name is None:
        env = os.environ.get("FLASK_ENV", "development").lower()
        config_class = config_by_name.get(env, config_by_name["default"])
    elif isinstance(config_name, str):
        config_class = config_by_name.get(config_name, config_by_name["default"])
    else:
        config_class = config_name

    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)

    # Register Global CSRF Protection Hook
    app.before_request(csrf_protect_request)

    # Register Template Context Processors & Filters
    register_template_context(app)

    # Register Blueprints
    app.register_blueprint(core_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(common_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(salary_bp)
    app.register_blueprint(payroll_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(reports_bp)

    # Register Error Handlers
    register_error_handlers(app)

    # Register custom CLI commands
    register_cli_commands(app)

    return app


def register_template_context(app: Flask) -> None:
    """Inject template context globals and formatting filters."""

    @app.context_processor
    def inject_csrf_token():
        return {"csrf_token": generate_csrf_token}

    @app.template_filter("currency")
    def currency_filter(value):
        try:
            if value is None:
                return "$0.00"
            return f"${float(value):,.2f}"
        except Exception:
            return "$0.00"

    @app.template_filter("inr")
    def inr_filter(value):
        try:
            if value is None:
                return "₹0.00"
            return f"₹{float(value):,.2f}"
        except Exception:
            return "₹0.00"


def register_error_handlers(app: Flask) -> None:
    """Register application-wide HTTP error handlers."""

    @app.errorhandler(400)
    def bad_request_error(error):
        description = getattr(error, "description", "Bad Request")
        return render_template("errors/404.html", error_title="400 - Bad Request", error_message=description), 400

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template("errors/500.html"), 500


def register_cli_commands(app: Flask) -> None:
    """Register custom Flask CLI management commands."""

    @app.cli.command("ping-db")
    def ping_db_command():
        """Ping the configured MySQL database and report connectivity status."""
        click.echo("Probing MySQL database connectivity...")
        status = db.ping()
        if status.get("connected"):
            click.secho(
                f"[SUCCESS] {status.get('message')} (Host: {status.get('host')}:{status.get('port')}, DB: {status.get('database')})",
                fg="green",
            )
        else:
            click.secho(f"[FAILED] {status.get('message')}", fg="red")
            click.echo("Please verify your DB_HOST, DB_USER, DB_PASSWORD and DB_NAME in .env")

    @app.cli.command("init-db")
    @click.option("--seed/--no-seed", default=True, help="Populate sample seed data after schema creation.")
    def init_db_command(seed):
        """Create database tables from schema.sql and optionally seed data."""
        import mysql.connector

        click.echo("Initializing MySQL database schema...")
        db_config = Config.get_db_credentials()
        target_db = db_config.pop("database", "employee_payroll")

        # Step 1: Ensure database exists by connecting to MySQL server
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{target_db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
            cursor.close()
            conn.close()
            click.secho(f"[OK] Database '{target_db}' checked/created.", fg="green")
        except Exception as e:
            click.secho(f"[ERROR] Could not connect to MySQL server to create database: {e}", fg="red")
            return

        # Step 2: Apply schema.sql
        db_config["database"] = target_db
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()

            schema_file = os.path.join(app.root_path, "schema.sql")
            with open(schema_file, "r", encoding="utf-8") as f:
                schema_sql = f.read()

            for statement in [stmt.strip() for stmt in schema_sql.split(";") if stmt.strip()]:
                cursor.execute(statement)

            conn.commit()
            cursor.close()
            conn.close()
            click.secho("[OK] schema.sql executed successfully (6 tables created).", fg="green")
        except Exception as e:
            click.secho(f"[ERROR] Failed executing schema.sql: {e}", fg="red")
            return

        # Step 3: Apply seed.sql if requested
        if seed:
            try:
                conn = mysql.connector.connect(**db_config)
                cursor = conn.cursor()

                seed_file = os.path.join(app.root_path, "seed.sql")
                with open(seed_file, "r", encoding="utf-8") as f:
                    seed_sql = f.read()

                for statement in [stmt.strip() for stmt in seed_sql.split(";") if stmt.strip()]:
                    cursor.execute(statement)

                conn.commit()
                cursor.close()
                conn.close()
                click.secho("[OK] seed.sql executed successfully (sample records populated).", fg="green")
            except Exception as e:
                click.secho(f"[ERROR] Failed executing seed.sql: {e}", fg="red")

    @app.cli.command("create-user")
    @click.option("--username", prompt="Username", help="Unique username for the new account")
    @click.option("--email", prompt="Email address", help="User email address")
    @click.option("--password", prompt="Password", hide_input=True, confirmation_prompt=True, help="Password for user")
    @click.option(
        "--role",
        type=click.Choice(["ACCOUNTANT", "ADMIN", "HR", "EMPLOYEE"], case_sensitive=False),
        default="ACCOUNTANT",
        prompt="Role (ACCOUNTANT, ADMIN, HR, EMPLOYEE)",
        help="Access role for user (default: ACCOUNTANT for Finance Manager)"
    )
    def create_user_command(username, email, password, role):
        """Safely create an initial user account (e.g. Finance Manager or Admin) with Werkzeug password hashing."""
        from repositories.user_repository import UserRepository
        user_repo = UserRepository()

        click.echo(f"Creating user '{username}' with role '{role.upper()}'...")
        try:
            # Check for existing username or email
            if user_repo.get_by_username(username):
                click.secho(f"[ERROR] Username '{username}' already exists.", fg="red")
                return
            if user_repo.get_by_email(email):
                click.secho(f"[ERROR] Email '{email}' is already registered.", fg="red")
                return

            user_id = user_repo.create_user(
                username=username,
                email=email,
                password=password,
                role=role.upper(),
                is_active=True
            )
            click.secho(
                f"[SUCCESS] User '{username}' created successfully (ID: {user_id}, Role: {role.upper()})! Password hashed with Werkzeug.",
                fg="green"
            )
        except Exception as e:
            click.secho(f"[ERROR] Failed to create user: {e}", fg="red")


# Root application instance for WSGI servers and `flask run`
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=True)
