import pytest
from pydantic import SecretStr
from rq.job import Job

from argilla_server.constants import API_KEY_HEADER_NAME
from argilla_server.jobs.queues import REDIS_CONNECTION
from argilla_server.settings import settings
from tests.factories import AnnotatorFactory, DatasetFactory


@pytest.fixture
def csghub_config(monkeypatch):
    monkeypatch.setattr(settings, "csghub_endpoint", "https://csghub.test")
    monkeypatch.setattr(settings, "csghub_token", SecretStr("private-csg-token"))


@pytest.mark.asyncio
async def test_resolve_url_never_contacts_user_supplied_hosts(
    async_client, owner_auth_header, csghub_config, respx_mock
):
    for url, expected in [
        ("https://huggingface.co/datasets/a/b", 200),
        ("https://csghub.test/datasets/a/b", 200),
        ("https://evil.test/datasets/a/b", 422),
        ("a/b", 422),
        ("https://csghub.test:bad/datasets/a/b", 422),
    ]:
        result = await async_client.get("/api/v1/hub/datasets/resolve", params={"url": url}, headers=owner_auth_header)
        assert result.status_code == expected
    assert not respx_mock.calls


@pytest.mark.asyncio
async def test_resolve_requires_authentication(async_client):
    result = await async_client.get(
        "/api/v1/hub/datasets/resolve", params={"url": "https://huggingface.co/datasets/a/b"}
    )
    assert result.status_code == 401


@pytest.mark.asyncio
async def test_native_catalog_becomes_hub_info(async_client, owner_auth_header, csghub_config, respx_mock):
    url = "https://csghub.test/api/v1/datasets/owner/repo/dataviewer"
    respx_mock.get(f"{url}/catalog").respond(
        200,
        json={
            "data": {
                "dataset_info": [
                    {
                        "config_name": "default",
                        "splits": [{"name": "train", "num_examples": 1, "files": ["internal-path"]}],
                    }
                ]
            }
        },
    )
    respx_mock.get(f"{url}/rows").respond(
        200, json={"data": {"columns": ["text"], "columns_type": ["VARCHAR"], "rows": [["hello"]], "total": 1}}
    )
    result = await async_client.get(
        "/api/v1/hub/datasets/info", params={"source": "csghub", "dataset": "owner/repo"}, headers=owner_auth_header
    )
    assert result.status_code == 200
    assert result.json()["dataset_info"]["default"]["features"]["text"]["dtype"] == "string"
    assert "internal-path" not in result.text
    assert "private-csg-token" not in result.text
    assert all(call.request.headers["Authorization"] == "Bearer private-csg-token" for call in respx_mock.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("status,expected", [(401, 401), (403, 403), (404, 404), (500, 502)])
async def test_native_errors_are_sanitized(
    async_client, owner_auth_header, csghub_config, respx_mock, status, expected
):
    respx_mock.get("https://csghub.test/api/v1/datasets/owner/repo/dataviewer/catalog").respond(
        status, text="private-csg-token internal upstream details"
    )
    result = await async_client.get(
        "/api/v1/hub/datasets/info", params={"source": "csghub", "dataset": "owner/repo"}, headers=owner_auth_header
    )
    assert result.status_code == expected
    assert "private-csg-token" not in result.text


@pytest.mark.asyncio
async def test_csghub_keeps_existing_role_policy(async_client, csghub_config, respx_mock):
    annotator = await AnnotatorFactory.create()
    result = await async_client.get(
        "/api/v1/hub/datasets/info",
        params={"source": "csghub", "dataset": "owner/repo"},
        headers={API_KEY_HEADER_NAME: annotator.api_key},
    )
    assert result.status_code == 403
    assert not respx_mock.calls


@pytest.mark.asyncio
async def test_import_job_retains_source_subset_split_and_mapping(async_client, owner_auth_header, csghub_config):
    dataset = await DatasetFactory.create()
    payload = {
        "source": "csghub",
        "name": "owner/repo",
        "subset": "custom",
        "split": "test",
        "mapping": {"fields": [{"source": "text", "target": "document"}]},
    }
    result = await async_client.post(f"/api/v1/datasets/{dataset.id}/import", json=payload, headers=owner_auth_header)
    assert result.status_code == 202, result.text
    job = Job.fetch(result.json()["id"], connection=REDIS_CONNECTION)
    assert job.kwargs["source"] == "csghub"
    assert job.kwargs["subset"] == "custom"
    assert job.kwargs["split"] == "test"
    assert job.kwargs["mapping"]["fields"] == payload["mapping"]["fields"]
