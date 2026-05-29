<script setup lang="ts">
import { computed } from "vue";
import type { Locale, ThresholdItem } from "../types";

const props = defineProps<{
  kriEnabled: boolean;
  thresholds: ThresholdItem[];
  locale: Locale;
  t: (key: string, values?: Record<string, string | number>) => string;
}>();

const emit = defineEmits<{
  updateKriEnabled: [enabled: boolean];
  thresholdChanged: [];
}>();

const enabledCount = computed(() => (props.kriEnabled ? props.thresholds.filter((item) => item.enabled).length : 0));

function labelOf(item: ThresholdItem): string {
  return item.label[props.locale] || item.label.zh;
}

function groupOf(item: ThresholdItem): string {
  return item.group[props.locale] || item.group.zh;
}

function rangeStyle(item: ThresholdItem): Record<string, string> {
  const percent = ((item.value - item.min) / (item.max - item.min)) * 100;
  return { "--pct": `${percent}%` };
}

function setKriFromEvent(event: Event): void {
  const enabled = (event.target as HTMLInputElement).checked;
  if (enabled) {
    props.thresholds.forEach((item) => {
      item.enabled = true;
    });
    emit("thresholdChanged");
  }
  emit("updateKriEnabled", enabled);
}

function setMetricEnabled(item: ThresholdItem, event: Event): void {
  item.enabled = (event.target as HTMLInputElement).checked;
  emit("thresholdChanged");
}

function setThresholdValue(item: ThresholdItem, event: Event): void {
  item.value = Number((event.target as HTMLInputElement).value);
  emit("thresholdChanged");
}
</script>

<template>
  <section class="threshold-panel">
    <div class="threshold-header">
      <h3>{{ t("threshold.title") }}</h3>
    </div>
    <div class="threshold-controls">
      <div class="threshold-master" :class="{ off: !kriEnabled }">
        <div>
          <div class="threshold-master-title">{{ t("threshold.master") }}</div>
          <div class="threshold-master-note">
            {{
              kriEnabled
                ? t("threshold.enabled", { count: enabledCount, total: thresholds.length })
                : t("threshold.disabled")
            }}
          </div>
        </div>
        <label class="switch-control" title="启用或关闭全部KRI阈值">
          <input type="checkbox" :checked="kriEnabled" @change="setKriFromEvent" />
          <span class="switch-track"></span>
        </label>
      </div>

      <div v-for="item in kriEnabled ? thresholds : []" :key="item.key" class="threshold-control" :class="{ disabled: !item.enabled }">
        <div class="threshold-row">
          <div class="threshold-name">
            <span class="threshold-chip">{{ groupOf(item) }}</span>
            <span class="threshold-label">{{ labelOf(item) }}</span>
            <span class="threshold-value">{{ item.value.toFixed(item.decimals) }}</span>
          </div>
          <label class="switch-control metric-switch" title="启用或关闭该KRI指标">
            <input
              type="checkbox"
              :checked="item.enabled"
              :disabled="!kriEnabled"
              @change="setMetricEnabled(item, $event)"
            />
            <span class="switch-track"></span>
          </label>
        </div>
        <input
          type="range"
          :min="item.min"
          :max="item.max"
          :step="item.step"
          :value="item.value"
          :disabled="!kriEnabled || !item.enabled"
          :style="rangeStyle(item)"
          @input="setThresholdValue(item, $event)"
        />
      </div>
    </div>
  </section>
</template>
