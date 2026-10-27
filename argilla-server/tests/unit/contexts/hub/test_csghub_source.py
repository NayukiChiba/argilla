import httpx
import pytest
from pydantic import SecretStr

from argilla_server.contexts.hub_sources import CSGHubError, CSGHubSource, feature_for_column, resolve_dataset_url
from argilla_server.settings import settings


@pytest.fixture
def source_config(monkeypatch):
    monkeypatch.setattr(settings, "csghub_endpoint", "https://hub.example.test")
    monkeypatch.setattr(settings, "csghub_internal_endpoint", None)
    monkeypatch.setattr(settings, "csghub_token", SecretStr("csg-private-token"))
    monkeypatch.setenv("HF_TOKEN", "hf-must-not-leak")


def response(data):
    return httpx.Response(200, json={"msg": "OK", "data": data})


@pytest.mark.parametrize(
    "url,source",
    [
        ("https://huggingface.co/datasets/stanfordnlp/imdb", "huggingface"),
        ("https://huggingface.co:443/datasets/stanfordnlp/imdb/", "huggingface"),
        ("https://hub.example.test/datasets/stanfordnlp/imdb", "csghub"),
    ],
)
def test_resolve_dataset_url(source_config, url, source):
    assert resolve_dataset_url(url) == {"repo_id": "stanfordnlp/imdb", "source": source}


@pytest.mark.parametrize(
    "url",
    [
        "stanfordnlp/imdb",
        "https://huggingface.co.evil.test/datasets/a/b",
        "https://huggingface.co@evil.test/datasets/a/b",
        "http://huggingface.co/datasets/a/b",
        "https://hub.example.test:444/datasets/a/b",
        "https://hub.example.test/models/a/b",
        "https://hub.example.test/datasets/a/b/tree/main",
        "https://hub.example.test/datasets/%2e%2e/b",
        "https://hub.example.test/datasets/a/b?token=private",
        "https://hub.example.test/datasets/a/b#viewer",
    ],
)
def test_rejects_ambiguous_or_untrusted_urls(source_config, url):
    with pytest.raises(CSGHubError):
        resolve_dataset_url(url)


def test_hf_url_does_not_require_csghub_configuration(monkeypatch):
    monkeypatch.setattr(settings, "csghub_endpoint", None)
    assert resolve_dataset_url("https://huggingface.co/datasets/a/b")["source"] == "huggingface"


def test_csghub_url_respects_endpoint_path(monkeypatch):
    monkeypatch.setattr(settings, "csghub_endpoint", "http://localhost:8080/hub")
    assert resolve_dataset_url("http://localhost:8080/hub/datasets/a/b")["repo_id"] == "a/b"
    with pytest.raises(CSGHubError):
        resolve_dataset_url("http://localhost:8080/datasets/a/b")


def test_container_transport_keeps_public_url_validation(monkeypatch):
    monkeypatch.setattr(settings, "csghub_endpoint", "http://127.0.0.1")
    monkeypatch.setattr(settings, "csghub_internal_endpoint", "http://host.docker.internal")
    assert resolve_dataset_url("http://127.0.0.1/datasets/a/b")["source"] == "csghub"
    assert CSGHubSource("a/b").url == "http://host.docker.internal/api/v1/datasets/a/b/dataviewer"
    with pytest.raises(CSGHubError):
        resolve_dataset_url("http://evil.test/datasets/a/b")


@pytest.mark.asyncio
async def test_catalog_features_and_token_isolation(source_config, respx_mock):
    catalog = [
        {"config_name": "text", "splits": [{"name": "train", "num_examples": 2}]},
        {"config_name": "chat", "splits": [{"name": "test", "num_examples": 1}]},
    ]
    respx_mock.get("https://hub.example.test/api/v1/datasets/owner/repo/dataviewer/catalog").mock(
        return_value=response({"dataset_info": catalog})
    )

    def sample(request):
        assert request.headers["authorization"] == "Bearer csg-private-token"
        if request.url.params["config"] == "text":
            return response(
                {
                    "columns": ["text", "score"],
                    "columns_type": ["VARCHAR", "BIGINT"],
                    "rows": [["example", 1]],
                    "total": 2,
                }
            )
        return response(
            {
                "columns": ["messages"],
                "columns_type": ["LIST"],
                "rows": [[[{"role": "user", "content": "hello"}]]],
                "total": 1,
            }
        )

    respx_mock.get("https://hub.example.test/api/v1/datasets/owner/repo/dataviewer/rows").mock(side_effect=sample)
    result = await CSGHubSource("owner/repo").viewer("info", {})
    info = result["dataset_info"]
    assert info["text"]["features"]["score"] == {"_type": "Value", "dtype": "int64"}
    assert info["chat"]["features"]["messages"][0]["role"]["dtype"] == "string"
    assert list(info["chat"]["splits"]) == ["test"]
    assert all(c.request.url.host == "hub.example.test" for c in respx_mock.calls)


