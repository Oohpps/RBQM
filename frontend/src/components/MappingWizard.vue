<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { commitUpload } from "../api";
import type { MappingConfig, MappingSelections, PreviewDomain, PreviewSource, RbqmState, UploadPreview, UploadRole } from "../types";

const props = defineProps<{
  preview: UploadPreview | null;
  files: File[];
  sourceRoles: Record<string, UploadRole>;
  params: URLSearchParams;
  t: (key: string, values?: Record<string, string | number>) => string;
}>();

const emit = defineEmits<{
  imported: [state: RbqmState];
  cancel: [];
}>();

const step = ref(1);
const selections = reactive<MappingSelections>({});
const committing = ref(false);

const selectedSources = computed(() => {
  if (!props.preview) return [];
  return props.preview.sources.filter((source) => selections[source.source_id]?.domain);
});

const warnings = computed(() => {
  const items: string[] = [];
  selectedSources.value.forEach((source) => {
    const selection = selections[source.source_id];
    const spec = domainSpec(selection.domain);
    (spec?.required_fields || []).forEach((field) => {
      if (!selection.fields?.[field]) items.push(`${source.source_id}: ${props.t("mapping.missing")} ${field}`);
    });
  });
  if (!selectedSources.value.length) items.push(props.t("mapping.noSources"));
  return items;
});

const config = computed<MappingConfig>(() => {
  const sources: MappingConfig["sources"] = {};
  selectedSources.value.forEach((source) => {
    const selection = selections[source.source_id];
    const fields: Record<string, string> = {};
    Object.entries(selection.fields || {}).forEach(([field, column]) => {
      if (column) fields[field] = column;
    });
    sources[source.source_id] = { domain: selection.domain, fields };
  });
  return { sources };
});

watch(
  () => props.preview,
  (preview) => {
    Object.keys(selections).forEach((key) => delete selections[key]);
    step.value = 1;
    preview?.sources.forEach((source) => {
      selections[source.source_id] = { domain: source.guessed_domain || "", fields: {} };
      initializeFieldMapping(source.source_id);
    });
  },
  { immediate: true },
);

function normalizeName(value: string): string {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^\w]+/gu, "_")
    .replace(/^_+|_+$/g, "");
}

function domainSpec(domain: string): PreviewDomain | null {
  return props.preview?.domains.find((item) => item.key === domain) || null;
}

function sourceSpec(sourceId: string): PreviewSource | null {
  return props.preview?.sources.find((item) => item.source_id === sourceId) || null;
}

function guessColumnForField(source: PreviewSource, field: string): string {
  const normalizedField = normalizeName(field);
  return source.columns.find((column) => normalizeName(column) === normalizedField)
    || source.columns.find((column) => normalizeName(column).includes(normalizedField))
    || "";
}

function initializeFieldMapping(sourceId: string): void {
  const selection = selections[sourceId];
  const source = sourceSpec(sourceId);
  const spec = domainSpec(selection?.domain);
  if (!selection || !source || !spec) return;
  const previous = selection.fields || {};
  selection.fields = {};
  spec.fields.forEach((field) => {
    selection.fields[field] = previous[field] || guessColumnForField(source, field);
  });
}

function onDomainChange(sourceId: string, domain: string): void {
  selections[sourceId].domain = domain;
  initializeFieldMapping(sourceId);
}

function onDomainSelect(sourceId: string, event: Event): void {
  onDomainChange(sourceId, (event.target as HTMLSelectElement).value);
}

async function commit(): Promise<void> {
  if (committing.value) return;
  committing.value = true;
  try {
    const state = await commitUpload(props.files, config.value, props.params, props.sourceRoles);
    emit("imported", state);
  } catch (error) {
    alert(error instanceof Error ? error.message : props.t("alert.upload"));
  } finally {
    committing.value = false;
  }
}
</script>

