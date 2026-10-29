#  Copyright 2021-present, the Recognai S.L. team.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from pydantic import SecretStr

import pytest

from datasets import Dataset as HFDataset, config as hf_datasets_config
from huggingface_hub import HfApi

from argilla_server.contexts import hub
from argilla_server.contexts.hub import HubDatasetExporter
from argilla_server.contexts.hub_sources import csghub_public_endpoint, csghub_sdk_endpoint
from argilla_server.enums import DatasetStatus, FieldType
from argilla_server.settings import settings

from tests.database import SyncTestSession
from tests.factories import DatasetSyncFactory, FieldSyncFactory, RecordSyncFactory


@pytest.fixture
def sync_test_session(mocker):
    session = SyncTestSession()

    def override_get_sync_db():
        yield session

    mocker.patch.object(hub, "get_sync_db", override_get_sync_db)

    yield session


class TestCSGHubExport:
    def test_sdk_endpoint_appends_hf_prefix(self, monkeypatch):
        monkeypatch.setattr(settings, "csghub_endpoint", "https://csghub.test")
        monkeypatch.setattr(settings, "csghub_internal_endpoint", "http://csghub.internal")
        monkeypatch.setattr(settings, "csghub_token", SecretStr("private-csg-token"))

        assert csghub_sdk_endpoint() == "https://csghub.test/hf"
        assert csghub_sdk_endpoint(internal=True) == "http://csghub.internal/hf"
        assert csghub_public_endpoint() == "https://csghub.test"

    def test_sdk_endpoint_without_internal_override(self, monkeypatch):
        monkeypatch.setattr(settings, "csghub_endpoint", "https://csghub.test")
        monkeypatch.setattr(settings, "csghub_internal_endpoint", None)

        assert csghub_sdk_endpoint(internal=True) == "https://csghub.test/hf"

    def test_export_to_csghub_routes_through_configured_endpoint(self, sync_test_session, mocker, monkeypatch):
        monkeypatch.setattr(settings, "csghub_endpoint", "https://csghub.test")
        monkeypatch.setattr(settings, "csghub_internal_endpoint", None)
        monkeypatch.setattr(settings, "csghub_token", None)

        dataset = DatasetSyncFactory.create(status=DatasetStatus.ready)
        FieldSyncFactory.create(name="text", settings={"type": FieldType.text, "use_markdown": False}, dataset=dataset)
        RecordSyncFactory.create(fields={"text": "Hello World"}, dataset=dataset)

        mock_push_to_hub = mocker.patch.object(HFDataset, "push_to_hub")
        mock_hf_api = mocker.patch("argilla_server.contexts.hub.HfApi")
        mock_hf_api.return_value.list_repo_tree.return_value = iter(
            [{"path": "data/train-00000-of-00001.parquet", "type": "file"}]
        )
        previous_endpoint = hf_datasets_config.HF_ENDPOINT

        try:
            HubDatasetExporter(dataset).export_to(
                name="owner/repo",
                subset="default",
                split="train",
                private=False,
                token="csghub-token",
                source="csghub",
            )
        finally:
            assert hf_datasets_config.HF_ENDPOINT == previous_endpoint

        mock_push_to_hub.assert_called_once()
        _, push_kwargs = mock_push_to_hub.call_args
        assert push_kwargs["repo_id"] == "owner/repo"
        assert push_kwargs["token"] == "csghub-token"

        assert mock_hf_api.call_args.kwargs["endpoint"] == "https://csghub.test/hf"
        assert mock_hf_api.call_args.kwargs["token"] == "csghub-token"
        mock_hf_api.return_value.create_repo.assert_called_once()
        # data dir exists: no placeholder upload needed
        mock_hf_api.return_value.upload_file.assert_not_called()

    def test_export_to_csghub_seeds_missing_data_dir(self, sync_test_session, mocker, monkeypatch):
        import requests
        from huggingface_hub.errors import HfHubHTTPError

        response = requests.Response()
        response.status_code = 500

        monkeypatch.setattr(settings, "csghub_endpoint", "https://csghub.test")
        monkeypatch.setattr(settings, "csghub_internal_endpoint", None)
        monkeypatch.setattr(settings, "csghub_token", None)

        dataset = DatasetSyncFactory.create(status=DatasetStatus.ready)
        FieldSyncFactory.create(name="text", settings={"type": FieldType.text, "use_markdown": False}, dataset=dataset)
        RecordSyncFactory.create(fields={"text": "Hello World"}, dataset=dataset)

        mocker.patch.object(HFDataset, "push_to_hub")
        mock_hf_api = mocker.patch("argilla_server.contexts.hub.HfApi")
        mock_hf_api.return_value.list_repo_tree.side_effect = HfHubHTTPError("500", response=response)
        mock_hf_api.return_value.upload_file.side_effect = None

        HubDatasetExporter(dataset).export_to(
            name="owner/repo",
            subset="custom",
            split="train",
            private=False,
            token="csghub-token",
            source="csghub",
        )

        mock_hf_api.return_value.upload_file.assert_called_once()
        _, upload_kwargs = mock_hf_api.return_value.upload_file.call_args
        assert upload_kwargs["path_in_repo"] == "custom/.gitkeep"
