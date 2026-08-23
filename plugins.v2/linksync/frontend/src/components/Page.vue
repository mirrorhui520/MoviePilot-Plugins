<script setup>
import { ref, computed, onMounted, inject } from 'vue'

// 主应用注入的能力
const props = defineProps({
  api: { type: Object, default: () => ({}) },
  nativeSubscribe: { type: Function, default: null },
  show_switch: { type: Boolean, default: true },
})
const emit = defineEmits(['action', 'switch', 'close'])
const toast = inject('moviepilot:toast', null)

const ROOT = '_ROOT_'

// ---------------- 数据 ----------------
const loading = ref(false)
const data = ref({ total: 0, mons: [] })

// ---------------- UI 本地状态（全部前端管理，交互即时无重绘） ----------------
const curMon = ref('')
const curDir = ref('') // 专辑名 或 ROOT
const search = ref('') // 目录版块搜索关键词
const pageSize = ref('all') // 'all' | 10 | 50
const monPage = ref(1)
const filePage = ref(1)
const collapsed = ref(false) // 目录版块折叠

const pageSizeItems = [
  { title: '不限制', value: 'all' },
  { title: '10 条/页', value: 10 },
  { title: '50 条/页', value: 50 },
]

// 当前监控目录对象
const curMonObj = computed(
  () => data.value.mons.find((m) => m.mon === curMon.value) || data.value.mons[0] || null,
)

// 过滤后的专辑列表（前端实时搜索）
const filteredAlbums = computed(() => {
  const mon = curMonObj.value
  if (!mon) return []
  const kw = search.value.trim().toLowerCase()
  if (!kw) return mon.albums || []
  return (mon.albums || []).filter((a) => a.name.toLowerCase().includes(kw))
})

// 当前文件列表（选中专辑 或 根目录）
const currentFiles = computed(() => {
  const mon = curMonObj.value
  if (!mon) return []
  if (curDir.value === ROOT) return mon.root_files || []
  const album = (mon.albums || []).find((a) => a.name === curDir.value)
  return album ? album.files || [] : []
})

// 目录分页
const monTotalPages = computed(() => {
  if (pageSize.value === 'all') return 1
  return Math.max(1, Math.ceil(filteredAlbums.value.length / pageSize.value))
})
const pagedAlbums = computed(() => {
  if (pageSize.value === 'all') return filteredAlbums.value
  const s = (monPage.value - 1) * pageSize.value
  return filteredAlbums.value.slice(s, s + pageSize.value)
})

// 文件分页
const fileTotalPages = computed(() => {
  if (pageSize.value === 'all') return 1
  return Math.max(1, Math.ceil(currentFiles.value.length / pageSize.value))
})
const pagedFiles = computed(() => {
  if (pageSize.value === 'all') return currentFiles.value
  const s = (filePage.value - 1) * pageSize.value
  return currentFiles.value.slice(s, s + pageSize.value)
})

// 折叠后保留的“当前选中专辑行”（选中专辑或根）
const selectedRow = computed(() => {
  const mon = curMonObj.value
  if (!mon) return null
  if (curDir.value === ROOT) {
    return { name: '（根目录下文件）', count: (mon.root_files || []).length, last_time: '', isRoot: true }
  }
  const album = (mon.albums || []).find((a) => a.name === curDir.value)
  if (album) return { ...album, isRoot: false }
  return null
})

