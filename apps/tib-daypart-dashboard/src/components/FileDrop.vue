<script setup lang="ts">
import { computed, ref } from "vue";

const props = defineProps<{
  title: string;
  description: string;
  file?: File;
  accept?: string;
}>();

const emit = defineEmits<{
  change: [file: File];
}>();

const dragging = ref(false);
const input = ref<HTMLInputElement>();
const fileLabel = computed(() => props.file?.name ?? "选择或拖入 CSV");

function pick(files: FileList | null): void {
  const file = files?.[0];
  if (file) emit("change", file);
}
</script>

<template>
  <button
    type="button"
    class="file-drop"
    :class="{ 'file-drop--active': dragging, 'file-drop--ready': file }"
    @click="input?.click()"
    @dragenter.prevent="dragging = true"
    @dragover.prevent="dragging = true"
    @dragleave.prevent="dragging = false"
    @drop.prevent="
      dragging = false;
      pick($event.dataTransfer?.files ?? null);
    "
  >
    <input
      ref="input"
      class="sr-only"
      type="file"
      :accept="accept ?? '.csv,text/csv'"
      @change="pick(($event.target as HTMLInputElement).files)"
    />
    <span class="file-drop__icon">{{ file ? "✓" : "＋" }}</span>
    <span class="file-drop__copy">
      <strong>{{ title }}</strong>
      <small>{{ description }}</small>
      <span>{{ fileLabel }}</span>
    </span>
  </button>
</template>
