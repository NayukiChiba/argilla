import { HUB_REPOSITORY_ERRORS, HubRepository } from "./HubRepository";

describe("HubRepository", () => {
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
