from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock

import httpx
import pytest

from argilla import Settings, TextField, TextQuestion
from argilla._api._hub import HubAPI
from argilla.datasets._io._hub import HubImportExportMixin

INFO = {
    "default": {
        "features": {"text": {"_type": "Value", "dtype": "string"}},
        "splits": {"train": {"name": "train"}, "test": {"name": "test"}},
    }
}


def make_client():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["X-Argilla-Api-Key"] == "argilla-key"
        assert request.url.host == "argilla.test"
        if request.url.path.endswith("/resolve"):
            assert request.url.params["url"] == "https://csghub.test/datasets/owner/repo"
            return httpx.Response(200, json={"repo_id": "owner/repo", "source": "csghub"})
        assert request.url.params["source"] == "csghub"
        if request.url.path.endswith("/info"):
            return httpx.Response(200, json={"dataset_info": INFO})
        offset = int(request.url.params["offset"])
        length = int(request.url.params["length"])
        return httpx.Response(
            200,
            json={
                "rows": [{"row": {"text": f"row {i}"}} for i in range(offset, min(offset + length, 205))],
                "num_rows_total": 205,
            },
        )

    http = httpx.Client(
        base_url="https://argilla.test",
        headers={"X-Argilla-Api-Key": "argilla-key"},
        transport=httpx.MockTransport(handler),
    )
    return SimpleNamespace(api=SimpleNamespace(hub=HubAPI(http)), api_url="https://argilla.test"), requests


class DatasetDouble(HubImportExportMixin):
    def __init__(self, **kwargs):
        self.arguments = kwargs
        self.records = SimpleNamespace(log=Mock())
        self.create = Mock()


def test_sdk_accepts_complete_url_and_infers_source():
    client, requests = make_client()
    dataset = DatasetDouble.from_hub(
        "https://csghub.test/datasets/owner/repo", client=client, settings="auto", max_records=1
    )
    assert dataset.arguments["name"] == "owner/repo"
    dataset.records.log.assert_called_once_with([{"text": "row 0"}])
    assert requests[0].url.path.endswith("/resolve")


def test_sdk_settings_accepts_complete_url():
    client, requests = make_client()
    settings = Settings.from_hub("https://csghub.test/datasets/owner/repo", client=client)
    assert settings.fields[0].name == "text"
    assert requests[0].url.path.endswith("/resolve")


def test_sdk_hf_url_is_normalized_before_ui_link(mocker):
    mocker.patch("webbrowser.open")
    client, _ = make_client()
    client.api.hub.resolve = Mock(return_value={"repo_id": "owner/repo", "source": "huggingface"})
    with pytest.warns(UserWarning):
        url = DatasetDouble.from_hub("https://huggingface.co/datasets/owner/repo", client=client, settings="ui")
    assert urlsplit(url).path == "/owner%2Frepo"
    assert "csghub" not in url


def test_sdk_reads_every_page_through_argilla_and_preserves_client_workspace():
    client, requests = make_client()
    settings = Settings(fields=[TextField("text")], questions=[TextQuestion("answer")])
    dataset = DatasetDouble.from_hub(
        "owner/repo",
        source="csghub",
        name="imported",
        client=client,
        workspace="team",
        settings=settings,
        split="test",
    )
    assert dataset.arguments["client"] is client
    assert dataset.arguments["workspace"] == "team"
    assert dataset.arguments["name"] == "imported"
    batches = [call.args[0] for call in dataset.records.log.call_args_list]
    assert [len(batch) for batch in batches] == [100, 100, 5]
    assert batches[-1][-1] == {"text": "row 204"}
    assert all(r.url.params["split"] == "test" for r in requests if r.url.path.endswith("/rows"))


def test_sdk_auto_settings_uses_same_source_and_limit():
    client, _ = make_client()
    dataset = DatasetDouble.from_hub("owner/repo", source="csghub", client=client, settings="auto", max_records=101)
    assert dataset.arguments["settings"].fields[0].name == "text"
    assert [len(c.args[0]) for c in dataset.records.log.call_args_list] == [100, 1]


def test_sdk_settings_only_does_not_read_records():
    client, requests = make_client()
    dataset = DatasetDouble.from_hub("owner/repo", source="csghub", client=client, settings="auto", with_records=False)
    dataset.records.log.assert_not_called()
    assert all(request.url.path.endswith("/info") for request in requests)


def test_sdk_invalid_split_rejected_before_dataset_creation():
    client, _ = make_client()
    with pytest.raises(ValueError, match="Unknown CSGHub split"):
        DatasetDouble.from_hub("owner/repo", source="csghub", client=client, settings="auto", split="missing")


