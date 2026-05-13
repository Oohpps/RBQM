<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { fetchConfig, fetchState, previewUpload, resetDemo as resetDemoApi, saveConfig as saveConfigApi, thresholdParams } from "./api";
import { scoreColumnsByMetric, thresholds as thresholdDefaults } from "./config";
import { translate } from "./i18n";
import type { DataRow, Locale, RbqmState, TabKey, Theme, ThresholdItem, UploadPreview } from "./types";
import DataTable from "./components/DataTable.vue";
import IconSvg from "./components/IconSvg.vue";
import MappingWizard from "./components/MappingWizard.vue";
import Sidebar from "./components/Sidebar.vue";
import ThresholdPanel from "./components/ThresholdPanel.vue";
import Topbar from "./components/Topbar.vue";

const kriEnabled = ref(true);
const activeTab = ref<TabKey>("import");
const state = ref<RbqmState | null>(null);
const locale = ref<Locale>((localStorage.getItem("rbqm.language") as Locale) || "zh");
const theme = ref<Theme>((localStorage.getItem("rbqm.theme") as Theme) || "light");
const sidebarCollapsed = ref(false);
const settingsRefreshTimer = ref<number | null>(null);
const pendingFiles = ref<File[]>([]);
const uploadPreview = ref<UploadPreview | null>(null);
const workspaceRef = ref<HTMLElement | null>(null);
const resizeHandleRef = ref<HTMLElement | null>(null);
const savingConfig = ref(false);
const thresholdRailWidth = {
  default: 352,
  min: 280,
  max: 560,
  storageKey: "rbqm.thresholdRailWidth",
};

const thresholds = reactive<ThresholdItem[]>(
  thresholdDefaults.map((item) => ({
    ...item,
    label: { ...item.label },
    group: { ...item.group },
  })),
);

const params = computed(() => thresholdParams(kriEnabled.value, thresholds));
const sampleChecked = computed(() => Boolean(state.value?.using_demo_data));
const dataHint = computed(() => (state.value?.using_demo_data ? t("hint.demo") : t("hint.uploaded")));
const visibleMetrics = computed(() => visibleMetricRows(state.value?.metrics || []));

function t(key: string, values: Record<string, string | number> = {}): string {
  return translate(locale.value, key, values);
}

function setLocale(nextLocale: Locale): void {
  locale.value = nextLocale;
  localStorage.setItem("rbqm.language", nextLocale);
}

function setTheme(nextTheme: Theme): void {
  theme.value = nextTheme;
  localStorage.setItem("rbqm.theme", nextTheme);
}

function activateTab(tab: TabKey): void {
  activeTab.value = tab;
}

function setKriEnabled(enabled: boolean): void {
  kriEnabled.value = enabled;
  scheduleRefresh();
}

function cancelUpload(): void {
  uploadPreview.value = null;
  pendingFiles.value = [];
}

function exportPackage(): void {
  window.location.href = `/api/export?${params.value.toString()}`;
}

function applyConfig(config: { kri_enabled: boolean; enabled_metrics: string[]; thresholds: Record<string, number> }): void {
  kriEnabled.value = config.kri_enabled;
  const enabled = new Set(config.enabled_metrics);
  thresholds.forEach((item) => {
    if (Object.prototype.hasOwnProperty.call(config.thresholds, item.key)) {
      item.value = Number(config.thresholds[item.key]);
    }
    item.enabled = enabled.has(item.key);
  });
}

async function loadConfig(): Promise<void> {
  try {
    const config = await fetchConfig();
    if (config.active) applyConfig(config.active);
  } catch (error) {
    console.error(error);
    alert(t("alert.configLoad"));
  }
}

async function saveConfig(): Promise<void> {
  if (savingConfig.value) return;
  savingConfig.value = true;
  try {
    const saved = await saveConfigApi(kriEnabled.value, thresholds);
    if (saved.active) applyConfig(saved.active);
    await loadState();
    alert(t("alert.configSave", { version: saved.active.version }));
  } catch (error) {
    console.error(error);
    alert(error instanceof Error ? error.message : t("alert.configSaveFailed"));
  } finally {
    savingConfig.value = false;
  }
}

function scheduleRefresh(): void {
  if (settingsRefreshTimer.value !== null) window.clearTimeout(settingsRefreshTimer.value);
  settingsRefreshTimer.value = window.setTimeout(() => {
    loadState();
  }, 240);
}

async function loadState(): Promise<void> {
  try {
    state.value = await fetchState(params.value);
  } catch (error) {
    console.error(error);
    alert(t("alert.load"));
  }
}

