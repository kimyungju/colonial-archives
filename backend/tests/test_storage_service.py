from __future__ import annotations

import importlib
import sys

from google.auth.exceptions import DefaultCredentialsError
from google.cloud import storage


def test_storage_service_import_does_not_require_application_credentials(monkeypatch) -> None:
    def fail_client(*_args, **_kwargs):
        raise DefaultCredentialsError("missing credentials")

    sys.modules.pop("app.services.storage", None)
    monkeypatch.setattr(storage, "Client", fail_client)

    module = importlib.import_module("app.services.storage")

    expected_url = f"gs://{module.settings.CLOUD_STORAGE_BUCKET}/CO 273.pdf"
    assert module.storage_service.get_pdf_url("CO 273") == expected_url