def test_sdk_ui_link_retains_source_subset_split_without_tokens(mocker):
    mocker.patch("webbrowser.open")
    client, _ = make_client()
    with pytest.warns(UserWarning):
        url = DatasetDouble.from_hub(
            "owner/repo", source="csghub", client=client, settings="ui", subset="custom", split="test"
        )
    assert urlsplit(url).path == "/owner%2Frepo"
    assert parse_qs(urlsplit(url).query) == {"source": ["csghub"], "subset": ["custom"], "split": ["test"]}
    assert "token" not in url


@pytest.mark.parametrize("maximum", [-1, True, 1.5])
def test_sdk_invalid_limit(maximum):
    client, _ = make_client()
    with pytest.raises(ValueError, match="max_records"):
        DatasetDouble.from_hub("owner/repo", source="csghub", client=client, settings="auto", max_records=maximum)


def test_sdk_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported hub source"):
        DatasetDouble.from_hub("owner/repo", source="unknown")


class DatasetPushDouble(HubImportExportMixin):
    def __init__(self, client):
        self._client = client
        self.records = Mock()
        self.records.return_value.to_datasets.return_value = Mock(__len__=Mock(return_value=1))
        self.to_disk = Mock()


def make_push_client():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["X-Argilla-Api-Key"] == "argilla-key"
        assert request.url.host == "argilla.test"
        if request.url.path.endswith("/resolve"):
            assert request.url.params["url"] == "https://csghub.test/datasets/owner/repo"
            return httpx.Response(200, json={"repo_id": "owner/repo", "source": "csghub"})
        assert request.url.params["source"] == "csghub"
        assert request.url.path.endswith("/export-target")
        return httpx.Response(200, json={"source": "csghub", "endpoint": "https://csghub.test"})

    http = httpx.Client(
        base_url="https://argilla.test",
        headers={"X-Argilla-Api-Key": "argilla-key"},
        transport=httpx.MockTransport(handler),
    )
    return SimpleNamespace(api=SimpleNamespace(hub=HubAPI(http)), api_url="https://argilla.test"), requests


def test_sdk_push_to_csghub_requires_token(mocker):
    from argilla import Argilla

    client, _ = make_push_client()
    mocker.patch.object(Argilla, "_get_default", return_value=client)

    dataset = DatasetPushDouble(client)
    with pytest.raises(ValueError, match="CSGHub access token"):
        dataset.to_hub("owner/repo", source="csghub", generate_card=False)


def test_sdk_push_to_csghub_uses_configured_endpoint(mocker):
    from argilla import Argilla

    client, requests = make_push_client()
    mocker.patch.object(Argilla, "_get_default", return_value=client)
    mock_hf_api = mocker.patch("huggingface_hub.HfApi")
    mock_hf_api.return_value.list_repo_tree.return_value = iter(
        [{"path": "data/train-00000-of-00001.parquet", "type": "file"}]
    )
    from datasets import config as hf_config

    previous_endpoint = hf_config.HF_ENDPOINT

    dataset = DatasetPushDouble(client)
    dataset.to_hub("owner/repo", source="csghub", token="csghub-token", generate_card=False)
    mock_hf_api.return_value.create_repo.assert_called_once()
    mock_hf_api.return_value.upload_file.assert_not_called()

    assert mock_hf_api.call_args.kwargs["endpoint"] == "https://csghub.test"
    assert mock_hf_api.call_args.kwargs["token"] == "csghub-token"
    push_call = dataset.records.return_value.to_datasets.return_value.push_to_hub.call_args
    assert push_call.args[0] == "owner/repo"
    assert requests[-1].url.path.endswith("/export-target")
    from datasets import config as hf_config

    assert hf_config.HF_ENDPOINT == previous_endpoint


def test_sdk_push_resolves_complete_csghub_url(mocker):
    from argilla import Argilla

    client, requests = make_push_client()
    mocker.patch.object(Argilla, "_get_default", return_value=client)
    mock_hf_api = mocker.patch("huggingface_hub.HfApi")
    mock_hf_api.return_value.list_repo_tree.return_value = iter(
        [{"path": "data/train-00000-of-00001.parquet", "type": "file"}]
    )

    dataset = DatasetPushDouble(client)
    dataset.to_hub("https://csghub.test/datasets/owner/repo", token="csghub-token", generate_card=False)

    assert requests[0].url.path.endswith("/resolve")
    assert mock_hf_api.call_args.kwargs["endpoint"] == "https://csghub.test"
