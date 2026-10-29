"""CSGHub's native dataset viewer, normalized to the Hub import contract.

Both the WebUI/worker and the Python SDK use this adapter through Argilla.
Credentials and the trusted upstream address stay on the server.
"""

import math
import re
from typing import Literal
from urllib.parse import quote, unquote, urlsplit

import httpx

from argilla_server.settings import settings

HubSource = Literal["huggingface", "csghub"]
PAGE_SIZE = 100
INTEGER_TYPES = {"TINYINT", "SMALLINT", "INTEGER", "INT", "BIGINT", "INT32", "INT64"}
FLOAT_TYPES = {"FLOAT", "DOUBLE", "FLOAT32", "FLOAT64"}


class CSGHubError(ValueError):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def validate_csghub_repo(repo_id: str) -> str:
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo_id) or any(p in (".", "..") for p in repo_id.split("/")):
        raise CSGHubError("Use a CSGHub repository ID in namespace/name format")
    return "/".join(quote(part, safe="") for part in repo_id.split("/"))


def validate_endpoint(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.query
        or parsed.fragment
    ):
        raise CSGHubError("Configure ARGILLA_CSGHUB_ENDPOINT on the Argilla server and worker", 503)
    return endpoint


def csghub_configuration():
    endpoint = validate_endpoint(settings.csghub_endpoint or "")
    if settings.csghub_internal_endpoint:
        endpoint = validate_endpoint(settings.csghub_internal_endpoint)
    token = settings.csghub_token.get_secret_value() if settings.csghub_token else ""
    return endpoint, {"Authorization": f"Bearer {token}"} if token else {}


def csghub_public_endpoint() -> str:
    """Public CSGHub origin advertised to clients pushing datasets back."""
    return validate_endpoint(settings.csghub_endpoint or "")


CSGHUB_HF_API_PREFIX = "/hf"


def csghub_sdk_endpoint(internal: bool = False) -> str:
    """HF-compatible SDK base URL (create repo, dataset info, LFS and resolve endpoints)."""
    endpoint = csghub_public_endpoint()
    if internal and settings.csghub_internal_endpoint:
        endpoint = validate_endpoint(settings.csghub_internal_endpoint)
    return endpoint.rstrip("/") + CSGHUB_HF_API_PREFIX