<template>
  <section v-if="preview" class="mapping-wizard" aria-live="polite">
    <div class="mapping-header">
      <div>
        <div class="card-title">{{ t("mapping.title") }}</div>
        <p>{{ t("mapping.subtitle") }}</p>
      </div>
      <button class="secondary-button" type="button" @click="emit('cancel')">{{ t("mapping.cancel") }}</button>
    </div>
    <div class="wizard-steps">
      <span class="wizard-step" :class="{ active: step === 1 }">{{ t("mapping.step1") }}</span>
      <span class="wizard-step" :class="{ active: step === 2 }">{{ t("mapping.step2") }}</span>
      <span class="wizard-step" :class="{ active: step === 3 }">{{ t("mapping.step3") }}</span>
    </div>

    <div class="mapping-body">
      <div v-if="step === 1" class="mapping-table">
        <div v-for="source in preview.sources" :key="source.source_id" class="mapping-row">
          <div>
            <div class="mapping-source">{{ source.source_id }}</div>
            <div class="mapping-meta">{{ t("mapping.rows") }} {{ source.rows }} / {{ t("mapping.columns") }} {{ source.columns.length }}</div>
            <div class="mapping-chips">
              <span v-for="column in source.columns.slice(0, 8)" :key="column">{{ column }}</span>
            </div>
          </div>
          <label>
            <span>{{ t("mapping.domain") }}</span>
            <select :value="selections[source.source_id]?.domain || ''" @change="onDomainSelect(source.source_id, $event)">
              <option value="">{{ t("mapping.skip") }}</option>
              <option v-for="domain in preview.domains" :key="domain.key" :value="domain.key">{{ domain.label }}</option>
            </select>
          </label>
        </div>
      </div>

      <div v-else-if="step === 2">
        <div v-if="!selectedSources.length" class="mapping-empty">{{ t("mapping.noSources") }}</div>
        <template v-else>
          <section v-for="source in selectedSources" :key="source.source_id" class="field-map-card">
            <div class="mapping-source">{{ source.source_id }} / {{ domainSpec(selections[source.source_id].domain)?.label }}</div>
            <div class="field-map-grid">
              <label v-for="field in domainSpec(selections[source.source_id].domain)?.fields || []" :key="field" class="field-map-row">
                <span>
                  <strong>{{ field }}</strong>
                  <small>
                    {{
                      domainSpec(selections[source.source_id].domain)?.required_fields.includes(field)
                        ? t("mapping.required")
                        : t("mapping.optional")
                    }}
                  </small>
                </span>
                <select v-model="selections[source.source_id].fields[field]">
                  <option value="">-</option>
                  <option v-for="column in source.columns" :key="column" :value="column">{{ column }}</option>
                </select>
              </label>
            </div>
          </section>
        </template>
      </div>

      <div v-else class="mapping-confirm" :class="{ 'has-warnings': warnings.length }">
        <div>
          <template v-if="warnings.length">
            <p v-for="warning in warnings" :key="warning">{{ warning }}</p>
          </template>
          <template v-else>{{ t("mapping.ready") }}</template>
        </div>
        <div class="mapping-summary">
          <div v-for="(item, sourceId) in config.sources" :key="sourceId">
            <strong>{{ sourceId }}</strong>
            <span>{{ domainSpec(item.domain)?.label || item.domain }} / {{ Object.keys(item.fields).length }} fields</span>
          </div>
        </div>
      </div>
    </div>

    <div class="mapping-actions">
      <button class="secondary-button" type="button" :disabled="step === 1 || committing" @click="step = Math.max(1, step - 1)">
        {{ t("mapping.back") }}
      </button>
      <button v-if="step !== 3" class="export-button" type="button" :disabled="committing" @click="step = Math.min(3, step + 1)">
        {{ t("mapping.next") }}
      </button>
      <button v-else class="export-button" type="button" :class="{ loading: committing }" :disabled="committing" @click="commit">
        {{ committing ? "正在导入..." : t("mapping.commit") }}
      </button>
    </div>
  </section>
</template>
