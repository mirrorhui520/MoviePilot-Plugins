<script setup>
import { ref, inject } from 'vue'

const props = defineProps({
  initialConfig: { type: Object, default: () => ({}) },
  api: { type: Object, default: () => ({}) },
  nativeSubscribe: { type: Function, default: null },
})
const emit = defineEmits(['save', 'close', 'switch'])
const toast = inject('moviepilot:toast', null)

const config = ref({
  enabled: false,
  notify: false,
  onlyonce: false,
  mode: 'fast',
  transfer_type: 'link',
  size: '',
  flush_interval: 3,
  concurrency: 4,
  exists_mode: 'skip',
  delete_mode: 'both',
  cron: '',
  monitor_dirs: '',
  exclude_keywords: '',
  ...props.initialConfig,
})

const modeItems = [
  { title: '兼容模式', value: 'compatibility' },
  { title: '性能模式', value: 'fast' },
]
const transferItems = [
  { title: '硬链接', value: 'link' },
  { title: '复制', value: 'copy' },
  { title: '移动', value: 'move' },
]
const existsItems = [
  { title: '跳过', value: 'skip' },
  { title: '覆盖', value: 'overwrite' },
]
const deleteItems = [
  { title: '同时删除目标文件并从记录移除', value: 'both' },
  { title: '仅删除目标目录真实文件（保留记录）', value: 'target' },
  { title: '仅从记录中移除（保留目标文件）', value: 'record' },
]

function saveConfig() {
  emit('save', config.value)
}

function notifyClose() {
  emit('close')
}
</script>

<template>
  <v-form
    class="pa-4"
    style="overflow-x: hidden; overflow-y: auto; max-width: 100%; min-width: 0; max-height: calc(100dvh - 170px); scrollbar-gutter: stable"
  >
    <v-row>
      <v-col cols="12" md="4">
        <v-switch v-model="config.enabled" label="启用插件" color="primary" />
      </v-col>
      <v-col cols="12" md="4">
        <v-switch v-model="config.notify" label="发送通知" color="primary" />
      </v-col>
      <v-col cols="12" md="4">
        <v-switch v-model="config.onlyonce" label="立即运行一次" color="primary" />
      </v-col>
      <v-col cols="12" md="4">
        <v-select v-model="config.mode" :items="modeItems" label="监控模式" density="compact" hide-details />
      </v-col>
      <v-col cols="12" md="4">
        <v-select v-model="config.transfer_type" :items="transferItems" label="转移方式" density="compact" hide-details />
      </v-col>
      <v-col cols="12" md="4">
        <v-text-field v-model="config.size" label="最小文件大小（KB）" density="compact" hide-details />
      </v-col>
      <v-col cols="12" md="4">
        <v-text-field
          v-model="config.flush_interval"
          label="通知汇总刷新间隔（秒）"
          density="compact"
          hide-details
          placeholder="默认3，实时事件间隔内聚合为一条通知"
        />
      </v-col>
      <v-col cols="12" md="4">
        <v-text-field
          v-model="config.concurrency"
          label="并发转移数"
          density="compact"
          hide-details
          placeholder="默认4，全量同步并行转移数量"
        />
      </v-col>
      <v-col cols="12" md="4">
        <v-select v-model="config.exists_mode" :items="existsItems" label="目标已存在处理" density="compact" hide-details />
      </v-col>
      <v-col cols="12" md="6">
        <v-select v-model="config.delete_mode" :items="deleteItems" label="详情页删除模式" density="compact" hide-details />
      </v-col>
      <v-col cols="12">
        <v-text-field
          v-model="config.cron"
          label="定时全量同步周期"
          density="compact"
          hide-details
          placeholder="5位cron表达式，留空关闭"
        />
      </v-col>
      <v-col cols="12">
        <v-textarea
          v-model="config.monitor_dirs"
          label="监控目录"
          rows="5"
          placeholder="每一行一个目录，支持以下几种配置方式：&#10;监控目录&#10;监控目录:转移目的目录"
        />
      </v-col>
      <v-col cols="12">
        <v-textarea
          v-model="config.exclude_keywords"
          label="排除关键词"
          rows="2"
          placeholder="每一行一个关键词"
        />
      </v-col>
      <v-col cols="12">
        <v-alert type="info" variant="tonal">
          转移方式：硬链接不占用额外空间、复制会生成副本、移动会删除源文件。
          最小文件大小：小于最小文件大小的文件将直接复制，其余按转移方式处理。
          目标已存在处理：跳过则不重复转移，覆盖会先删除已存在目标再转移。
          通知为批量汇总：全量同步结束后发送一次，实时模式下按“通知汇总刷新间隔”聚合发送。
        </v-alert>
      </v-col>
    </v-row>
    <v-row class="mt-2">
      <v-col cols="12" class="d-flex justify-end">
        <v-btn color="primary" variant="flat" @click="saveConfig">保存</v-btn>
      </v-col>
    </v-row>
  </v-form>
</template>
