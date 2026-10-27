import httpx
import pytest
from sqlalchemy import select

from argilla_server.api.schemas.v1.datasets import HubDatasetMapping
from argilla_server.contexts.hub import HubDataset
from argilla_server.enums import DatasetStatus
from argilla_server.models import Record
from argilla_server.settings import settings
from tests.factories import CustomFieldFactory, DatasetFactory, IntegerMetadataPropertyFactory, TextFieldFactory


@pytest.mark.asyncio
async def test_csghub_import_persists_mapped_records_across_pages(
    db, mock_search_engine, monkeypatch, respx_mock, mocker
):
    monkeypatch.setattr(settings, "csghub_endpoint", "https://csghub.test")
    load_hf = mocker.patch("argilla_server.contexts.hub.load_dataset")
    dataset = await DatasetFactory.create(status=DatasetStatus.ready)
    await TextFieldFactory.create(name="document", required=True, dataset=dataset)
    await CustomFieldFactory.create(name="details", dataset=dataset)
    await IntegerMetadataPropertyFactory.create(name="rank", dataset=dataset)
    await dataset.awaitable_attrs.fields
    await dataset.awaitable_attrs.questions
    await dataset.awaitable_attrs.metadata_properties
    url = "https://csghub.test/api/v1/datasets/owner/repo/dataviewer"
    respx_mock.get(f"{url}/catalog").respond(
        200,
        json={
            "data": {"dataset_info": [{"config_name": "default", "splits": [{"name": "test", "num_examples": 205}]}]}
        },
    )

    def rows(request):
        assert request.url.params["split"] == "test"
        start = (int(request.url.params["page"]) - 1) * 100
        return httpx.Response(
            200,
            json={
                "data": {
                    "columns": ["id", "text", "object", "score"],
                    "total": 205,
                    "rows": [
                        [i, f"line {i}\nsecond line", {"items": [i, None]}, i]
                        for i in range(start, min(start + 100, 205))
                    ],
                }
            },
        )

    respx_mock.get(f"{url}/rows").mock(side_effect=rows)
    mapping = HubDatasetMapping.model_validate(
        {
            "fields": [{"source": "text", "target": "document"}, {"source": "object", "target": "details"}],
            "metadata": [{"source": "score", "target": "rank"}],
            "external_id": "id",
        }
    )
    importer = HubDataset("owner/repo", "default", "test", mapping, source="csghub")
    await importer.take(205).import_to(db, mock_search_engine, dataset)
    records = (await db.execute(select(Record).where(Record.dataset_id == dataset.id))).scalars().all()
    assert len(records) == 205
    indexed = {record.external_id: record for record in records}
    assert set(indexed) == {str(i) for i in range(205)}
    assert indexed["204"].fields == {
        "document": "line 204\nsecond line",
        "details": {"__argilla_raw_value__": {"items": [204, None]}},
    }
    assert indexed["204"].metadata_ == {"rank": 204}
    load_hf.assert_not_called()
    # A job retry updates the same external IDs instead of duplicating rows.
    await importer.take(205).import_to(db, mock_search_engine, dataset)
    assert len((await db.execute(select(Record).where(Record.dataset_id == dataset.id))).scalars().all()) == 205
