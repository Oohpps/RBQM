<script setup lang="ts">
import logoUrl from "../../assets/rbqm-logo.png";
import IconSvg from "./IconSvg.vue";

defineProps<{
  sampleChecked: boolean;
  t: (key: string, values?: Record<string, string | number>) => string;
}>();

const emit = defineEmits<{
  toggleSidebar: [];
  filesSelected: [files: File[]];
  useDemo: [];
}>();

function onFilesSelected(event: Event): void {
  const input = event.target as HTMLInputElement;
  if (input.files?.length) {
    emit("filesSelected", Array.from(input.files));
    input.value = "";
  }
}

function onSampleChange(event: Event): void {
  const input = event.target as HTMLInputElement;
  if (input.checked) emit("useDemo");
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
      <a class="side-item muted" href="#">
        <span class="side-icon"><IconSvg name="grid" /></span>
        <span class="sidebar-text">{{ t("nav.dashboard") }}</span>
      </a>
      <a class="side-item muted" href="#">
        <span class="side-icon"><IconSvg name="lab" /></span>
        <span class="sidebar-text">{{ t("nav.studies") }}</span>
      </a>
      <a class="side-item active" href="#">
        <span class="side-icon"><IconSvg name="sliders" /></span>
        <span class="sidebar-text">{{ t("nav.thresholds") }}</span>
      </a>
      <a class="side-item muted" href="#">
        <span class="side-icon"><IconSvg name="pin" /></span>
        <span class="sidebar-text">{{ t("nav.sites") }}</span>
      </a>
      <a class="side-item muted" href="#">
        <span class="side-icon"><IconSvg name="chart" /></span>
        <span class="sidebar-text">{{ t("nav.reports") }}</span>
      </a>
    </nav>

    <section class="upload-panel">
      <h3 class="sidebar-text">{{ t("upload.title") }}</h3>
      <label class="upload-button">
        <span class="button-icon"><IconSvg name="upload" /></span>
        <span class="sidebar-text">{{ t("upload.button") }}</span>
        <input type="file" accept=".csv,.xlsx,.xls" multiple @change="onFilesSelected" />
      </label>
      <p class="sidebar-text">{{ t("upload.note") }}</p>
    </section>

    <label class="sample-toggle">
      <span class="sidebar-text">{{ t("sample.toggle") }}</span>
      <input type="checkbox" :checked="sampleChecked" @change="onSampleChange" />
      <span class="toggle-track"></span>
    </label>
  </aside>
</template>