async function resetDemo(): Promise<void> {
  try {
    uploadPreview.value = null;
    pendingFiles.value = [];
    state.value = await resetDemoApi(params.value);
  } catch (error) {
    alert(error instanceof Error ? error.message : t("alert.load"));
  }
}

async function onFilesSelected(files: File[]): Promise<void> {
  if (!files.length) return;
  pendingFiles.value = files;
  try {
    uploadPreview.value = await previewUpload(pendingFiles.value);
    activeTab.value = "import";
  } catch (error) {
    alert(error instanceof Error ? error.message : t("alert.preview"));
  }
}

function onUploadImported(nextState: RbqmState): void {
  state.value = nextState;
  uploadPreview.value = null;
  pendingFiles.value = [];
}

function visibleMetricRows(rows: DataRow[]): DataRow[] {
  if (!rows.length) return rows;
  const disabledScoreColumns = new Set<string>();
  thresholds
    .filter((item) => !kriEnabled.value || !item.enabled)
    .forEach((item) => {
      (scoreColumnsByMetric[item.key] || []).forEach((column) => disabledScoreColumns.add(column));
    });

  return rows.map((row) => {
    const next = { ...row };
    disabledScoreColumns.forEach((column) => delete next[column]);
    return next;
  });
}

function clampThresholdRailWidth(width: number): number {
  return Math.min(thresholdRailWidth.max, Math.max(thresholdRailWidth.min, Math.round(width)));
}

function setThresholdRailWidth(width: number, persist = true): void {
  const workspace = workspaceRef.value;
  const handle = resizeHandleRef.value;
  if (!workspace) return;
  const nextWidth = clampThresholdRailWidth(width);
  workspace.style.setProperty("--threshold-rail-width", `${nextWidth}px`);
  if (handle) {
    handle.setAttribute("aria-valuemin", String(thresholdRailWidth.min));
    handle.setAttribute("aria-valuemax", String(thresholdRailWidth.max));
    handle.setAttribute("aria-valuenow", String(nextWidth));
  }
  if (persist) localStorage.setItem(thresholdRailWidth.storageKey, String(nextWidth));
}

function initThresholdRailResize(): void {
  const workspace = workspaceRef.value;
  const handle = resizeHandleRef.value;
  if (!workspace || !handle) return;
  const savedWidth = Number(localStorage.getItem(thresholdRailWidth.storageKey));
  setThresholdRailWidth(Number.isFinite(savedWidth) && savedWidth > 0 ? savedWidth : thresholdRailWidth.default, false);

  const widthFromPointer = (clientX: number) => clientX - workspace.getBoundingClientRect().left;
  const stopResize = () => document.body.classList.remove("threshold-resizing");

  handle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);
    document.body.classList.add("threshold-resizing");
  });
  handle.addEventListener("pointermove", (event) => {
    if (document.body.classList.contains("threshold-resizing")) setThresholdRailWidth(widthFromPointer(event.clientX));
  });
  handle.addEventListener("pointerup", stopResize);
  handle.addEventListener("pointercancel", stopResize);
  handle.addEventListener("dblclick", () => setThresholdRailWidth(thresholdRailWidth.default));
  handle.addEventListener("keydown", (event) => {
    const current = Number(handle.getAttribute("aria-valuenow")) || thresholdRailWidth.default;
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      setThresholdRailWidth(current - 16);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      setThresholdRailWidth(current + 16);
    } else if (event.key === "Home") {
      event.preventDefault();
      setThresholdRailWidth(thresholdRailWidth.min);
    } else if (event.key === "End") {
      event.preventDefault();
      setThresholdRailWidth(thresholdRailWidth.max);
    }
  });
}

watch(theme, (nextTheme) => {
  document.body.dataset.theme = nextTheme;
}, { immediate: true });

watch(locale, (nextLocale) => {
  document.documentElement.lang = nextLocale === "zh" ? "zh-CN" : "en";
}, { immediate: true });

watch(sidebarCollapsed, (collapsed) => {
  document.body.classList.toggle("sidebar-collapsed", collapsed);
});

onMounted(async () => {
  await nextTick();
  initThresholdRailResize();
  await loadConfig();
  loadState();
});

onBeforeUnmount(() => {
  if (settingsRefreshTimer.value !== null) window.clearTimeout(settingsRefreshTimer.value);
});
</script>

