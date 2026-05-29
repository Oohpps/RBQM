<script setup lang="ts">
import { computed } from "vue";
import type { DataRow } from "../types";

const props = withDefaults(
  defineProps<{
    rows: DataRow[];
    preferredColumns?: string[] | null;
    limit?: number | null;
    emptyText: string;
  }>(),
  {
    preferredColumns: null,
    limit: null,
  },
);

const data = computed(() => (props.limit ? props.rows.slice(0, props.limit) : props.rows));
const columns = computed(() => {
  if (!data.value.length) return [];
  const preferred = props.preferredColumns?.filter((column) => column in data.value[0]) || [];
  return preferred.length ? preferred : Object.keys(data.value[0]);
});

function isNumericColumn(column: string): boolean {
  return data.value.some((row) => typeof row[column] === "number");
}

function formatCell(value: string | number | boolean | null | string[] | undefined): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.join("、");
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  return String(value);
}
</script>

<template>
  <table>
    <tbody v-if="!data.length">
      <tr>
        <td>{{ emptyText }}</td>
      </tr>
    </tbody>
    <template v-else>
      <thead>
        <tr>
          <th v-for="column in columns" :key="column" :class="{ number: isNumericColumn(column) }">
            {{ column }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, rowIndex) in data" :key="rowIndex">
          <td v-for="column in columns" :key="column" :class="{ number: isNumericColumn(column) }">
            {{ formatCell(row[column]) }}
          </td>
        </tr>
      </tbody>
    </template>
  </table>
</template>
