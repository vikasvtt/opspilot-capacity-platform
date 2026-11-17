import os

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies import get_db
from app.core.security import create_token_pair, hash_password
from app.db.base import Base
from app.models.entities import Rack, Site, User, UserRole
from app import models  # noqa: F401
from app.main import app

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
test_engine = create_engine(TEST_DATABASE_URL) if TEST_DATABASE_URL else None
TestSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False) if test_engine else None


@pytest.fixture
def db():
    if test_engine is None:
        pytest.skip("Set TEST_DATABASE_URL to run API integration tests")
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(test_engine)


@pytest.fixture
def client(db):
    def override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_user(db, role: UserRole, email: str | None = None) -> tuple[User, dict[str, str]]:
    email = email or f"{role.value}@example.test"
    user = User(email=email, password_hash=hash_password("StrongPass123!"), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, create_token_pair(user.id, user.role.value)


def make_site_and_rack(db, capacity: int = 10):
    site = Site(name="Hyderabad DC", city="Hyderabad", total_capacity=capacity)
    db.add(site)
    db.flush()
    rack = Rack(site_id=site.id, name="R-01", total_slots=capacity, used_slots=0)
    db.add(rack)
    db.commit()
    db.refresh(site)
    db.refresh(rack)
    return site, rack