// ---------------- 数据加载 ----------------
async function load() {
  loading.value = true
  try {
    const res = await props.api.get('plugin/LinkSync/page_data')
    data.value = res?.data || { total: 0, mons: [] }
    if (!curMon.value || !data.value.mons.some((m) => m.mon === curMon.value)) {
      curMon.value = data.value.mons[0]?.mon || ''
    }
    const mon = data.value.mons.find((m) => m.mon === curMon.value)
    if (mon) {
      const names = (mon.albums || []).map((a) => a.name)
      if (curDir.value !== ROOT && curDir.value && !names.includes(curDir.value)) {
        curDir.value = names[0] || ''
      }
    }
  } catch (e) {
    console.error(e)
    toast?.error('数据加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}
onMounted(load)

// ---------------- 通用 API 调用 ----------------
async function callApi(path, params, successMsg) {
  try {
    const res = await props.api.get(`plugin/LinkSync/${path}`, { params })
    if (res?.success) {
      toast?.success(res?.message || successMsg || '操作成功')
      await load()
      return true
    }
    toast?.error(res?.message || '操作失败')
    return false
  } catch (e) {
    console.error(e)
    toast?.error('操作失败')
    return false
  }
}

function syncAll() {
  callApi('realtime_sync', {}, '已触发全量同步')
}

// ---------------- 删除 / 清空确认弹窗 ----------------
const confirm = ref({ show: false, title: '', text: '', api: '', params: {}, mode: '' })
const lastMode = ref('both') // 记忆上次使用的删除模式，下次打开弹窗默认选中
const confirmModes = [
  { value: 'both', label: '文件+记录', color: 'error', variant: 'flat', desc: '删除目标文件并从记录移除' },
  { value: 'target', label: '仅删文件', color: 'error', variant: 'tonal', desc: '仅删除目标目录真实文件（保留记录）' },
  { value: 'record', label: '仅清记录', color: 'grey-darken-2', variant: 'tonal', desc: '仅从记录中移除（保留目标文件）' },
]

function askDeleteAlbum(album) {
  const mon = curMonObj.value
  if (!mon) return
  confirm.value = {
    show: true,
    title: `删除专辑目录「${album.name}」`,
    text: `将按所选模式处理目标目录「${mon.target_root || ''}」下的专辑「${album.name}」（共 ${album.count} 个文件记录）。仅作用于目标目录，不影响源（监控）目录。`,
    api: 'delete',
    params: { mon_path: mon.mon, rel: album.name, is_dir: 1 },
    mode: lastMode.value,
  }
}

function askClear() {
  confirm.value = {
    show: true,
    title: '清空全部目标目录',
    text: '将按所选模式处理全部监控目录对应的目标目录下所有内容（文件夹与文件）及其记录。此操作不可恢复，请谨慎操作。',
    api: 'clear',
    params: {},
    mode: lastMode.value,
  }
}

function setConfirmMode(mode) {
  confirm.value.mode = mode
}

function runConfirm() {
  const c = confirm.value
  const params = { ...c.params, mode: c.mode }
  confirm.value.show = false
  lastMode.value = c.mode // 记住本次使用的模式，下次弹窗默认选中
  callApi(c.api, params, '处理完成')
}

// ---------------- 交互 ----------------
function selectDir(dir) {
  curDir.value = dir
  filePage.value = 1
}

function onMonChange() {
  curDir.value = ''
  monPage.value = 1
  filePage.value = 1
}

function onPageSizeChange() {
  monPage.value = 1
  filePage.value = 1
}
</script>

<template>
  <div
    class="plugin-page d-flex flex-column ga-3"
    style="overflow-x: hidden; overflow-y: auto; max-width: 100%; min-width: 0; max-height: calc(100dvh - 170px); scrollbar-gutter: stable; padding: 16px; box-sizing: border-box"
  >
    <v-alert type="info" variant="tonal" density="compact">
      目录版块展示目标目录下的一级专辑，点击专辑筛选右侧文件记录列表；删除仅作用于目标目录下的该专辑及其记录，不影响源（监控）目录。
    </v-alert>

    <!-- 顶部操作区 -->
    <v-row dense align="center">
      <v-col cols="12" sm="auto">
        <v-btn color="primary" variant="flat" @click="load">刷新列表</v-btn>
      </v-col>
      <v-col cols="12" sm="auto">
        <v-btn color="primary" variant="tonal" @click="syncAll">立即全量同步</v-btn>
      </v-col>
      <v-col cols="12" sm="auto">
        <v-btn color="error" variant="tonal" prepend-icon="mdi-delete-outline" @click="askClear">
          清空全部目标目录
        </v-btn>
      </v-col>
    </v-row>

    <!-- 监控目录切换 + 每页条数 -->
    <v-row dense align="center" v-if="data.mons.length > 1">
      <v-col cols="12" sm="auto">
        <span class="text-caption text-grey-darken-1">切换监控目录：</span>
      </v-col>
      <v-col style="min-width: 0">
        <v-btn-toggle
          v-model="curMon"
          mandatory
          density="compact"
          class="w-100"
          style="overflow-x: auto; max-width: 100%"
          @update:model-value="onMonChange"
        >
          <v-btn v-for="m in data.mons" :key="m.mon" :value="m.mon" size="small">
            {{ m.mon }}（{{ m.total }}）
          </v-btn>
        </v-btn-toggle>
      </v-col>
    </v-row>
    <v-row dense align="center">
      <v-col cols="12" sm="auto">
        <span class="text-caption text-grey-darken-1">每页条数：</span>
      </v-col>
      <v-col cols="auto">
        <v-btn-toggle v-model="pageSize" density="compact" mandatory @update:model-value="onPageSizeChange">
          <v-btn v-for="item in pageSizeItems" :key="item.value" :value="item.value" size="small">
            {{ item.title }}
          </v-btn>
        </v-btn-toggle>
      </v-col>
      <v-col cols="auto" class="ml-auto">
        <span class="text-caption text-grey">共 {{ data.total }} 条转移记录</span>
      </v-col>
    </v-row>

    <v-divider />

    <!-- 空状态 -->
    <div v-if="!loading && data.total === 0" class="text-center text-grey pa-6">
      暂无转移记录，新文件转移完成后会出现在这里。
    </div>

    <!-- 左右分栏：目录版块 + 文件记录列表 -->
    <v-row v-else dense>
      <!-- 目录版块 -->
      <v-col cols="12" md="6">
        <v-card variant="tonal" density="comfortable" class="h-100">
          <v-card-title class="d-flex align-center ga-2 text-subtitle-2 text-primary">
            <span class="text-truncate" style="flex: 1 1 auto; min-width: 0">目录版块 — {{ curMonObj?.target_root || '' }} / 一级专辑</span>
            <v-spacer />
            <v-text-field
              v-model="search"
              density="compact"
              hide-details
              clearable
              placeholder="搜索专辑"
              prepend-inner-icon="mdi-magnify"
              style="max-width: 220px"
            />
            <v-btn
              icon
              size="small"
              variant="text"
              :title="collapsed ? '展开目录版块' : '收起目录版块'"
              @click="collapsed = !collapsed"
            >
              <v-icon>{{ collapsed ? 'mdi-chevron-down' : 'mdi-chevron-up' }}</v-icon>
            </v-btn>
          </v-card-title>
          <v-card-text class="pa-1" style="max-height: 420px; overflow-y: auto; scrollbar-gutter: stable">
            <div v-if="loading" class="pa-4"><v-progress-linear indeterminate /></div>
            <template v-else-if="!collapsed">
              <div
                v-for="album in pagedAlbums"
                :key="album.name"
                class="d-flex align-center ga-1 py-1 px-2 album-row"
                :class="curDir === album.name ? 'bg-primary-lighten-5 rounded' : ''"
              >
                <div
                  class="d-flex align-center flex-grow-1 album-name"
                  style="min-width: 0; cursor: pointer"
                  @click="selectDir(album.name)"
                >
                  <v-icon
                    size="small"
                    class="me-1 flex-shrink-0"
                    :color="curDir === album.name ? 'primary' : 'grey-darken-1'"
                  >
                    {{ curDir === album.name ? 'mdi-check' : 'mdi-folder' }}
                  </v-icon>
                  <span class="text-truncate text-body-2">{{ album.name }}（{{ album.count }}）</span>
                </div>
                <span v-if="album.last_time" class="text-caption text-grey flex-shrink-0 ms-1">
                  {{ album.last_time }}
                </span>
                <v-btn
                  icon
                  size="x-small"
                  color="error"
                  variant="text"
                  title="删除专辑"
                  @click="askDeleteAlbum(album)"
                >
                  <v-icon size="small">mdi-delete-outline</v-icon>
                </v-btn>
              </div>
              <!-- 根目录下文件查看行 -->
              <div
                v-if="curMonObj?.root_files?.length"
                class="d-flex align-center ga-1 py-1 px-2 album-row"
                :class="curDir === ROOT ? 'bg-primary-lighten-5 rounded' : ''"
              >
                <div
                  class="d-flex align-center flex-grow-1 album-name"
                  style="min-width: 0; cursor: pointer"
                  @click="selectDir(ROOT)"
                >
                  <v-icon
                    size="small"
                    class="me-1 flex-shrink-0"
                    :color="curDir === ROOT ? 'primary' : 'grey-darken-1'"
                  >
                    {{ curDir === ROOT ? 'mdi-check' : 'mdi-format-list-bulleted' }}
                  </v-icon>
                  <span class="text-truncate text-body-2">根目录下文件（{{ curMonObj.root_files.length }}）</span>
                </div>
              </div>
              <div v-if="filteredAlbums.length === 0 && !curMonObj?.root_files?.length" class="text-grey text-caption pa-2">
                该监控目录暂无转移记录
              </div>
              <div v-if="filteredAlbums.length === 0 && search" class="text-grey text-caption pa-2">
                未找到匹配「{{ search }}」的专辑
              </div>
            </template>
            <!-- 折叠后仅保留当前选中行 -->
            <template v-else>
              <div v-if="selectedRow" class="d-flex align-center ga-1 py-1 px-2 bg-primary-lighten-5 rounded album-row">
                <div
                  class="d-flex align-center flex-grow-1 album-name"
                  style="min-width: 0; cursor: pointer"
                  @click="collapsed = false"
                >
                  <v-icon size="small" class="me-1 flex-shrink-0" color="primary">mdi-check</v-icon>
                  <span class="text-truncate text-body-2">{{ selectedRow.name }}（{{ selectedRow.count }}）</span>
                </div>
                <span v-if="selectedRow.last_time" class="text-caption text-grey flex-shrink-0 ms-1">
                  {{ selectedRow.last_time }}
                </span>
                <v-btn
                  v-if="!selectedRow.isRoot"
                  icon
                  size="x-small"
                  color="error"
                  variant="text"
                  title="删除专辑"
                  @click="askDeleteAlbum(selectedRow)"
                >
                  <v-icon size="small">mdi-delete-outline</v-icon>
                </v-btn>
              </div>
            </template>
          </v-card-text>
          <!-- 目录分页 -->
          <v-card-actions v-if="pageSize !== 'all' && monTotalPages > 1" class="pt-0">
            <v-pagination v-model="monPage" :length="monTotalPages" density="compact" total-visible="5" />
          </v-card-actions>
        </v-card>
      </v-col>

      <!-- 文件记录列表 -->
      <v-col cols="12" md="6">
        <v-card variant="tonal" density="comfortable" class="h-100">
          <v-card-title class="text-subtitle-2 text-primary text-truncate">
            文件记录列表 — {{ curDir === ROOT ? '目标目录根下直接转移的文件' : (curDir || '请选择专辑') }}
          </v-card-title>
          <v-card-text class="pa-1" style="max-height: 420px; overflow-y: auto; scrollbar-gutter: stable">
            <div v-if="loading" class="pa-4"><v-progress-linear indeterminate /></div>
            <template v-else>
              <div v-for="f in pagedFiles" :key="f.rel" class="d-flex align-center ga-1 py-1 px-2">
                <v-icon size="small" color="grey" class="flex-shrink-0">mdi-music-note-plus</v-icon>
                <span class="text-body-2 text-truncate" style="flex: 1 1 auto; min-width: 0" :title="f.rel">
                  {{ f.rel }}
                </span>
                <span v-if="f.time" class="text-caption text-grey flex-shrink-0">{{ f.time }}</span>
                <v-chip v-if="f.mode" size="x-small" color="primary" variant="tonal" class="flex-shrink-0">
                  {{ f.mode }}
                </v-chip>
              </div>
              <div v-if="pagedFiles.length === 0" class="text-grey text-caption pa-2">
                当前目录暂无已转移文件记录。
              </div>
            </template>
          </v-card-text>
          <!-- 文件分页 -->
          <v-card-actions v-if="pageSize !== 'all' && fileTotalPages > 1" class="pt-0">
            <v-pagination v-model="filePage" :length="fileTotalPages" density="compact" total-visible="5" />
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <!-- 删除/清空确认弹窗：点击后延伸三种模式选择 -->
    <v-dialog v-model="confirm.show" max-width="520">
      <v-card>
        <v-card-title class="text-subtitle-1">{{ confirm.title }}</v-card-title>
        <v-card-text>
          <p class="text-body-2 text-grey">{{ confirm.text }}</p>
          <v-list density="compact">
            <v-list-item
              v-for="mode in confirmModes"
              :key="mode.value"
              :active="confirm.mode === mode.value"
              @click="setConfirmMode(mode.value)"
            >
              <template #prepend>
                <v-icon :color="confirm.mode === mode.value ? mode.color : ''">
                  {{ confirm.mode === mode.value ? 'mdi-radiobox-marked' : 'mdi-radiobox-blank' }}
                </v-icon>
              </template>
              <v-list-item-title>{{ mode.label }}</v-list-item-title>
              <v-list-item-subtitle>{{ mode.desc }}</v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="grey" variant="text" @click="confirm.show = false">取消</v-btn>
          <v-btn color="error" variant="flat" @click="runConfirm">确认执行</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 右下角跳转设置页按钮（与主应用 Vuetify 渲染模式的 VFab 一致） -->
    <v-btn
      v-if="show_switch"
      icon
      color="primary"
      size="large"
      rounded="circle"
      elevation="4"
      class="position-fixed"
      style="bottom: 24px; right: 24px; z-index: 120"
      title="插件设置"
      @click="emit('switch')"
    >
      <v-icon>mdi-cog</v-icon>
    </v-btn>
  </div>
</template>

<style scoped>
/* 目录条目悬停反馈（左对齐文本区域） */
.album-name:hover {
  background-color: rgba(0, 0, 0, 0.06);
}
</style>
