import { useResolve } from "ts-injecty";
import { ref, useFetch } from "@nuxtjs/composition-api";
import { HubSource } from "~/v1/domain/entities/hub/DatasetCreation";
import { useRoutes, useFocusTab } from "~/v1/infrastructure/services";
import { GetDatasetCreationUseCase } from "~/v1/domain/usecases/get-dataset-creation-use-case";
import { GetDatasetsUseCase } from "@/v1/domain/usecases/get-datasets-use-case";
import { GetWorkspacesUseCase } from "~/v1/domain/usecases/get-workspaces-use-case";
import { useDatasets } from "~/v1/infrastructure/storage/DatasetsStorage";
import { useRole } from "~/v1/infrastructure/services/useRole";
import { HUB_REPOSITORY_ERRORS } from "~/v1/infrastructure/repositories/HubRepository";

export const useHomeViewModel = () => {
  const workspaces = ref<any[]>([]);
  const getWorkspacesUseCase = useResolve(GetWorkspacesUseCase);
  const { isAdminOrOwnerRole } = useRole();
  const isLoadingDatasets = ref(false);
  const { goToImportDatasetFromHub } = useRoutes();
  const { state: datasets } = useDatasets();
  const getDatasetsUseCase = useResolve(GetDatasetsUseCase);
  const getDatasetCreationUseCase = useResolve(GetDatasetCreationUseCase);
  const error = ref("");

  const getNewDatasetByUrl = async (url: string) => {
    error.value = "";
    try {
      const { repo_id: repoId, source } =
        await getDatasetCreationUseCase.resolveUrl(url);
      await getNewDatasetByRepoId(repoId, source);
    } catch {
      error.value = "datasetCreation.invalidHubUrl";
    }
  };

  useFocusTab(async () => {
    await onLoadDatasets();
  });

  useFetch(async () => {
    loadDatasets();
    workspaces.value = await getWorkspacesUseCase.execute();
  });

  const getNewDatasetByRepoId = async (
    repositoryId: string,
    source: HubSource = "huggingface"
  ) => {
    error.value = "";
    try {
      await getDatasetCreationUseCase.execute(repositoryId, source);
      goToImportDatasetFromHub(repositoryId, source);
    } catch (cause: any) {
      const messages = {
        [HUB_REPOSITORY_ERRORS.NOT_EXIST]: "datasetCreation.cantLoadRepository",
        [HUB_REPOSITORY_ERRORS.AUTHENTICATION_REQUIRED]:
          "datasetCreation.hubAuthenticationRequired",
        [HUB_REPOSITORY_ERRORS.UNAVAILABLE]: "datasetCreation.hubUnavailable",
      };

      error.value =
        source === "csghub"
          ? "datasetCreation.csghubUnavailable"
          : messages[cause.response] ?? "datasetCreation.hubUnavailable";
    }
  };

  const exampleDatasets = [
    {
      repoId: "stanfordnlp/imdb",
      task: "Text Classification",
      tags: ["sentiment-classification"],
      icon: "text-classification",
      color: "hsl(25, 95%, 53%)",
      rows: "100K",
    },
    {
      repoId: "databricks/databricks-dolly-15k",
      task: "Question answering",
      tags: ["instruction-dataset", "rag"],
      icon: "question-answering",
      color: "hsl(217, 91%, 60%)",
      rows: "15K",
    },
    {
      repoId: "dvilasuero/finepersonas-v0.1-tiny-flux-schnell",
      task: "Text to Image",
      tags: ["synthetic", "rlaif"],
      icon: "text-to-image",
      color: "hsl(38, 92%, 50%)",
      rows: "350",
    },
  ];

  const onLoadDatasets = async () => {
    await getDatasetsUseCase.execute();
  };

  const loadDatasets = async () => {
    isLoadingDatasets.value = true;

    await onLoadDatasets();

    isLoadingDatasets.value = false;
  };

  return {
    getNewDatasetByUrl,
    datasets,
    workspaces,
    isLoadingDatasets,
    getNewDatasetByRepoId,
    isAdminOrOwnerRole,
    exampleDatasets,
    error,
  };
};
