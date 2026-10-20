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

from typing import Dict

import httpx
from fastapi import APIRouter, HTTPException, Query, Security, status
from fastapi.responses import Response
from huggingface_hub import get_token

from argilla_server.api.policies.v1 import HubPolicy, authorize
from argilla_server.models import User
from argilla_server.security import auth

DATASETS_SERVER_URL = "https://datasets-server.huggingface.co"
DATASETS_SERVER_TIMEOUT = 30.0

router = APIRouter(prefix="/hub/datasets", tags=["hub"])


async def _proxy_dataset_viewer(endpoint: str, params: Dict[str, str]) -> Response:
    headers = {}
    token = get_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=DATASETS_SERVER_TIMEOUT) as client:
            upstream = await client.get(f"{DATASETS_SERVER_URL}/{endpoint}", params=params, headers=headers)
    except httpx.RequestError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to connect to the Hugging Face dataset viewer",
        ) from error

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers={"content-type": upstream.headers.get("content-type", "application/json")},
    )


async def _authorize_hub_access(current_user: User) -> None:
    await authorize(current_user, HubPolicy.access())


@router.get("/info")
async def get_dataset_info(
    dataset: str = Query(..., min_length=1),
    current_user: User = Security(auth.get_current_user),
) -> Response:
    await _authorize_hub_access(current_user)
    return await _proxy_dataset_viewer("info", {"dataset": dataset})


@router.get("/statistics")
async def get_dataset_statistics(
    dataset: str = Query(..., min_length=1),
    config: str = Query(..., min_length=1),
    split: str = Query(..., min_length=1),
    current_user: User = Security(auth.get_current_user),
) -> Response:
    await _authorize_hub_access(current_user)
    return await _proxy_dataset_viewer("statistics", {"dataset": dataset, "config": config, "split": split})


@router.get("/first-rows")
async def get_dataset_first_rows(
    dataset: str = Query(..., min_length=1),
    config: str = Query(..., min_length=1),
    split: str = Query(..., min_length=1),
    current_user: User = Security(auth.get_current_user),
) -> Response:
    await _authorize_hub_access(current_user)
    return await _proxy_dataset_viewer("first-rows", {"dataset": dataset, "config": config, "split": split})
