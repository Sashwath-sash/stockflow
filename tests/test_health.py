from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.api.health import readiness_check


def test_readiness_check_reports_reachable_database() -> None:
    db = Mock()

    result = readiness_check(db)

    db.execute.assert_called_once()
    assert result == {"status": "ready", "database": "reachable"}


def test_readiness_check_returns_503_when_database_is_unavailable() -> None:
    db = Mock()
    db.execute.side_effect = SQLAlchemyError("connection failed")

    with pytest.raises(HTTPException) as error:
        readiness_check(db)

    assert error.value.status_code == 503
    assert error.value.detail == "Database is unavailable"
