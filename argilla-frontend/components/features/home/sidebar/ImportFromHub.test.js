import { shallowMount } from "@vue/test-utils";
import ImportFromHub from "./ImportFromHub.vue";

describe("ImportFromHub URL entry", () => {
  it("submits the complete URL without a second source selector", async () => {
    const wrapper = shallowMount(ImportFromHub, {
      propsData: { isExpanded: true },
      mocks: { $t: (key) => key },
      stubs: ["BaseButton", "BaseInput", "BaseInputContainer", "svgicon"],
    });
    await wrapper.setData({
      repositoryId: " https://huggingface.co/datasets/owner/repo ",
    });
    await wrapper.find("form").trigger("submit");
    expect(wrapper.emitted("on-import-url")).toEqual([
      ["https://huggingface.co/datasets/owner/repo"],
    ]);
    expect(wrapper.find("select").exists()).toBe(false);
  });
});