def resolve_dataset_url(url: str) -> dict:
    """Resolve a dataset page URL without requesting user-supplied hosts."""
    parsed = urlsplit(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise CSGHubError("Enter a complete dataset URL, including its domain")
    if parsed.query or parsed.fragment:
        raise CSGHubError("Use the dataset root URL without query parameters or fragments")

    def origin(parts):
        return parts.scheme, parts.hostname, parts.port or (443 if parts.scheme == "https" else 80)

    if origin(parsed) == ("https", "huggingface.co", 443):
        source, prefix = "huggingface", "/datasets/"
    else:
        endpoint = validate_endpoint(settings.csghub_endpoint or "")
        configured = urlsplit(endpoint)
        if origin(parsed) != origin(configured):
            raise CSGHubError("The dataset URL must belong to huggingface.co or ARGILLA_CSGHUB_ENDPOINT")
        source, prefix = "csghub", configured.path.rstrip("/") + "/datasets/"

    path = parsed.path.rstrip("/")
    if not path.startswith(prefix):
        raise CSGHubError("Use a dataset page URL ending in /datasets/namespace/name")
    repo_id = unquote(path[len(prefix) :])
    validate_csghub_repo(repo_id)
    return {"repo_id": repo_id, "source": source}


def feature_for_column(type_name: str, values: list):
    """Keep scalar types; inspect nested values without flattening their contents."""
    kind = type_name.upper()
    if kind in ("BOOLEAN", "BOOL"):
        return {"_type": "Value", "dtype": "bool"}
    if kind in INTEGER_TYPES:
        return {"_type": "Value", "dtype": "int64"}
    if kind in FLOAT_TYPES or kind.startswith("DECIMAL"):
        return {"_type": "Value", "dtype": "float64"}
    if kind in ("VARCHAR", "STRING", "TEXT", "UTF8"):
        return {"_type": "Value", "dtype": "string"}
    value = next((value for value in values if value is not None), None)
    if isinstance(value, bool):
        return {"_type": "Value", "dtype": "bool"}
    if isinstance(value, int):
        return {"_type": "Value", "dtype": "int64"}
    if isinstance(value, float):
        return {"_type": "Value", "dtype": "float64"}
    if isinstance(value, str):
        return {"_type": "Value", "dtype": "string"}
    if isinstance(value, list):
        return [feature_for_column("", [item for row in values if isinstance(row, list) for item in row])]
    if isinstance(value, dict):
        keys = dict.fromkeys(key for row in values if isinstance(row, dict) for key in row)
        return {key: feature_for_column("", [row.get(key) for row in values if isinstance(row, dict)]) for key in keys}
    return {"_type": "Json"}


def decode_column_value(value, type_name: str):
    """Restore typed scalars serialized as strings by CSGHub's Parquet viewer."""
    if not isinstance(value, str):
        return value
    kind = type_name.upper()
    if kind in INTEGER_TYPES and re.fullmatch(r"[+-]?[0-9]+", value):
        return int(value)
    if kind in FLOAT_TYPES or kind.startswith("DECIMAL"):
        try:
            number = float(value)
            if math.isfinite(number):
                return number
        except ValueError:
            pass
    if kind in ("BOOLEAN", "BOOL") and value.lower() in ("true", "false"):
        return value.lower() == "true"
    if kind in INTEGER_TYPES | FLOAT_TYPES | {"BOOLEAN", "BOOL"} or kind.startswith("DECIMAL"):
        raise CSGHubError("CSGHub returned a value incompatible with its declared column type", 502)
    return value


class CSGHubSource:
    def __init__(self, repo_id: str):
        self.repo_id = repo_id
        repo_path = validate_csghub_repo(repo_id)
        endpoint, self.headers = csghub_configuration()
        self.url = f"{endpoint}/api/v1/datasets/{repo_path}/dataviewer"

    async def _get(self, client: httpx.AsyncClient, path: str, **params):
        response = await client.get(f"{self.url}/{path}", params=params, headers=self.headers)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise CSGHubError("CSGHub returned an invalid dataset viewer response", 502)
        return data

    async def catalog(self, client: httpx.AsyncClient):
        catalog = await self._get(client, "catalog")
        if not catalog.get("dataset_info"):
            raise CSGHubError("The CSGHub dataset viewer is not ready. Prepare its data preview in CSGHub first.", 409)
        return catalog["dataset_info"]

    async def info(self, client: httpx.AsyncClient):
        result = {}
        for config in await self.catalog(client):
            name = config["config_name"]
            splits = config.get("splits") or []
            if not splits:
                continue
            sample = await self._get(client, "rows", config=name, split=splits[0]["name"], page=1, per=10)
            columns, rows = self._decode_rows(sample)
            types = sample.get("columns_type") or []
            result[name] = {
                "config_name": name,
                "dataset_name": self.repo_id.split("/")[-1],
                "features": {
                    column: feature_for_column(types[index] if index < len(types) else "", [r[column] for r in rows])
                    for index, column in enumerate(columns)
                },
                "splits": {
                    split["name"]: {"name": split["name"], "num_examples": split.get("num_examples")}
                    for split in splits
                },
            }
        if not result:
            raise CSGHubError("The CSGHub dataset has no available subsets or splits", 409)
        return {"dataset_info": result}

    @staticmethod
    def _decode_rows(data):
        columns = data.get("columns")
        rows = data.get("rows")
        if (
            not isinstance(columns, list)
            or not all(isinstance(column, str) for column in columns)
            or not isinstance(rows, list)
            or len(set(columns)) != len(columns)
        ):
            raise CSGHubError("CSGHub returned an invalid row schema", 502)
        if any(not isinstance(row, list) or len(row) != len(columns) for row in rows):
            raise CSGHubError("CSGHub row values do not match the column schema", 502)
        types = data.get("columns_type") or []
        if not isinstance(types, list) or not all(isinstance(kind, str) for kind in types):
            raise CSGHubError("CSGHub returned invalid column types", 502)
        return columns, [
            {
                column: decode_column_value(value, types[index] if index < len(types) else "")
                for index, (column, value) in enumerate(zip(columns, row))
            }
            for row in rows
        ]

    async def rows(self, client, config, split, offset=0, length=1):
        result = []
        total = None
        while len(result) < length:
            position = offset + len(result)
            data = await self._get(
                client, "rows", config=config, split=split, page=position // PAGE_SIZE + 1, per=PAGE_SIZE
            )
            _, page = self._decode_rows(data)
            total = data.get("total")
            if total is not None and (type(total) is not int or total < 0):
                raise CSGHubError("CSGHub returned an invalid row count", 502)
            remaining = page[position % PAGE_SIZE : position % PAGE_SIZE + length - len(result)]
            result.extend(remaining)
            if not remaining or len(page) < PAGE_SIZE or (total is not None and offset + len(result) >= total):
                break
        return {"rows": [{"row_idx": offset + i, "row": row} for i, row in enumerate(result)], "num_rows_total": total}

    async def batches(self, config, split, limit=None):
        async with httpx.AsyncClient(timeout=30.0) as client:
            catalog = await self.catalog(client)
            valid = any(
                c["config_name"] == config and any(s["name"] == split for s in c.get("splits", [])) for c in catalog
            )
            if not valid:
                raise CSGHubError("Unknown CSGHub subset or split")
            offset = 0
            while limit is None or offset < limit:
                length = min(PAGE_SIZE, limit - offset) if limit is not None else PAGE_SIZE
                page = await self.rows(client, config, split, offset, length)
                rows = [item["row"] for item in page["rows"]]
                if not rows:
                    break
                yield rows
                offset += len(rows)
                total = page["num_rows_total"]
                if len(rows) < length or (total is not None and offset >= total):
                    break

    async def viewer(self, endpoint, params):
        async with httpx.AsyncClient(timeout=30.0) as client:
            if endpoint == "info":
                return await self.info(client)
            if endpoint == "splits":
                return {
                    "splits": [
                        {"dataset": self.repo_id, "config": c["config_name"], "split": s["name"]}
                        for c in await self.catalog(client)
                        for s in c.get("splits", [])
                    ]
                }
            if endpoint == "statistics":
                # CSGHub has no equivalent statistics API. Do not invent distributions.
                return {"statistics": []}
            return await self.rows(
                client, params["config"], params["split"], int(params.get("offset", 0)), int(params.get("length", 1))
            )
