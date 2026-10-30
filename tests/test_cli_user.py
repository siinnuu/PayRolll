"""
Automated tests for user creation CLI commands (Module 2).
"""

from unittest.mock import patch, MagicMock


def test_cli_create_user_command_success(runner):
    """Verify 'create-user' CLI command creates user with Werkzeug hash."""
    with patch("repositories.user_repository.UserRepository.get_by_username", return_value=None), \
         patch("repositories.user_repository.UserRepository.get_by_email", return_value=None), \
         patch("repositories.user_repository.UserRepository.create_user", return_value=101) as mock_create:

        result = runner.invoke(
            args=[
                "create-user",
                "--username", "finance_lead",
                "--email", "finance@example.com",
                "--password", "StrongPass@123",
                "--role", "ACCOUNTANT",
            ]
        )

        assert result.exit_code == 0
        assert "created successfully" in result.output
        mock_create.assert_called_once_with(
            username="finance_lead",
            email="finance@example.com",
            password="StrongPass@123",
            role="ACCOUNTANT",
            is_active=True
        )


def test_cli_create_user_duplicate_username(runner):
    """Verify 'create-user' CLI rejects duplicate usernames."""
    existing_user = {"id": 1, "username": "admin", "email": "admin@example.com"}

    with patch("repositories.user_repository.UserRepository.get_by_username", return_value=existing_user):
        result = runner.invoke(
            args=[
                "create-user",
                "--username", "admin",
                "--email", "newadmin@example.com",
                "--password", "Pass@123",
                "--role", "ADMIN",
            ]
        )

        assert result.exit_code == 0
        assert "already exists" in result.output
