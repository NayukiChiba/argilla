import { type NuxtAxiosInstance } from "@nuxtjs/axios";
import { PublicNuxtAxiosInstance } from "../services";
import {
  DatasetCreation,
  HubSource,
} from "~/v1/domain/entities/hub/DatasetCreation";

export const enum HUB_REPOSITORY_ERRORS {
  NOT_EXIST = "ERROR_FETCHING_DATASET",
  AUTHENTICATION_REQUIRED = "HUGGING_FACE_AUTHENTICATION_REQUIRED",
  UNAVAILABLE = "HUGGING_FACE_UNAVAILABLE",
  INVALID_URL = "INVALID_HUB_DATASET_URL",
}

type HubSplit = {
  config: string;
  split: string;
};

type HubFirstRowsFeature = {
  name: string;
  type: unknown;
};

export type HubPreview = {
  record: Record<string, unknown>;
  viewerAvailable: boolean;
};

export class HubRepository {
  private axios: NuxtAxiosInstance;
  constructor(axios: PublicNuxtAxiosInstance) {
    this.axios = axios;
  }

  async resolveUrl(
    url: string
  ): Promise<{ repo_id: string; source: HubSource }> {
    try {
      const { data } = await this.axios.get("/v1/hub/datasets/resolve", {
        params: { url },
        skipGlobalErrorHandler: true,
      } as any);
      return data;
    } catch {
      throw { response: HUB_REPOSITORY_ERRORS.INVALID_URL };
    }
  }

  async getExportTarget(
    source: HubSource
  ): Promise<{ source: HubSource; endpoint: string }> {
    const { data } = await this.axios.get("/v1/hub/datasets/export-target", {
      params: { source },
      skipGlobalErrorHandler: true,
    } as any);
    return data;
  }

  async getDatasetCreation(
    repoId: string,
    source: HubSource = "huggingface"
  ): Promise<any> {
    try {
      const { data } = await this.axios.get("/v1/hub/datasets/info", {
        params: { dataset: repoId, ...(source === "csghub" ? { source } : {}) },
        skipGlobalErrorHandler: true,
      } as any);

      return await this.completeMissingSubsets(
        repoId,
        data.dataset_info,
        source
      );
    } catch (e: any) {
      const status = e.response?.status;
      const response =
        status === 401 || status === 403
          ? HUB_REPOSITORY_ERRORS.AUTHENTICATION_REQUIRED
          : status === 404
          ? HUB_REPOSITORY_ERRORS.NOT_EXIST
          : HUB_REPOSITORY_ERRORS.UNAVAILABLE;

      throw {
        response,
      };
    }
  }

  private async completeMissingSubsets(
    repoId: string,
    datasetInfo: any,
    source: HubSource
  ) {
    let splits: HubSplit[];

    try {
      const { data } = await this.axios.get("/v1/hub/datasets/splits", {
        params: { dataset: repoId, ...(source === "csghub" ? { source } : {}) },
        skipGlobalErrorHandler: true,
      } as any);
      splits = data.splits;
    } catch {
      return datasetInfo;
    }

    const completedDatasetInfo = { ...datasetInfo };
    const splitsByConfig = splits.reduce((result, { config, split }) => {
      const configSplits = result.get(config) ?? [];
      configSplits.push(split);
      result.set(config, configSplits);

      return result;
    }, new Map<string, string[]>());

    for (const [config, configSplits] of splitsByConfig) {
      if (completedDatasetInfo[config]) continue;

      try {
        const split = configSplits[0];
        const { data } = await this.axios.get("/v1/hub/datasets/first-rows", {
          params: {
            dataset: repoId,
            config,
            split,
            ...(source === "csghub" ? { source } : {}),
          },
          skipGlobalErrorHandler: true,
        } as any);
        const datasetName =
          Object.values<any>(completedDatasetInfo)[0]?.dataset_name ??
          repoId.split("/").pop();

        completedDatasetInfo[config] = {
          config_name: config,
          dataset_name: datasetName,
          features: Object.fromEntries(
            data.features.map(({ name, type }: HubFirstRowsFeature) => [
              name,
              type,
            ])
          ),
          splits: Object.fromEntries(
            configSplits.map((name) => [
              name,
              { name, dataset_name: datasetName },
            ])
          ),
        };
      } catch {
        // A failed subset should not prevent importing the remaining subsets.
      }
    }

    return completedDatasetInfo;
  }

  async getColumnsDistributions(
    repoId: string,
    subset: string,
    split: string,
    source: HubSource = "huggingface"
  ): Promise<any> {
    // Example call https://datasets-server.huggingface.co/statistics?dataset=derek-thomas/ScienceQA&config=default&split=train
    const { data } = await this.axios.get("/v1/hub/datasets/statistics", {
      params: {
        dataset: repoId,
        ...(source === "csghub" ? { source } : {}),
        config: subset,
        split,
      },
      skipGlobalErrorHandler: true,
    } as any);

    const distributions = [];
    for (const columnStats of data.statistics) {
      const columnDistribution = {
        name: columnStats.column_name,
        type: columnStats.column_type,
        values: null,
      };

      const stats = columnStats.column_statistics;

      switch (columnDistribution.type) {
        // Helpful for ratings
        case "int":
          columnDistribution.values = { min: stats.min, max: stats.max };
          break;
        // Helpful for label questions or terms metadata
        case "string_label":
          columnDistribution.values = [];
          for (const key of stats.frequencies) {
            columnDistribution.values.push(key);
          }
          break;
        default:
          // For other cases, the values will be null
          break;
      }
      distributions.push(columnDistribution);
    }

    return distributions;
  }

  async getFirstRecord(dataset: DatasetCreation): Promise<HubPreview> {
    const { repoId, selectedSubset, source } = dataset;
    const params = {
      dataset: repoId,
      ...(source === "csghub" ? { source } : {}),
      split: selectedSubset.selectedSplit.name,
      config: selectedSubset.name,
    };

    try {
      const { data } = await this.axios.get("/v1/hub/datasets/rows", {
        params: { ...params, offset: 0, length: 1 },
        skipGlobalErrorHandler: true,
      } as any);

      return { record: data.rows[0]?.row ?? {}, viewerAvailable: true };
    } catch {
      try {
        const { data } = await this.axios.get("/v1/hub/datasets/first-rows", {
          params,
          skipGlobalErrorHandler: true,
        } as any);

        return { record: data.rows[0]?.row ?? {}, viewerAvailable: false };
      } catch {
        return { record: {}, viewerAvailable: false };
      }
    }
  }
}