@pytest.mark.asyncio
async def test_rows_cross_page_boundary_preserve_nested_values(source_config, respx_mock):
    def page(request):
        params = request.url.params
        assert params["config"] == "a/b + c"
        start = (int(params["page"]) - 1) * int(params["per"])
        rows = [[i, {"messages": [str(i)], "null": None}] for i in range(start, min(start + 100, 205))]
        return response({"columns": ["id", "object"], "rows": rows, "total": 205})

    respx_mock.get("https://hub.example.test/api/v1/datasets/owner/repo/dataviewer/rows").mock(side_effect=page)
    result = await CSGHubSource("owner/repo").viewer(
        "rows", {"config": "a/b + c", "split": "train", "offset": "98", "length": "5"}
    )
    assert [r["row"]["id"] for r in result["rows"]] == list(range(98, 103))
    assert result["rows"][0]["row"]["object"] == {"messages": ["98"], "null": None}
    assert len(respx_mock.calls) == 2


@pytest.mark.asyncio
async def test_batches_respect_limit_and_selected_split(source_config, respx_mock):
    respx_mock.get("https://hub.example.test/api/v1/datasets/owner/repo/dataviewer/catalog").mock(
        return_value=response({"dataset_info": [{"config_name": "default", "splits": [{"name": "test"}]}]})
    )

    def page(request):
        assert request.url.params["split"] == "test"
        start = (int(request.url.params["page"]) - 1) * 100
        return response({"columns": ["id"], "rows": [[i] for i in range(start, min(start + 100, 250))], "total": 250})

    route = respx_mock.get("https://hub.example.test/api/v1/datasets/owner/repo/dataviewer/rows").mock(
        side_effect=page
    )
    batches = [batch async for batch in CSGHubSource("owner/repo").batches("default", "test", 105)]
    assert [len(batch) for batch in batches] == [100, 5]
    assert batches[-1][-1] == {"id": 104}
    assert route.call_count == 2


@pytest.mark.parametrize("repo", ["../repo", "owner/..", "http://evil/datasets/x", "owner/repo?x=1", "a/b/c"])
def test_rejects_invalid_repository_paths(source_config, repo):
    with pytest.raises(CSGHubError):
        CSGHubSource(repo)


def test_missing_endpoint_is_explicit(monkeypatch):
    monkeypatch.setattr(settings, "csghub_endpoint", None)
    with pytest.raises(CSGHubError, match="ARGILLA_CSGHUB_ENDPOINT"):
        CSGHubSource("owner/repo")


@pytest.mark.asyncio
async def test_unprepared_dataset_is_not_reported_as_empty_success(source_config, respx_mock):
    respx_mock.get("https://hub.example.test/api/v1/datasets/owner/repo/dataviewer/catalog").mock(
        return_value=response({"status": 1, "dataset_info": []})
    )
    with pytest.raises(CSGHubError, match="not ready") as exc:
        await CSGHubSource("owner/repo").viewer("info", {})
    assert exc.value.status_code == 409


def test_rejects_malformed_rows_instead_of_silently_dropping_columns():
    with pytest.raises(CSGHubError):
        CSGHubSource._decode_rows({"columns": ["text", "label"], "rows": [["missing-label"]]})


@pytest.mark.parametrize(
    "kind,values,want", [("BIGINT", [None], "int64"), ("VARCHAR", [None], "string"), ("BOOLEAN", [False], "bool")]
)
def test_column_types_survive_null_samples(kind, values, want):
    assert feature_for_column(kind, values)["dtype"] == want


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 404, 500])
async def test_upstream_errors_are_not_empty_datasets(source_config, respx_mock, status):
    respx_mock.get("https://hub.example.test/api/v1/datasets/owner/repo/dataviewer/catalog").mock(
        return_value=httpx.Response(status)
    )
    with pytest.raises(httpx.HTTPStatusError):
        await CSGHubSource("owner/repo").viewer("info", {})
