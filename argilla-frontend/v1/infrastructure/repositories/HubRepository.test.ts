import { HUB_REPOSITORY_ERRORS, HubRepository } from "./HubRepository";

describe("HubRepository", () => {
  it("resolves the full URL before loading metadata", async () => {
    const get = jest
      .fn()
      .mockResolvedValue({ data: { repo_id: "owner/repo", source: "csghub" } });
    const repository = new HubRepository({ get } as any);
    await expect(
      repository.resolveUrl("http://127.0.0.1/datasets/owner/repo")
    ).resolves.toEqual({ repo_id: "owner/repo", source: "csghub" });
    expect(get).toHaveBeenCalledWith(
      "/v1/hub/datasets/resolve",
      expect.objectContaining({
        params: { url: "http://127.0.0.1/datasets/owner/repo" },
      })
    );
  });

  it("keeps CSGHub selected for info, splits and preview requests", async () => {
    const get = jest
      .fn()
      .mockResolvedValueOnce({ data: { dataset_info: { default: {} } } })
      .mockResolvedValueOnce({ data: { splits: [] } })
      .mockResolvedValueOnce({
        data: { rows: [{ row: { text: "CSGHub data" } }] },
      });
    const repository = new HubRepository({ get } as any);
    await repository.getDatasetCreation("owner/repo", "csghub");
    const preview = await repository.getFirstRecord({
      repoId: "owner/repo",
      source: "csghub",
      selectedSubset: { name: "custom", selectedSplit: { name: "test" } },
    } as any);
    expect(preview.record).toEqual({ text: "CSGHub data" });
    for (const [, options] of get.mock.calls) {
      expect(options.params.source).toBe("csghub");
    }
    expect(get.mock.calls[2][1].params).toMatchObject({
      config: "custom",
      split: "test",
    });
  });

  const createRepository = (get: jest.Mock) => {
    const axios = { get };

    return new HubRepository(axios as any);
  };

  it("loads dataset information through the Argilla server", async () => {
    const get = jest
      .fn()
      .mockResolvedValueOnce({
        data: { dataset_info: { config_name: "default" } },
      })
      .mockResolvedValueOnce({ data: { splits: [] } });
    const repository = createRepository(get);

    const result = await repository.getDatasetCreation("owner/dataset");

    expect(result).toEqual({ config_name: "default" });
    expect(get).toHaveBeenCalledWith("/v1/hub/datasets/info", {
      params: { dataset: "owner/dataset" },
      skipGlobalErrorHandler: true,
    });
    expect(get).toHaveBeenCalledWith("/v1/hub/datasets/splits", {
      params: { dataset: "owner/dataset" },
      skipGlobalErrorHandler: true,
    });
  });

  it("completes subsets missing from dataset information with first rows", async () => {
    const get = jest
      .fn()
      .mockResolvedValueOnce({
        data: {
          dataset_info: {
            malicious_skills: {
              config_name: "malicious_skills",
              dataset_name: "malicious_agent_skills_bench",
              features: {
                Pattern: { _type: "Value", dtype: "string" },
              },
              splits: { train: { name: "train" } },
            },
          },
        },
      })
      .mockResolvedValueOnce({
        data: {
          splits: [
            { config: "malicious_skills", split: "train" },
            { config: "skills_dataset", split: "train" },
          ],
        },
      })
      .mockResolvedValueOnce({
        data: {
          features: [
            {
              name: "url",
              type: { _type: "Value", dtype: "string" },
            },
          ],
          rows: [],
        },
      });
    const repository = createRepository(get);

    const result = await repository.getDatasetCreation(
      "ProtectSkills/MaliciousAgentSkillsBench"
    );

    expect(result.skills_dataset).toEqual({
      config_name: "skills_dataset",
      dataset_name: "malicious_agent_skills_bench",
      features: {
        url: { _type: "Value", dtype: "string" },
      },
      splits: {
        train: {
          name: "train",
          dataset_name: "malicious_agent_skills_bench",
        },
      },
    });
    expect(get).toHaveBeenLastCalledWith("/v1/hub/datasets/first-rows", {
      params: {
        dataset: "ProtectSkills/MaliciousAgentSkillsBench",
        config: "skills_dataset",
        split: "train",
      },
      skipGlobalErrorHandler: true,
    });
  });

  it("keeps available dataset information when subset discovery fails", async () => {
    const datasetInfo = {
      default: {
        config_name: "default",
        dataset_name: "dataset",
      },
    };
    const get = jest
      .fn()
      .mockResolvedValueOnce({ data: { dataset_info: datasetInfo } })
      .mockRejectedValueOnce(new Error("Dataset Viewer unavailable"));
    const repository = createRepository(get);

    const result = await repository.getDatasetCreation("owner/dataset");

    expect(result).toEqual(datasetInfo);
  });

  it("loads the first record from the paginated viewer", async () => {
    const get = jest.fn().mockResolvedValueOnce({
      data: { rows: [{ row: { text: "sample" } }] },
    });
    const repository = createRepository(get);
    const dataset = {
      repoId: "owner/dataset",
      selectedSubset: {
        name: "default",
        selectedSplit: { name: "train" },
      },
    } as any;

    await expect(repository.getFirstRecord(dataset)).resolves.toEqual({
      record: { text: "sample" },
      viewerAvailable: true,
    });
    expect(get).toHaveBeenCalledWith("/v1/hub/datasets/rows", {
      params: {
        dataset: "owner/dataset",
        config: "default",
        split: "train",
        offset: 0,
        length: 1,
      },
      skipGlobalErrorHandler: true,
    });
  });

  it("uses cached first rows for fields when the paginated viewer fails", async () => {
    const get = jest
      .fn()
      .mockRejectedValueOnce(new Error("Scan size limit exceeded"))
      .mockResolvedValueOnce({
        data: { rows: [{ row: { text: "cached sample" } }] },
      });
    const repository = createRepository(get);
    const dataset = {
      repoId: "owner/dataset",
      selectedSubset: {
        name: "default",
        selectedSplit: { name: "train" },
      },
    } as any;

    await expect(repository.getFirstRecord(dataset)).resolves.toEqual({
      record: { text: "cached sample" },
      viewerAvailable: false,
    });
    expect(get).toHaveBeenLastCalledWith("/v1/hub/datasets/first-rows", {
      params: {
        dataset: "owner/dataset",
        config: "default",
        split: "train",
      },
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
