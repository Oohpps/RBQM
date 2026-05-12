<script setup lang="ts">
import { ref } from "vue";
import type { Locale, TabKey, Theme } from "../types";
import IconSvg from "./IconSvg.vue";

defineProps<{
  activeTab: TabKey;
  locale: Locale;
  theme: Theme;
  t: (key: string, values?: Record<string, string | number>) => string;
}>();

const emit = defineEmits<{
  changeTab: [tab: TabKey];
  changeLocale: [locale: Locale];
  changeTheme: [theme: Theme];
}>();

const settingsOpen = ref(false);
const tabs: { key: TabKey; label: string }[] = [
  { key: "import", label: "tabs.import" },
  { key: "overview", label: "tabs.overview" },
  { key: "kri", label: "tabs.kri" },
  { key: "ranking", label: "tabs.ranking" },
  { key: "details", label: "tabs.details" },
  { key: "actions", label: "tabs.actions" },
];
</script>

<template>
  <header class="topbar">
    <div class="topbar-left">
      <div class="topbar-logo">RBQM</div>
      <nav class="top-tabs" aria-label="子菜单">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="top-tab"
          :class="{ active: activeTab === tab.key }"
          type="button"
          @click="emit('changeTab', tab.key)"
        >
          {{ t(tab.label) }}
        </button>
      </nav>
    </div>
    <div class="top-actions">
      <button class="icon-button" aria-label="通知"><IconSvg name="bell" /></button>
      <button class="deploy-button">{{ t("actions.deploy") }}</button>
      <div class="settings-wrap">
        <button
          class="icon-button"
          type="button"
          aria-label="更多设置"
          :aria-expanded="settingsOpen"
          aria-controls="settingsMenu"
          @click.stop="settingsOpen = !settingsOpen"
        >
          <IconSvg name="more" />
        </button>
        <div id="settingsMenu" class="settings-menu" :class="{ hidden: !settingsOpen }" @click.stop>
          <div class="settings-title">{{ t("settings.title") }}</div>
          <div class="settings-group">
            <div class="settings-label">{{ t("settings.language") }}</div>
            <div class="segmented-control" role="group" aria-label="语言">
              <button type="button" :class="{ active: locale === 'zh' }" @click="emit('changeLocale', 'zh')">中文</button>
              <button type="button" :class="{ active: locale === 'en' }" @click="emit('changeLocale', 'en')">EN</button>
            </div>
          </div>
          <div class="settings-group">
            <div class="settings-label">{{ t("settings.theme") }}</div>
            <div class="segmented-control" role="group" aria-label="主题">
              <button type="button" :class="{ active: theme === 'light' }" @click="emit('changeTheme', 'light')">Light</button>
              <button type="button" :class="{ active: theme === 'dark' }" @click="emit('changeTheme', 'dark')">Dark</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </header>
</template>
