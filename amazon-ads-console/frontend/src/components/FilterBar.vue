<script setup lang="ts">
import { ref } from 'vue'
import { NButton, NDatePicker, NSelect } from 'naive-ui'

const props = defineProps<{ latestDate?: string; loading?: boolean }>()
const emit = defineEmits<{ query: [payload: { accountId: string; date: string }] }>()
const accounts = [
  { label: '川鹏', id: 'amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh' },
  { label: '欧德思', id: 'amzn1.ads-account.g.dfa7o7cwdl371d634ew58i919' },
  { label: '洁博利', id: 'amzn1.ads-account.g.6wudif27px024b6yk7v98vtwh' },
  { label: 'AMS', id: 'amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz' },
]
const accountOptions = accounts.map(a => ({ label:`店铺：${a.label}`, value:a.id }))
const accountId = ref(accounts[0].id)
const day = ref('')
const followLatest = ref(true)
const onAccount = (value:string) => {
  accountId.value = value
  day.value = ''
  followLatest.value = true
  submit()
}
const submit = () => emit('query', { accountId: accountId.value, date: followLatest.value ? '' : day.value })
const latest = () => { day.value = ''; followLatest.value = true; submit() }
const selectDay = (value: string | null) => { day.value = value || ''; followLatest.value = !value }
</script>

<template>
  <div class="filters naive-filters">
    <NSelect :value="accountId" :options="accountOptions" style="width:190px" @update:value="onAccount" />
    <NDatePicker
      :formatted-value="(followLatest ? props.latestDate : day) || null"
      value-format="yyyy-MM-dd"
      type="date"
      clearable
      style="width:150px"
      @update:formatted-value="selectDay"
    />
    <NButton type="primary" :disabled="props.loading" @click="submit">查询</NButton>
    <NButton :disabled="props.loading" @click="latest">最新数据</NButton>
    <span v-if="followLatest">自动跟随最新入库日期</span>
  </div>
</template>

<style scoped>
.naive-filters{align-items:center}
</style>
