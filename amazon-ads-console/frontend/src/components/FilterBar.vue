<script setup lang="ts">
import { ref } from 'vue'
import { NButton, NDatePicker, NSelect } from 'naive-ui'

const emit = defineEmits<{ query: [payload: { accountId: string; date: string }] }>()
const accounts = [
  { label: '川鹏', id: 'amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh', date: '2026-08-26' },
  { label: '欧德思', id: 'amzn1.ads-account.g.dfa7o7cwdl371d634ew58i919', date: '2026-08-25' },
  { label: '洁博利', id: 'amzn1.ads-account.g.6wudif27px024b6yk7v98vtwh', date: '2026-09-04' },
  { label: 'AMS', id: 'amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz', date: '2026-08-27' },
]
const accountOptions = accounts.map(a => ({ label:`店铺：${a.label}`, value:a.id }))
const accountId = ref(accounts[0].id)
const day = ref(accounts[0].date)
const onAccount = (value:string) => {
  accountId.value = value
  const item = accounts.find(x => x.id === value)
  if (item) day.value = item.date
}
const submit = () => emit('query', { accountId: accountId.value, date: day.value })
</script>

<template>
  <div class="filters naive-filters">
    <NSelect :value="accountId" :options="accountOptions" style="width:190px" @update:value="onAccount" />
    <NDatePicker
      :formatted-value="day || null"
      value-format="yyyy-MM-dd"
      type="date"
      clearable
      style="width:150px"
      @update:formatted-value="v => day = v || ''"
    />
    <NButton type="primary" :disabled="!day" @click="submit">查询</NButton>
  </div>
</template>

<style scoped>
.naive-filters{align-items:center}
</style>