<template>
  <div class="app-shell">
    <Sidebar
      :sample-checked="sampleChecked"
      :t="t"
      @toggle-sidebar="sidebarCollapsed = !sidebarCollapsed"
      @files-selected="onFilesSelected"
      @use-demo="resetDemo"
    />

    <main class="main">
      <Topbar
        :active-tab="activeTab"
        :locale="locale"
        :theme="theme"
        :saving-config="savingConfig"
        :t="t"
        @change-tab="activateTab"
        @change-locale="setLocale"
        @change-theme="setTheme"
        @save-config="saveConfig"
      />

      <section ref="workspaceRef" class="workspace">
        <aside class="threshold-rail">
          <ThresholdPanel
            :kri-enabled="kriEnabled"
            :thresholds="thresholds"
            :locale="locale"
            :t="t"
            @update-kri-enabled="setKriEnabled"
            @threshold-changed="scheduleRefresh"
          />
        </aside>
        <div
          ref="resizeHandleRef"
          class="threshold-resize-handle"
          role="separator"
          aria-label="调整KRI阈值设置列宽"
          aria-orientation="vertical"
          tabindex="0"
        ></div>

        <section class="content">
          <section class="tab-page" :class="{ active: activeTab === 'import' }">
            <h1>{{ t("pages.import") }}</h1>
            <div class="info-banner">
              <IconSvg name="info" />
              <span>{{ dataHint }}</span>
            </div>

            <div v-if="state?.raw_summary.length" class="data-card">
              <div class="card-title">{{ t("cards.raw") }}</div>
              <div class="table-wrap">
                <DataTable :rows="state.raw_summary" :empty-text="t('empty')" />
              </div>
            </div>

            <MappingWizard
              :preview="uploadPreview"
              :files="pendingFiles"
              :params="params"
              :t="t"
              @imported="onUploadImported"
              @cancel="cancelUpload"
            />

            <div class="data-card">
              <div class="card-title">{{ t("cards.domain") }}</div>
              <div class="table-wrap">
                <DataTable :rows="state?.domain_summary || []" :empty-text="t('empty')" />
              </div>
            </div>

            <details class="fields-card" open>
              <summary>
                <span>{{ t("cards.fields") }}</span>
                <IconSvg name="chevron" />
              </summary>
              <div class="field-list">
                <div v-for="item in state?.fields || []" :key="item.domain" class="field-row">
                  <span class="field-domain">{{ item.domain }}：</span>
                  <span>
                    <span v-for="field in item.fields" :key="field" class="field-chip">{{ field }}</span>
                  </span>
                </div>
              </div>
            </details>
          </section>

          <section class="tab-page" :class="{ active: activeTab === 'overview' }">
            <h1>{{ t("pages.overview") }}</h1>
            <div class="metric-grid">
              <div v-for="(value, label) in state?.overview || {}" :key="label" class="metric-card">
                <div class="metric-label">{{ label }}</div>
                <div class="metric-value">{{ value }}</div>
              </div>
            </div>
          </section>

          <section class="tab-page" :class="{ active: activeTab === 'kri' }">
            <h1>{{ t("pages.kri") }}</h1>
            <div class="data-card">
              <div class="card-title">{{ t("cards.kri") }}</div>
              <div class="table-wrap">
                <DataTable :rows="visibleMetrics" :limit="12" :empty-text="t('empty')" />
              </div>
            </div>
          </section>

          <section class="tab-page fill-table-page" :class="{ active: activeTab === 'ranking' }">
            <h1>{{ t("pages.ranking") }}</h1>
            <div class="data-card">
              <div class="table-wrap">
                <DataTable
                  :rows="state?.metrics || []"
                  :preferred-columns="['中心', '受试者数', '风险评分', '风险等级', '缺失率', '延迟录入率']"
                  :limit="30"
                  :empty-text="t('empty')"
                />
              </div>
            </div>
          </section>

          <section class="tab-page fill-table-page" :class="{ active: activeTab === 'details' }">
            <h1>{{ t("pages.details") }}</h1>
            <div class="data-card">
              <div class="table-wrap">
                <DataTable :rows="state?.signals || []" :limit="30" :empty-text="t('empty')" />
              </div>
            </div>
          </section>

          <section class="tab-page fill-table-page" :class="{ active: activeTab === 'actions' }">
            <h1>{{ t("pages.actions") }}</h1>
            <div class="data-card">
              <div class="table-wrap">
                <DataTable :rows="state?.action_log || []" :limit="30" :empty-text="t('empty')" />
              </div>
            </div>
            <button class="export-button" type="button" @click="exportPackage">
              {{ t("actions.export") }}
            </button>
          </section>
        </section>
      </section>
    </main>
  </div>
</template>
