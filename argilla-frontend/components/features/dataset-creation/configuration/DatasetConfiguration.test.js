import { shallowMount } from "@vue/test-utils";
import DatasetConfiguration from "./DatasetConfiguration.vue";

jest.mock("./useDatasetConfiguration", () => ({
  useDatasetConfiguration: () => ({
    firstRecord: { text: "hello" },
    viewerAvailable: true,
    getFirstRecord: jest.fn(),
  }),
}));

describe("DatasetConfiguration sources", () => {
  const stubs = {
    HorizontalResizable: { template: '<div><slot name="down" /></div>' },
    VerticalResizable: { template: '<div><slot name="left" /></div>' },
  };
  const dataset = (source) => ({
    source,
    repoId: "owner/repo",
    mappedFields: [],
    questions: [],
    selectedSubset: { name: "default", selectedSplit: { name: "train" } },
  });

  it("does not construct a Hugging Face iframe for CSGHub", () => {
    const wrapper = shallowMount(DatasetConfiguration, {
      propsData: { dataset: dataset("csghub") },
      stubs,
      mocks: { $t: (key) => key },
    });
    expect(wrapper.vm.datasetViewerUrl).toBeNull();
    expect(wrapper.find("iframe").exists()).toBe(false);
    expect(wrapper.find(".dataset-config__raw-preview").text()).toContain(
      "hello"
    );
  });

  it("retains the Hugging Face embed for Hugging Face datasets", () => {
    const wrapper = shallowMount(DatasetConfiguration, {
      propsData: { dataset: dataset("huggingface") },
      stubs,
      mocks: { $t: (key) => key },
    });
    expect(wrapper.vm.datasetViewerUrl).toBe(
      "https://huggingface.co/datasets/owner/repo/embed/viewer/default/train"
    );
  });
});
