import { shallowMount } from "@vue/test-utils";
import Viewer from "./csghub.vue";

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
const page = (start, count = 4) => ({
  data: {
    num_rows_total: 9,
    rows: Array.from({ length: count }, (_, i) => ({
      row_idx: start + i,
      row: { text: `<iframe src="evil">row ${start + i}</iframe>`, label: 0 },
    })),
  },
});
const create = (get) =>
  shallowMount(Viewer, {
    mocks: {
      $axios: { get },
      $route: {
        query: { dataset: "root/private", config: "default", split: "test" },
        fullPath: "/viewer?split=test",
      },
      $t: (key) => key,
    },
  });

describe("CSGHub embedded viewer", () => {
  it("pages through authenticated backend data and renders HTML as inert text", async () => {
    const get = jest
      .fn()
      .mockResolvedValueOnce(page(0))
      .mockResolvedValueOnce(page(4));
    const wrapper = create(get);
    await flush();
    expect(get).toHaveBeenCalledWith("/v1/hub/datasets/rows", {
      params: {
        dataset: "root/private",
        config: "default",
        split: "test",
        source: "csghub",
        offset: 0,
        length: 4,
      },
      skipGlobalErrorHandler: true,
    });
    expect(wrapper.findAll("tbody tr")).toHaveLength(4);
    expect(wrapper.find("iframe").exists()).toBe(false);
    expect(wrapper.find("pre").text()).toContain('<iframe src="evil">');
    await wrapper.find("tbody button").trigger("click");
    expect(wrapper.find("pre").classes()).toContain("expanded");
    await wrapper.findAll("footer button").at(1).trigger("click");
    await flush();
    expect(get.mock.calls[1][1].params.offset).toBe(4);
    expect(wrapper.find("tbody button").text()).toContain("5");
    expect(wrapper.find("pre").classes()).not.toContain("expanded");
    wrapper.destroy();
  });

  it("clears stale data on failure and offers a working retry", async () => {
    const get = jest
      .fn()
      .mockResolvedValueOnce(page(0))
      .mockRejectedValueOnce(new Error("403"))
      .mockResolvedValueOnce(page(4));
    const wrapper = create(get);
    await flush();
    await wrapper.vm.loadPage(4);
    expect(wrapper.find("table").exists()).toBe(false);
    expect(wrapper.find('[role="alert"]').exists()).toBe(true);
    await wrapper.find('[role="alert"] button').trigger("click");
    await flush();
    expect(wrapper.findAll("tbody tr")).toHaveLength(4);
    wrapper.destroy();
  });

  it("ignores late responses when the subset/split changes", async () => {
    let finishOld;
    const get = jest
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finishOld = resolve;
          })
      )
      .mockResolvedValueOnce(page(0, 1));
    const wrapper = create(get);
    wrapper.vm.$route.query.split = "validation";
    await wrapper.vm.$options.watch["$route.fullPath"].handler.call(wrapper.vm);
    await flush();
    finishOld(page(0));
    await flush();
    expect(get.mock.calls[1][1].params.split).toBe("validation");
    expect(wrapper.findAll("tbody tr")).toHaveLength(1);
    wrapper.destroy();
  });
});
