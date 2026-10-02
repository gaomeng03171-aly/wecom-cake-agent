import os

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DIFY_CLIENT_MODE"] = "mock"
os.environ["WECOM_SENDER_MODE"] = "mock"
os.environ["WECOM_CORP_ID"] = "test-corp"
os.environ["WECOM_CALLBACK_TOKEN"] = "test-token"
os.environ["WECOM_ENCODING_AES_KEY"] = "A" * 43

import pytest
from fastapi.testclient import TestClient

from app.db import Base, get_engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=get_engine())
    Base.metadata.create_all(bind=get_engine())
    with TestClient(app) as test_client:
        yield test_client
