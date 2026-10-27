"""Access the configured dataset sources through the Argilla server."""

from argilla._api._base import ResourceAPI
from argilla._exceptions._api import api_error_handler


class HubAPI(ResourceAPI):
    @api_error_handler
    def resolve(self, url: str) -> dict:
        response = self.http_client.get("/api/v1/hub/datasets/resolve", params={"url": url})
        response.raise_for_status()
        return response.json()

    @api_error_handler
    def info(self, repo_id: str, source: str = "huggingface") -> dict:
        response = self.http_client.get("/api/v1/hub/datasets/info", params={"dataset": repo_id, "source": source})
        response.raise_for_status()
        return response.json()["dataset_info"]

    @api_error_handler
    def rows(self, repo_id: str, subset: str, split: str, source: str, offset: int, length: int = 100) -> dict:
        response = self.http_client.get(
            "/api/v1/hub/datasets/rows",
            params={
                "dataset": repo_id,
                "source": source,
                "config": subset,
                "split": split,
                "offset": offset,
                "length": length,
            },
        )
        response.raise_for_status()
        return response.json()

    def iter_batches(self, repo_id: str, subset: str, split: str, source: str = "csghub", max_records=None):
        if max_records is not None and (
            not isinstance(max_records, int) or isinstance(max_records, bool) or max_records < 0
        ):
            raise ValueError("max_records must be a non-negative integer")
        offset = 0
        while max_records is None or offset < max_records:
            length = min(100, max_records - offset) if max_records is not None else 100
            page = self.rows(repo_id, subset, split, source, offset, length)
            rows = [item["row"] for item in page["rows"]]
            if not rows:
                break
            yield rows
            offset += len(rows)
            total = page.get("num_rows_total")
            if len(rows) < length or (total is not None and offset >= total):
                break
