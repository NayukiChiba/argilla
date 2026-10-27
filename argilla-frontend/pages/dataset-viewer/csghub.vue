<template>
  <main class="csghub-viewer" :aria-busy="loading">
    <header>
      <strong>{{ $t("datasetCreation.csghubViewer.title") }}</strong>
      <span>{{ dataset }}</span>
      <span>{{ config }} / {{ split }}</span>
    </header>
    <p v-if="loading" role="status">
      {{ $t("datasetCreation.csghubViewer.loading") }}
    </p>
    <div v-else-if="failed" role="alert">
      <p>{{ $t("datasetCreation.csghubUnavailable") }}</p>
      <button @click="loadPage(offset)">
        {{ $t("datasetCreation.csghubViewer.retry") }}
      </button>
    </div>
    <template v-else>
      <div class="csghub-viewer__table">
        <table v-if="rows.length">
          <thead>
            <tr>
              <th scope="col">#</th>
              <th v-for="column in columns" :key="column" scope="col">
                {{ column }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in rows" :key="item.row_idx">
              <th scope="row">
                <button
                  :aria-expanded="expanded.includes(item.row_idx)"
                  :title="
                    $t(
                      `datasetCreation.csghubViewer.${
                        expanded.includes(item.row_idx) ? 'collapse' : 'expand'
                      }`
                    )
                  "
                  @click="toggleRow(item.row_idx)"
                >
                  {{ item.row_idx + 1 }}
                  {{ expanded.includes(item.row_idx) ? "−" : "+" }}
                </button>
              </th>
              <td v-for="column in columns" :key="column">
                <pre :class="{ expanded: expanded.includes(item.row_idx) }">{{
                  formatValue(item.row[column])
                }}</pre>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else>{{ $t("datasetCreation.csghubViewer.empty") }}</p>
      </div>
      <footer>
        <button :disabled="offset === 0" @click="loadPage(offset - pageSize)">
          {{ $t("datasetCreation.csghubViewer.previous") }}
        </button>
        <span role="status">{{
          $t("datasetCreation.csghubViewer.rows", {
            start: rows.length ? offset + 1 : 0,
            end: offset + rows.length,
            total: total === null ? "?" : total,
          })
        }}</span>
        <button :disabled="!hasNext" @click="loadPage(offset + pageSize)">
          {{ $t("datasetCreation.csghubViewer.next") }}
        </button>
      </footer>
    </template>
  </main>
</template>

<script>
export default {
  layout: "app",
  data() {
    return {
      rows: [],
      offset: 0,
      total: null,
      pageSize: 4,
      expanded: [],
      loading: false,
      failed: false,
      requestId: 0,
    };
  },
  computed: {
    dataset() {
      return this.$route.query.dataset;
    },
    config() {
      return this.$route.query.config;
    },
    split() {
      return this.$route.query.split;
    },
    columns() {
      return [...new Set(this.rows.flatMap((item) => Object.keys(item.row)))];
    },
    hasNext() {
      return this.total === null
        ? this.rows.length === this.pageSize
        : this.offset + this.rows.length < this.total;
    },
  },
  watch: {
    "$route.fullPath": {
      immediate: true,
      handler() {
        this.loadPage(0);
      },
    },
  },
  beforeDestroy() {
    this.requestId++;
  },
  methods: {
    formatValue(value) {
      if (typeof value === "string") return value;
      return JSON.stringify(value, null, 2) ?? "";
    },
    toggleRow(index) {
      this.expanded = this.expanded.includes(index)
        ? this.expanded.filter((value) => value !== index)
        : [...this.expanded, index];
    },
    async loadPage(offset) {
      const requestId = ++this.requestId;
      this.loading = true;
      this.failed = false;
      this.rows = [];
      this.expanded = [];
      this.offset = offset;
      try {
        if (
          ![this.dataset, this.config, this.split].every(
            (value) => typeof value === "string" && value
          )
        ) {
          throw new Error("Missing dataset, subset or split");
        }
        const { data } = await this.$axios.get("/v1/hub/datasets/rows", {
          params: {
            dataset: this.dataset,
            config: this.config,
            split: this.split,
            source: "csghub",
            offset,
            length: this.pageSize,
          },
          skipGlobalErrorHandler: true,
        });
        if (requestId !== this.requestId) return;
        this.rows = data.rows;
        this.total = data.num_rows_total ?? null;
      } catch {
        if (requestId === this.requestId) this.failed = true;
      } finally {
        if (requestId === this.requestId) this.loading = false;
      }
    },
  },
};
</script>

<style scoped lang="scss">
.csghub-viewer {
  padding: 12px;
  color: var(--fg-primary);
  background: var(--bg-accent-grey-1);
  font-size: 13px;
  header {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 16px;
    margin-bottom: 12px;
  }
  header span {
    overflow-wrap: anywhere;
  }
  &__table {
    overflow: auto;
    max-height: 360px;
    border: 1px solid var(--bg-opacity-10);
    border-radius: 6px;
  }
  table {
    border-collapse: separate;
    border-spacing: 0;
    width: 100%;
  }
  th,
  td {
    padding: 10px;
    vertical-align: top;
    text-align: left;
    border-bottom: 1px solid var(--bg-opacity-10);
  }
  thead th {
    position: sticky;
    top: 0;
    background: var(--bg-accent-grey-2);
    z-index: 1;
  }
  td {
    min-width: 220px;
    max-width: 440px;
  }
  pre {
    font: inherit;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    margin: 0;
    max-height: 8em;
    overflow: auto;
  }
  pre.expanded {
    max-height: none;
  }
  footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-top: 12px;
  }
  button {
    padding: 5px 8px;
    border: 1px solid var(--bg-opacity-10);
    border-radius: 4px;
    background: var(--bg-accent-grey-1);
    color: inherit;
    cursor: pointer;
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  button:focus-visible {
    outline: 2px solid var(--bg-action);
    outline-offset: 2px;
  }
}
</style>
