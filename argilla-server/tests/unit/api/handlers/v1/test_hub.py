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

import httpx
import pytest
import respx
from httpx import AsyncClient, Response

from argilla_server.api.handlers.v1.hub import DATASETS_SERVER_URL
from argilla_server.constants import API_KEY_HEADER_NAME
from tests.factories import AnnotatorFactory


@pytest.mark.asyncio
class TestHubDatasetViewer:
    def url(self, endpoint: str) -> str:
        return f"/api/v1/hub/datasets/{endpoint}"

    async def test_get_info_uses_server_token(
        self, async_client: AsyncClient, owner_auth_header: dict, respx_mock, mocker
    ):
        mocker.patch("argilla_server.api.handlers.v1.hub.get_token", return_value="hf-secret-token")
        respx_mock.get(f"{DATASETS_SERVER_URL}/info").mock(
            return_value=Response(200, json={"dataset_info": {"config_name": "default"}})
        )

        response = await async_client.get(
            self.url("info"),
            params={"dataset": "owner/dataset"},
            headers=owner_auth_header,
        )

        assert response.status_code == 200
        assert response.json() == {"dataset_info": {"config_name": "default"}}
        request, _ = respx.calls.last
        assert request.headers["Authorization"] == "Bearer hf-secret-token"
        assert request.url.params["dataset"] == "owner/dataset"

    @pytest.mark.parametrize("upstream_status", [401, 404])
    async def test_preserves_hugging_face_error_status(
        self, upstream_status: int, async_client: AsyncClient, owner_auth_header: dict, respx_mock, mocker
    ):
        mocker.patch("argilla_server.api.handlers.v1.hub.get_token", return_value=None)
        respx_mock.get(f"{DATASETS_SERVER_URL}/info").mock(
            return_value=Response(upstream_status, json={"error": "Hugging Face error"})
        )

        response = await async_client.get(
            self.url("info"),
            params={"dataset": "owner/dataset"},
            headers=owner_auth_header,
        )

        assert response.status_code == upstream_status
        assert response.json() == {"error": "Hugging Face error"}

    async def test_returns_bad_gateway_when_dataset_viewer_is_unavailable(
        self, async_client: AsyncClient, owner_auth_header: dict, respx_mock, mocker
    ):
        mocker.patch("argilla_server.api.handlers.v1.hub.get_token", return_value=None)
        respx_mock.get(f"{DATASETS_SERVER_URL}/info").mock(side_effect=httpx.ConnectError("Connection failed"))

        response = await async_client.get(
            self.url("info"),
            params={"dataset": "owner/dataset"},
            headers=owner_auth_header,
        )

        assert response.status_code == 502
        assert response.json() == {"detail": "Unable to connect to the Hugging Face dataset viewer"}

    async def test_requires_argilla_authentication(self, async_client: AsyncClient):
        response = await async_client.get(self.url("info"), params={"dataset": "owner/dataset"})

        assert response.status_code == 401

    async def test_rejects_annotators(self, async_client: AsyncClient):
        annotator = await AnnotatorFactory.create()

        response = await async_client.get(
            self.url("info"),
            params={"dataset": "owner/dataset"},
            headers={API_KEY_HEADER_NAME: annotator.api_key},
        )

        assert response.status_code == 403
