<script setup lang="ts">
import { computed } from "vue";
import { icons } from "../config";

const props = defineProps<{ name: string }>();
const svg = computed(() => icons[props.name] || "");
</script>

<template>
  <span v-html="svg"></span>
</template>
