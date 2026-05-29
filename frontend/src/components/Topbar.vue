<script setup lang="ts">
import { ref } from "vue";
import type { Locale, TabKey, Theme } from "../types";
import IconSvg from "./IconSvg.vue";

defineProps<{
  activeTab: TabKey;
  locale: Locale;
  theme: Theme;
  savingConfig: boolean;
  t: (key: string, values?: Record<string, string | number>) => string;
}>();

const emit = defineEmits<{
  changeTab: [tab: TabKey];
  changeLocale: [locale: Locale];
  changeTheme: [theme: Theme];
  saveConfig: [];
}>();

const settingsOpen = ref(false);
</script>

<template>
  <header class="topbar">
    <div class="topbar-left">
      <div class="topbar-logo">RBQM</div>
    </div>
    <div class="top-actions">
      <button class="icon-button" aria-label="通知"><IconSvg name="bell" /></button>
      <button class="deploy-button" type="button" :disabled="savingConfig" @click="emit('saveConfig')">
        {{ savingConfig ? t("actions.savingConfig") : t("actions.saveConfig") }}
      </button>
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
