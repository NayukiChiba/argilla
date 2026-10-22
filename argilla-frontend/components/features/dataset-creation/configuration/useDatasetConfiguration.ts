import { useResolve } from "ts-injecty";
import { ref } from "vue";
import { GetFirstRecordFromHub } from "~/v1/domain/usecases/get-first-record-from-hub";

export const useDatasetConfiguration = () => {
  const firstRecord = ref(null);
  const viewerAvailable = ref<boolean | null>(null);
  const getFirstRecordUseCase = useResolve(GetFirstRecordFromHub);

  const getFirstRecord = async (dataset: any) => {
    firstRecord.value = null;
    viewerAvailable.value = null;

    const preview = await getFirstRecordUseCase.execute(dataset);
    firstRecord.value = preview.record;
    viewerAvailable.value = preview.viewerAvailable;
  };

  return {
    firstRecord,
    viewerAvailable,
    getFirstRecord,
  };
};
