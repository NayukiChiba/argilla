import { HubSource } from "../entities/hub/DatasetCreation";
import { DatasetCreationBuilder } from "../entities/hub/DatasetCreationBuilder";
import { HubRepository } from "~/v1/infrastructure/repositories/HubRepository";

export class GetDatasetCreationUseCase {
  constructor(private readonly hubRepository: HubRepository) {}

  resolveUrl(url: string) {
    return this.hubRepository.resolveUrl(url);
  }

  async execute(repoId: string, source: HubSource = "huggingface") {
    const datasetInfo = await this.hubRepository.getDatasetCreation(
      repoId,
      source
    );

    const datasetCreation = new DatasetCreationBuilder(
      repoId,
      datasetInfo,
      source
    );

    return datasetCreation.build();
  }
}
