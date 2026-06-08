<script setup lang="ts">
import { ref } from "vue";
import logoUrl from "../../assets/rbqm-logo.png";
import type { TabKey, UploadRole } from "../types";
import IconSvg from "./IconSvg.vue";

defineProps<{
  activeTab: TabKey;
  importing: boolean;
  t: (key: string, values?: Record<string, string | number>) => string;
}>();

const emit = defineEmits<{
  toggleSidebar: [];
  navigate: [tab: TabKey];
  filesSelected: [files: File[], role: UploadRole];
}>();

const uploadOptions: { role: UploadRole; label: string }[] = [
  { role: "clinical_data", label: "临床研究数据" },
  { role: "progress_report", label: "进展报告" },
  { role: "critical_points", label: "关键数据点" },
  { role: "query_detail", label: "质疑明细报告" },
];
const importOpen = ref(false);

function onFilesSelected(event: Event, role: UploadRole): void {
  const input = event.target as HTMLInputElement;
  if (input.disabled) return;
  if (input.files?.length) {
    emit("filesSelected", Array.from(input.files), role);
    importOpen.value = false;
    input.value = "";
  }
}

</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <img class="brand-logo" :src="logoUrl" alt="RBQM logo" />
      <div>
        <div class="brand-title sidebar-text">Clinical Risk</div>
        <div class="brand-subtitle sidebar-text">Quality Management</div>
      </div>
    </div>

    <nav class="side-nav" aria-label="主菜单">
      <button class="nav-collapse-button" type="button" aria-label="收起左侧菜单" @click="emit('toggleSidebar')">
        <IconSvg name="collapseLeft" />
        <span class="sidebar-text">{{ t("nav.collapse") }}</span>
      </button>
      <button
        class="side-item"
        :class="{ active: activeTab === 'overview', muted: activeTab !== 'overview' }"
        type="button"
        @click="emit('navigate', 'overview')"
      >
        <span class="side-icon"><IconSvg name="lab" /></span>
        <span class="sidebar-text">{{ t("nav.studies") }}</span>
      </button>
      <button
        class="side-item"
        :class="{ active: activeTab === 'import', muted: activeTab !== 'import' }"
        type="button"
        @click="emit('navigate', 'import')"
      >
        <span class="side-icon"><IconSvg name="sliders" /></span>
        <span class="sidebar-text">{{ t("nav.thresholds") }}</span>
      </button>
      <button
        class="side-item"
        :class="{ active: activeTab === 'efficacy', muted: activeTab !== 'efficacy' }"
        type="button"
        @click="emit('navigate', 'efficacy')"
      >
        <span class="side-icon"><IconSvg name="chart" /></span>
        <span class="sidebar-text">{{ t("nav.efficacy") }}</span>
      </button>
      <button
        class="side-item"
        :class="{ active: activeTab === 'risk_forecast', muted: activeTab !== 'risk_forecast' }"
        type="button"
        @click="emit('navigate', 'risk_forecast')"
      >
        <span class="side-icon"><IconSvg name="chart" /></span>
        <span class="sidebar-text">{{ t("nav.riskForecast") }}</span>
      </button>
      <button
        class="side-item"
        :class="{ active: activeTab === 'kri', muted: activeTab !== 'kri' }"
        type="button"
        @click="emit('navigate', 'kri')"
      >
        <span class="side-icon"><IconSvg name="grid" /></span>
        <span class="sidebar-text">{{ t("nav.dashboard") }}</span>
      </button>
      <button
        class="side-item"
        :class="{ active: activeTab === 'ranking', muted: activeTab !== 'ranking' }"
        type="button"
        @click="emit('navigate', 'ranking')"
      >
        <span class="side-icon"><IconSvg name="pin" /></span>
        <span class="sidebar-text">{{ t("nav.sites") }}</span>
      </button>
      <button
        class="side-item"
        :class="{ active: activeTab === 'details', muted: activeTab !== 'details' }"
        type="button"
        @click="emit('navigate', 'details')"
      >
        <span class="side-icon"><IconSvg name="chart" /></span>
        <span class="sidebar-text">{{ t("nav.reports") }}</span>
      </button>
    </nav>

    <section class="upload-panel">
      <button class="upload-trigger-button" type="button" :aria-expanded="importOpen" :disabled="importing" @click="importOpen = !importOpen">
        <span class="button-icon"><IconSvg name="upload" /></span>
        <span class="sidebar-text">导入数据</span>
      </button>
    </section>

    <section v-if="importOpen" class="upload-popover" aria-label="导入数据">
      <div class="upload-popover-header">
        <div>
          <h3>导入数据</h3>
          <p>{{ t("upload.note") }}</p>
        </div>
        <button class="upload-popover-close" type="button" aria-label="关闭导入数据" @click="importOpen = false">×</button>
      </div>
      <div class="upload-option-grid">
        <label v-for="option in uploadOptions" :key="option.role" class="upload-option-card" :class="{ disabled: importing }">
          <span class="button-icon"><IconSvg name="upload" /></span>
          <span>{{ option.label }}</span>
          <input type="file" accept=".csv,.xlsx,.xls" multiple :disabled="importing" @change="onFilesSelected($event, option.role)" />
        </label>
      </div>
    </section>
  </aside>
</template>
