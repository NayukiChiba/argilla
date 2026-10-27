import { DatasetRepository } from "./DatasetRepository";

describe("DatasetRepository CSGHub import", () => {
  it("keeps the source, subset, split and mapping in metadata and the worker request", async () => {
    const post = jest.fn().mockResolvedValue({ data: { id: "created-id" } });
    const repository = new DatasetRepository({ post });
    const creation = {
      source: "csghub",
      repoId: "owner/repo",
      name: "imported",
      workspace: { id: "workspace-id" },
      selectedSubset: { name: "chat", selectedSplit: { name: "test" } },
      mappings: { fields: [{ source: "messages", target: "conversation" }] },
    };
    await repository.create(creation);
    expect(post.mock.calls[0][1].metadata).toEqual(
      expect.objectContaining({
        source: "csghub",
        subset: "chat",
        split: "test",
        mapping: creation.mappings,
      })
    );
    await repository.import("created-id", creation);
    expect(post.mock.calls[1]).toEqual([
      "/v1/datasets/created-id/import",
      {
        source: "csghub",
        name: "owner/repo",
        subset: "chat",
        split: "test",
        mapping: creation.mappings,
      },
    ]);
  });
});
