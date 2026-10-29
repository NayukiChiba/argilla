import { useResolve } from "ts-injecty";
import { onBeforeMount, ref, computed, watch } from "vue";
import { Dataset } from "~/v1/domain/entities/dataset/Dataset";
import { DatasetExportSource } from "~/v1/domain/entities/dataset/DatasetExport";
import { ExportDatasetToHubUseCase } from "~/v1/domain/usecases/export-dataset-to-hub-use-case";
import { HubRepository, JobRepository } from "~/v1/infrastructure/repositories";
import {
  useDebounce,
  useLocalStorage,
  useNotifications,
} from "~/v1/infrastructure/services";

interface ExportToHubProps {
  dataset: Dataset;
}

interface DatasetExporting {
  jobId: string;
  datasetName: string;
  source?: DatasetExportSource;
}

export const useExportToHubViewModel = (props: ExportToHubProps) => {
  const { dataset } = props;
  const notify = useNotifications();
  const debounce = useDebounce(3000);
  const { get, set } = useLocalStorage();

  const isDialogOpen = ref(false);
  const isDialogHovered = ref(false);
  const errors = ref({
    orgOrUsername: [],
    datasetName: [],
    hfToken: [],
  });
  const exportToHubForm = ref({
    source: "huggingface" as DatasetExportSource,
    orgOrUsername: "",
    datasetName: "",
    hfToken: "",
    isPrivate: false,
  });

  const exportToHubUseCase = useResolve(ExportDatasetToHubUseCase);
  const jobRepository = useResolve(JobRepository);
  const hubRepository = useResolve(HubRepository);

  const validate = () => {
    const regex = /hf_[A-Za-z0-9]+/i;
    const validations = {
      orgOrUsername: [],
      datasetName: [],
      hfToken: [],
    };
    if (!exportToHubForm.value.orgOrUsername) {
      validations.orgOrUsername.push(
        "exportToHub.validations.orgOrUsernameIsRequired"
      );
    }
    if (!exportToHubForm.value.datasetName) {
      validations.datasetName.push(
        "exportToHub.validations.datasetNameIsRequired"
      );
    }
    if (!exportToHubForm.value.hfToken) {
      validations.hfToken.push(
        exportToHubForm.value.source === "csghub"
          ? "exportToHub.validations.csghubTokenIsRequired"
          : "exportToHub.validations.hfTokenIsRequired"
      );
    } else if (
      exportToHubForm.value.source === "huggingface" &&
      !regex.test(exportToHubForm.value.hfToken)
    ) {
      validations.hfToken.push("exportToHub.validations.hfTokenInvalid");
    }
    return validations;
  };

  const validateForm = (input: string) => {
    errors.value[input] = validate()[input];
  };

  const isValid = computed(() => {
    const validations = validate();
    return (
      validations.orgOrUsername.length === 0 &&
      validations.datasetName.length === 0 &&
      validations.hfToken.length === 0
    );
  });

  const getDatasetExporting = () =>
    get<Record<string, DatasetExporting>>("datasetExportJobIds") ?? {};

  const isExporting = ref(!!getDatasetExporting()[dataset.id]);

  const openExportedDataset = async (exported: DatasetExporting) => {
    if (exported.source === "csghub") {
      try {
        const { endpoint } = await hubRepository.getExportTarget("csghub");
        window.open(`${endpoint}/datasets/${exported.datasetName}`, "_blank");
        return;
      } catch {}
    }
    window.open(
      `https://huggingface.co/datasets/${exported.datasetName}`,
      "_blank"
    );
  };

  const verifyExportStatus = async () => {
    try {
      const datasetExporting = getDatasetExporting();
      const exporting = datasetExporting[dataset.id];

      if (!exporting) return;

      const { jobId, datasetName, source } = exporting;

      const job = await jobRepository.getJobStatus(jobId);

      if (job.isRunning) return;

      isExporting.value = job.isRunning;

      delete datasetExporting[dataset.id];

      set("datasetExportJobIds", datasetExporting);

      notify.notify({
        type: job.isFinished ? "success" : "danger",
        message: job.isFinished ? "Dataset exported to Hub" : "Export failed",
        buttonText: job.isFinished ? "Go to Hub" : undefined,
        onClick: job.isFinished
          ? () => openExportedDataset({ jobId, datasetName, source })
          : undefined,
        permanent: true,
      });
    } catch {}
  };

  const watchExportStatus = async () => {
    while (isExporting.value) {
      await debounce.wait();

      await verifyExportStatus();
    }

    debounce.stop();
  };

  const exportToHub = async () => {
    try {
      isExporting.value = true;

      await exportToHubUseCase.execute(dataset, {
        name: `${exportToHubForm.value.orgOrUsername}/${exportToHubForm.value.datasetName}`,
        isPrivate: exportToHubForm.value.isPrivate,
        hfToken: exportToHubForm.value.hfToken,
        source: exportToHubForm.value.source,
      });

      watchExportStatus();
    } catch {
      closeDialog();
      isExporting.value = false;
    }
  };

  const openDialog = () => {
    exportToHubForm.value = {
      source: "huggingface",
      orgOrUsername: "",
      datasetName: dataset.name,
      hfToken: "",
      isPrivate: false,
    };

    isDialogOpen.value = true;
  };

  const closeDialog = () => {
    isDialogOpen.value = false;
    isDialogHovered.value = false;
  };

  const openDialogOnHover = () => {
    if (isExporting.value) {
      isDialogHovered.value = true;
    }
  };

  const closeDialogOnLeave = () => {
    if (isExporting.value && !isDialogOpen.value) {
      isDialogHovered.value = false;
    }
  };

  const isDialogVisible = computed(
    () => isDialogOpen.value || isDialogHovered.value
  );

  watch(isExporting, (newValue) => {
    if (!newValue) {
      closeDialog();
    }
  });

  onBeforeMount(() => {
    watchExportStatus();
  });

  return {
    isDialogVisible,
    closeDialog,
    openDialog,
    openDialogOnHover,
    closeDialogOnLeave,
    isExporting,
    exportToHub,
    exportToHubForm,
    validateForm,
    errors,
    isValid,
  };
};
