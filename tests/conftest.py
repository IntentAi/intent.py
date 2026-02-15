"""Shared pytest fixtures."""

import pytest


@pytest.fixture
def mock_token() -> str:
    """Return a mock bot token."""
    return "bot_test_token_123"
