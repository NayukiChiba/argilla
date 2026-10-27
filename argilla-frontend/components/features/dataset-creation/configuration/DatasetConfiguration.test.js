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

  it("embeds CSGHub through the authenticated local viewer and follows subset/split selection", async () => {
    const resolve = jest.fn(({ path, query }) => ({
      href: `/argilla${path}?${new URLSearchParams(query)}`,
    }));
    const wrapper = shallowMount(DatasetConfiguration, {
      propsData: { dataset: dataset("csghub") },
      stubs,
      mocks: { $t: (key) => key, $router: { resolve } },
    });
    expect(wrapper.find("iframe").attributes("src")).toBe(
      "/argilla/dataset-viewer/csghub?dataset=owner%2Frepo&config=default&split=train"
    );
    const changed = dataset("csghub");
    changed.selectedSubset = {
      name: "subset / two",
      selectedSplit: { name: "test" },
    };
    await wrapper.setProps({ dataset: changed });
    expect(wrapper.find("iframe").attributes("src")).toContain(
      "config=subset+%2F+two&split=test"
    );
    expect(wrapper.find(".dataset-config__raw-preview").exists()).toBe(false);
    wrapper.destroy();
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
