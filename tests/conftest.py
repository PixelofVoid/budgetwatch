import pytest

from budgetwatch.db.connection import Database
from budgetwatch.services.budget import BudgetService


@pytest.fixture
def db():
    database = Database.in_memory(seed=False)
    yield database
    database.close()


@pytest.fixture
def service(db):
    return BudgetService(db)
