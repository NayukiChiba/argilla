import { useResolve } from "ts-injecty";
import { ref, useRoute, useContext } from "@nuxtjs/composition-api";
import { HubSource } from "~/v1/domain/entities/hub/DatasetCreation";
import { GetDatasetCreationUseCase } from "~/v1/domain/usecases/get-dataset-creation-use-case";

export const useNewDatasetViewModel = () => {
  const { error } = useContext();
  const route = useRoute();
  const datasetConfig = ref();
  const getDatasetCreationUseCase = useResolve(GetDatasetCreationUseCase);

  const getNewDatasetByRepoId = async (repositoryId: string) => {
    const source: HubSource =
      route.value.query.source === "csghub" ? "csghub" : "huggingface";
    try {
      datasetConfig.value = await getDatasetCreationUseCase.execute(
        repositoryId,
        source
      );
    } catch (e) {
      error({ statusCode: 404, message: "Cannot fetch the dataset" });
    }
  };

  const getNewDatasetByRepoIdFromUrl = async () => {
    const repositoryId = route.value.params.id;
    await getNewDatasetByRepoId(repositoryId);
    const { subset, split } = route.value.query;
    if (
      datasetConfig.value &&
      typeof subset === "string" &&
      datasetConfig.value.subsets.includes(subset)
    ) {
      datasetConfig.value.changeSubset(subset);
    }
    if (datasetConfig.value && typeof split === "string") {
      const selectedSplit = datasetConfig.value.selectedSubset.splits.find(
        (s) => s.name === split
      );
      if (selectedSplit)
        datasetConfig.value.selectedSubset.selectedSplit = selectedSplit;
    }
  };

  const changeSubset = (name: string) => {
    datasetConfig.value.changeSubset(name);
  };

  return {
    getNewDatasetByRepoId,
    getNewDatasetByRepoIdFromUrl,
    changeSubset,
    datasetConfig,
  };
};
