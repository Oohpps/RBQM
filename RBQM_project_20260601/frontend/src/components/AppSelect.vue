<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

export interface AppSelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

const props = withDefaults(defineProps<{
  modelValue: string;
  options: AppSelectOption[];
  placeholder?: string;
  disabled?: boolean;
  ariaLabel?: string;
}>(), {
  placeholder: "请选择",
  disabled: false,
  ariaLabel: "选择选项",
});

const emit = defineEmits<{
  "update:modelValue": [value: string];
  change: [value: string];
}>();

const root = ref<HTMLElement | null>(null);
const open = ref(false);
const selectedOption = computed(() => props.options.find((option) => option.value === props.modelValue));

function toggle(): void {
  if (!props.disabled) open.value = !open.value;
}

function choose(option: AppSelectOption): void {
  if (option.disabled) return;
  emit("update:modelValue", option.value);
  emit("change", option.value);
  open.value = false;
}

function onDocumentPointerDown(event: PointerEvent): void {
  if (!root.value?.contains(event.target as Node)) open.value = false;
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") open.value = false;
}

onMounted(() => {
  document.addEventListener("pointerdown", onDocumentPointerDown);
  document.addEventListener("keydown", onKeydown);
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onDocumentPointerDown);
  document.removeEventListener("keydown", onKeydown);
});
</script>

<template>
  <div ref="root" class="app-select" :class="{ open, disabled }">
    <button
      type="button"
      class="app-select-trigger"
      :disabled="disabled"
      :aria-label="ariaLabel"
      :aria-expanded="open"
      aria-haspopup="listbox"
      @click="toggle"
    >
      <span :class="{ placeholder: !selectedOption }">{{ selectedOption?.label || placeholder }}</span>
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="m7 10 5 5 5-5"></path>
      </svg>
    </button>
    <div v-if="open" class="app-select-menu" role="listbox">
      <button
        v-for="option in options"
        :key="option.value"
        type="button"
        class="app-select-option"
        :class="{ selected: option.value === modelValue }"
        :disabled="option.disabled"
        role="option"
        :aria-selected="option.value === modelValue"
        @click="choose(option)"
      >
        <span>{{ option.label }}</span>
        <svg v-if="option.value === modelValue" viewBox="0 0 24 24" aria-hidden="true">
          <path d="m5 12 4 4L19 6"></path>
        </svg>
      </button>
    </div>
  </div>
</template>
