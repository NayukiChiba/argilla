import { HUB_REPOSITORY_ERRORS, HubRepository } from "./HubRepository";

describe("HubRepository", () => {
  const createRepository = (get: jest.Mock) => {
    const axios = { get };

    return new HubRepository(axios as any);
  };

  it("loads dataset information through the Argilla server", async () => {
    const get = jest.fn().mockResolvedValue({
      data: { dataset_info: { config_name: "default" } },
    });
    const repository = createRepository(get);

    const result = await repository.getDatasetCreation("owner/dataset");

    expect(result).toEqual({ config_name: "default" });
    expect(get).toHaveBeenCalledWith("/v1/hub/datasets/info", {
      params: { dataset: "owner/dataset" },
      skipGlobalErrorHandler: true,
    });
  });

  it.each([
    [401, HUB_REPOSITORY_ERRORS.AUTHENTICATION_REQUIRED],
    [403, HUB_REPOSITORY_ERRORS.AUTHENTICATION_REQUIRED],
    [404, HUB_REPOSITORY_ERRORS.NOT_EXIST],
    [502, HUB_REPOSITORY_ERRORS.UNAVAILABLE],
  ])("maps status %s to %s", async (status, expected) => {
    const repository = createRepository(
      jest.fn().mockRejectedValue({ response: { status } })
    );

    await expect(
      repository.getDatasetCreation("owner/dataset")
    ).rejects.toEqual({ response: expected });
  });
});
