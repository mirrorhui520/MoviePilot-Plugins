import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const {createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createBlock:_createBlock,createCommentVNode:_createCommentVNode,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = {
  class: "plugin-page d-flex flex-column ga-3",
  style: {"overflow-x":"hidden","overflow-y":"auto","max-width":"100%","min-width":"0","max-height":"calc(100dvh - 170px)","scrollbar-gutter":"stable"}
};
const _hoisted_2 = { class: "d-flex align-center ga-2" };
const _hoisted_3 = { class: "text-caption text-grey" };
const _hoisted_4 = {
  key: 1,
  class: "text-center text-grey pa-6"
};
const _hoisted_5 = {
  class: "text-truncate",
  style: {"flex":"1 1 auto","min-width":"0"}
};
const _hoisted_6 = {
  key: 0,
  class: "pa-4"
};
const _hoisted_7 = {
  key: 0,
  class: "text-caption text-grey flex-shrink-0 ms-1"
};
const _hoisted_8 = {
  key: 1,
  class: "text-grey text-caption pa-2"
};
const _hoisted_9 = {
  key: 2,
  class: "text-grey text-caption pa-2"
};
const _hoisted_10 = {
  key: 0,
  class: "d-flex align-center ga-1 py-1 px-2 bg-primary-lighten-5 rounded"
};
const _hoisted_11 = {
  key: 0,
  class: "text-caption text-grey flex-shrink-0 ms-1"
};
const _hoisted_12 = {
  key: 0,
  class: "pa-4"
};
const _hoisted_13 = ["title"];
const _hoisted_14 = {
  key: 0,
  class: "text-caption text-grey flex-shrink-0"
};
const _hoisted_15 = {
  key: 0,
  class: "text-grey text-caption pa-2"
};
const _hoisted_16 = { class: "text-body-2 text-grey" };

const {ref,computed,onMounted,inject} = await importShared('vue');


// 主应用注入的能力
const ROOT = '_ROOT_';

// ---------------- 数据 ----------------

const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: Object, default: () => ({}) },
  nativeSubscribe: { type: Function, default: null },
},
  emits: ['action', 'switch', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;
const toast = inject('moviepilot:toast', null);

const loading = ref(false);
const data = ref({ total: 0, mons: [] });

// ---------------- UI 本地状态（全部前端管理，交互即时无重绘） ----------------
const curMon = ref('');
const curDir = ref(''); // 专辑名 或 ROOT
const search = ref(''); // 目录版块搜索关键词
const pageSize = ref('all'); // 'all' | 10 | 50
const monPage = ref(1);
const filePage = ref(1);
const collapsed = ref(false); // 目录版块折叠

const pageSizeItems = [
  { title: '不限制', value: 'all' },
  { title: '10 条/页', value: 10 },
  { title: '50 条/页', value: 50 },
];

// 当前监控目录对象
const curMonObj = computed(
  () => data.value.mons.find((m) => m.mon === curMon.value) || data.value.mons[0] || null,
);

// 过滤后的专辑列表（前端实时搜索）
const filteredAlbums = computed(() => {
  const mon = curMonObj.value;
  if (!mon) return []
  const kw = search.value.trim().toLowerCase();
  if (!kw) return mon.albums || []
  return (mon.albums || []).filter((a) => a.name.toLowerCase().includes(kw))
});

// 当前文件列表（选中专辑 或 根目录）
const currentFiles = computed(() => {
  const mon = curMonObj.value;
  if (!mon) return []
  if (curDir.value === ROOT) return mon.root_files || []
  const album = (mon.albums || []).find((a) => a.name === curDir.value);
  return album ? album.files || [] : []
});

// 目录分页
const monTotalPages = computed(() => {
  if (pageSize.value === 'all') return 1
  return Math.max(1, Math.ceil(filteredAlbums.value.length / pageSize.value))
});
const pagedAlbums = computed(() => {
  if (pageSize.value === 'all') return filteredAlbums.value
  const s = (monPage.value - 1) * pageSize.value;
  return filteredAlbums.value.slice(s, s + pageSize.value)
});

// 文件分页
const fileTotalPages = computed(() => {
  if (pageSize.value === 'all') return 1
  return Math.max(1, Math.ceil(currentFiles.value.length / pageSize.value))
});
const pagedFiles = computed(() => {
  if (pageSize.value === 'all') return currentFiles.value
  const s = (filePage.value - 1) * pageSize.value;
  return currentFiles.value.slice(s, s + pageSize.value)
});

// 折叠后保留的“当前选中专辑行”（选中专辑或根）
const selectedRow = computed(() => {
  const mon = curMonObj.value;
  if (!mon) return null
  if (curDir.value === ROOT) {
    return { name: '（根目录下文件）', count: (mon.root_files || []).length, last_time: '', isRoot: true }
  }
  const album = (mon.albums || []).find((a) => a.name === curDir.value);
  if (album) return { ...album, isRoot: false }
  return null
});

// ---------------- 数据加载 ----------------
async function load() {
  loading.value = true;
  try {
    const res = await props.api.get('plugin/LinkSync/page_data');
    data.value = res?.data || { total: 0, mons: [] };
    if (!curMon.value || !data.value.mons.some((m) => m.mon === curMon.value)) {
      curMon.value = data.value.mons[0]?.mon || '';
    }
    const mon = data.value.mons.find((m) => m.mon === curMon.value);
    if (mon) {
      const names = (mon.albums || []).map((a) => a.name);
      if (curDir.value !== ROOT && curDir.value && !names.includes(curDir.value)) {
        curDir.value = names[0] || '';
      }
    }
  } catch (e) {
    console.error(e);
    toast?.error('数据加载失败，请稍后重试');
  } finally {
    loading.value = false;
  }
}
onMounted(load);

// ---------------- 通用 API 调用 ----------------
async function callApi(path, params, successMsg) {
  try {
    const res = await props.api.get(`plugin/LinkSync/${path}`, { params });
    if (res?.success) {
      toast?.success(res?.message || successMsg || '操作成功');
      await load();
      return true
    }
    toast?.error(res?.message || '操作失败');
    return false
  } catch (e) {
    console.error(e);
    toast?.error('操作失败');
    return false
  }
}

function syncAll() {
  callApi('realtime_sync', {}, '已触发全量同步');
}

// ---------------- 删除 / 清空确认弹窗 ----------------
const confirm = ref({ show: false, title: '', text: '', api: '', params: {}, mode: '' });
const confirmModes = [
  { value: 'both', label: '文件+记录', color: 'error', variant: 'flat', desc: '删除目标文件并从记录移除' },
  { value: 'target', label: '仅删文件', color: 'error', variant: 'tonal', desc: '仅删除目标目录真实文件（保留记录）' },
  { value: 'record', label: '仅清记录', color: 'grey-darken-2', variant: 'tonal', desc: '仅从记录中移除（保留目标文件）' },
];

function askDeleteAlbum(album) {
  const mon = curMonObj.value;
  if (!mon) return
  confirm.value = {
    show: true,
    title: `删除专辑目录「${album.name}」`,
    text: `将按所选模式处理目标目录「${mon.target_root || ''}」下的专辑「${album.name}」（共 ${album.count} 个文件记录）。仅作用于目标目录，不影响源（监控）目录。`,
    api: 'delete',
    params: { mon_path: mon.mon, rel: album.name, is_dir: 1 },
    mode: 'both',
  };
}

function askClear() {
  confirm.value = {
    show: true,
    title: '清空全部目标目录',
    text: '将按所选模式处理全部监控目录对应的目标目录下所有内容（文件夹与文件）及其记录。此操作不可恢复，请谨慎操作。',
    api: 'clear',
    params: {},
    mode: 'both',
  };
}

function setConfirmMode(mode) {
  confirm.value.mode = mode;
}

function runConfirm() {
  const c = confirm.value;
  const params = { ...c.params, mode: c.mode };
  confirm.value.show = false;
  callApi(c.api, params, '处理完成');
}

// ---------------- 交互 ----------------
function selectDir(dir) {
  curDir.value = dir;
  filePage.value = 1;
}

function onMonChange() {
  curDir.value = '';
  monPage.value = 1;
  filePage.value = 1;
}

function onPageSizeChange() {
  monPage.value = 1;
  filePage.value = 1;
}

return (_ctx, _cache) => {
  const _component_v_alert = _resolveComponent("v-alert");
  const _component_v_btn = _resolveComponent("v-btn");
  const _component_v_col = _resolveComponent("v-col");
  const _component_v_btn_group = _resolveComponent("v-btn-group");
  const _component_v_row = _resolveComponent("v-row");
  const _component_v_btn_toggle = _resolveComponent("v-btn-toggle");
  const _component_v_divider = _resolveComponent("v-divider");
  const _component_v_spacer = _resolveComponent("v-spacer");
  const _component_v_text_field = _resolveComponent("v-text-field");
  const _component_v_icon = _resolveComponent("v-icon");
  const _component_v_card_title = _resolveComponent("v-card-title");
  const _component_v_progress_linear = _resolveComponent("v-progress-linear");
  const _component_v_card_text = _resolveComponent("v-card-text");
  const _component_v_pagination = _resolveComponent("v-pagination");
  const _component_v_card_actions = _resolveComponent("v-card-actions");
  const _component_v_card = _resolveComponent("v-card");
  const _component_v_chip = _resolveComponent("v-chip");
  const _component_v_list_item_title = _resolveComponent("v-list-item-title");
  const _component_v_list_item_subtitle = _resolveComponent("v-list-item-subtitle");
  const _component_v_list_item = _resolveComponent("v-list-item");
  const _component_v_list = _resolveComponent("v-list");
  const _component_v_dialog = _resolveComponent("v-dialog");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_v_alert, {
      type: "info",
      variant: "tonal",
      density: "compact"
    }, {
      default: _withCtx(() => [...(_cache[11] || (_cache[11] = [
        _createTextVNode(" 目录版块展示目标目录下的一级专辑，点击专辑筛选右侧文件记录列表；删除仅作用于目标目录下的该专辑及其记录，不影响源（监控）目录。 ", -1)
      ]))]),
      _: 1
    }),
    _createVNode(_component_v_row, {
      dense: "",
      align: "center"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_v_col, {
          cols: "12",
          sm: "auto"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_btn, {
              color: "primary",
              variant: "flat",
              onClick: load
            }, {
              default: _withCtx(() => [...(_cache[12] || (_cache[12] = [
                _createTextVNode("刷新列表", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_v_col, {
          cols: "12",
          sm: "auto"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_btn, {
              color: "primary",
              variant: "tonal",
              onClick: syncAll
            }, {
              default: _withCtx(() => [...(_cache[13] || (_cache[13] = [
                _createTextVNode("立即全量同步", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_v_col, {
          cols: "12",
          sm: "auto"
        }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_2, [
              _cache[17] || (_cache[17] = _createElementVNode("span", { class: "text-caption text-grey-darken-1" }, "清空全部目标目录：", -1)),
              _createVNode(_component_v_btn_group, {
                density: "compact",
                rounded: "sm"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_btn, {
                    size: "x-small",
                    color: "error",
                    variant: "flat",
                    onClick: askClear
                  }, {
                    default: _withCtx(() => [...(_cache[14] || (_cache[14] = [
                      _createTextVNode("文件+记录", -1)
                    ]))]),
                    _: 1
                  }),
                  _createVNode(_component_v_btn, {
                    size: "x-small",
                    color: "error",
                    variant: "tonal",
                    onClick: askClear
                  }, {
                    default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
                      _createTextVNode("仅删文件", -1)
                    ]))]),
                    _: 1
                  }),
                  _createVNode(_component_v_btn, {
                    size: "x-small",
                    color: "grey-darken-2",
                    variant: "tonal",
                    onClick: askClear
                  }, {
                    default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
                      _createTextVNode("仅清记录", -1)
                    ]))]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ])
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    (data.value.mons.length > 1)
      ? (_openBlock(), _createBlock(_component_v_row, {
          key: 0,
          dense: "",
          align: "center"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_col, {
              cols: "12",
              sm: "auto"
            }, {
              default: _withCtx(() => [...(_cache[18] || (_cache[18] = [
                _createElementVNode("span", { class: "text-caption text-grey-darken-1" }, "切换监控目录：", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_v_col, { style: {"min-width":"0"} }, {
              default: _withCtx(() => [
                _createVNode(_component_v_btn_toggle, {
                  modelValue: curMon.value,
                  "onUpdate:modelValue": [
                    _cache[0] || (_cache[0] = $event => ((curMon).value = $event)),
                    onMonChange
                  ],
                  mandatory: "",
                  density: "compact",
                  class: "w-100",
                  style: {"overflow-x":"auto","max-width":"100%"}
                }, {
                  default: _withCtx(() => [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(data.value.mons, (m) => {
                      return (_openBlock(), _createBlock(_component_v_btn, {
                        key: m.mon,
                        value: m.mon,
                        size: "small"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(m.mon) + "（" + _toDisplayString(m.total) + "） ", 1)
                        ]),
                        _: 2
                      }, 1032, ["value"]))
                    }), 128))
                  ]),
                  _: 1
                }, 8, ["modelValue"])
              ]),
              _: 1
            })
          ]),
          _: 1
        }))
      : _createCommentVNode("", true),
    _createVNode(_component_v_row, {
      dense: "",
      align: "center"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_v_col, {
          cols: "12",
          sm: "auto"
        }, {
          default: _withCtx(() => [...(_cache[19] || (_cache[19] = [
            _createElementVNode("span", { class: "text-caption text-grey-darken-1" }, "每页条数：", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_v_col, { cols: "auto" }, {
          default: _withCtx(() => [
            _createVNode(_component_v_btn_toggle, {
              modelValue: pageSize.value,
              "onUpdate:modelValue": [
                _cache[1] || (_cache[1] = $event => ((pageSize).value = $event)),
                onPageSizeChange
              ],
              density: "compact",
              mandatory: ""
            }, {
              default: _withCtx(() => [
                (_openBlock(), _createElementBlock(_Fragment, null, _renderList(pageSizeItems, (item) => {
                  return _createVNode(_component_v_btn, {
                    key: item.value,
                    value: item.value,
                    size: "small"
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(item.title), 1)
                    ]),
                    _: 2
                  }, 1032, ["value"])
                }), 64))
              ]),
              _: 1
            }, 8, ["modelValue"])
          ]),
          _: 1
        }),
        _createVNode(_component_v_col, {
          cols: "auto",
          class: "ml-auto"
        }, {
          default: _withCtx(() => [
            _createElementVNode("span", _hoisted_3, "共 " + _toDisplayString(data.value.total) + " 条转移记录", 1)
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode(_component_v_divider),
    (!loading.value && data.value.total === 0)
      ? (_openBlock(), _createElementBlock("div", _hoisted_4, " 暂无转移记录，新文件转移完成后会出现在这里。 "))
      : (_openBlock(), _createBlock(_component_v_row, {
          key: 2,
          dense: ""
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_col, {
              cols: "12",
              md: "6"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_card, {
                  variant: "tonal",
                  density: "comfortable",
                  class: "h-100"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_card_title, { class: "d-flex align-center ga-2 text-subtitle-2 text-primary" }, {
                      default: _withCtx(() => [
                        _createElementVNode("span", _hoisted_5, "目录版块 — " + _toDisplayString(curMonObj.value?.target_root || '') + " / 一级专辑", 1),
                        _createVNode(_component_v_spacer),
                        _createVNode(_component_v_text_field, {
                          modelValue: search.value,
                          "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((search).value = $event)),
                          density: "compact",
                          "hide-details": "",
                          clearable: "",
                          placeholder: "搜索专辑",
                          "prepend-inner-icon": "mdi-magnify",
                          style: {"max-width":"220px"}
                        }, null, 8, ["modelValue"]),
                        _createVNode(_component_v_btn, {
                          icon: "",
                          size: "small",
                          variant: "text",
                          title: collapsed.value ? '展开目录版块' : '收起目录版块',
                          onClick: _cache[3] || (_cache[3] = $event => (collapsed.value = !collapsed.value))
                        }, {
                          default: _withCtx(() => [
                            _createVNode(_component_v_icon, null, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(collapsed.value ? 'mdi-chevron-down' : 'mdi-chevron-up'), 1)
                              ]),
                              _: 1
                            })
                          ]),
                          _: 1
                        }, 8, ["title"])
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_v_card_text, {
                      class: "pa-1",
                      style: {"max-height":"420px","overflow-y":"auto","scrollbar-gutter":"stable"}
                    }, {
                      default: _withCtx(() => [
                        (loading.value)
                          ? (_openBlock(), _createElementBlock("div", _hoisted_6, [
                              _createVNode(_component_v_progress_linear, { indeterminate: "" })
                            ]))
                          : (!collapsed.value)
                            ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(pagedAlbums.value, (album) => {
                                  return (_openBlock(), _createElementBlock("div", {
                                    key: album.name,
                                    class: _normalizeClass(["d-flex align-center ga-1 py-1 px-2", curDir.value === album.name ? 'bg-primary-lighten-5 rounded' : ''])
                                  }, [
                                    _createVNode(_component_v_btn, {
                                      size: "small",
                                      variant: "text",
                                      color: "primary",
                                      class: "text-truncate",
                                      style: {"flex":"1 1 auto","min-width":"0"},
                                      "prepend-icon": curDir.value === album.name ? 'mdi-check' : 'mdi-folder',
                                      onClick: $event => (selectDir(album.name))
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode(_toDisplayString(album.name) + "（" + _toDisplayString(album.count) + "） ", 1)
                                      ]),
                                      _: 2
                                    }, 1032, ["prepend-icon", "onClick"]),
                                    (album.last_time)
                                      ? (_openBlock(), _createElementBlock("span", _hoisted_7, _toDisplayString(album.last_time), 1))
                                      : _createCommentVNode("", true),
                                    _createVNode(_component_v_btn, {
                                      icon: "",
                                      size: "x-small",
                                      color: "error",
                                      variant: "text",
                                      title: "删除专辑",
                                      onClick: $event => (askDeleteAlbum(album))
                                    }, {
                                      default: _withCtx(() => [
                                        _createVNode(_component_v_icon, { size: "small" }, {
                                          default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
                                            _createTextVNode("mdi-delete-outline", -1)
                                          ]))]),
                                          _: 1
                                        })
                                      ]),
                                      _: 1
                                    }, 8, ["onClick"])
                                  ], 2))
                                }), 128)),
                                (curMonObj.value?.root_files?.length)
                                  ? (_openBlock(), _createElementBlock("div", {
                                      key: 0,
                                      class: _normalizeClass(["d-flex align-center ga-1 py-1 px-2", curDir.value === ROOT ? 'bg-primary-lighten-5 rounded' : ''])
                                    }, [
                                      _createVNode(_component_v_btn, {
                                        size: "small",
                                        variant: "text",
                                        class: "text-truncate",
                                        style: {"flex":"1 1 auto","min-width":"0"},
                                        "prepend-icon": curDir.value === ROOT ? 'mdi-check' : 'mdi-format-list-bulleted',
                                        onClick: _cache[4] || (_cache[4] = $event => (selectDir(ROOT)))
                                      }, {
                                        default: _withCtx(() => [
                                          _createTextVNode(" 根目录下文件（" + _toDisplayString(curMonObj.value.root_files.length) + "） ", 1)
                                        ]),
                                        _: 1
                                      }, 8, ["prepend-icon"])
                                    ], 2))
                                  : _createCommentVNode("", true),
                                (filteredAlbums.value.length === 0 && !curMonObj.value?.root_files?.length)
                                  ? (_openBlock(), _createElementBlock("div", _hoisted_8, " 该监控目录暂无转移记录 "))
                                  : _createCommentVNode("", true),
                                (filteredAlbums.value.length === 0 && search.value)
                                  ? (_openBlock(), _createElementBlock("div", _hoisted_9, " 未找到匹配「" + _toDisplayString(search.value) + "」的专辑 ", 1))
                                  : _createCommentVNode("", true)
                              ], 64))
                            : (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                                (selectedRow.value)
                                  ? (_openBlock(), _createElementBlock("div", _hoisted_10, [
                                      _createVNode(_component_v_btn, {
                                        size: "small",
                                        variant: "text",
                                        color: "primary",
                                        class: "text-truncate",
                                        style: {"flex":"1 1 auto","min-width":"0"},
                                        "prepend-icon": "mdi-check",
                                        onClick: _cache[5] || (_cache[5] = $event => (collapsed.value = false))
                                      }, {
                                        default: _withCtx(() => [
                                          _createTextVNode(_toDisplayString(selectedRow.value.name) + "（" + _toDisplayString(selectedRow.value.count) + "） ", 1)
                                        ]),
                                        _: 1
                                      }),
                                      (selectedRow.value.last_time)
                                        ? (_openBlock(), _createElementBlock("span", _hoisted_11, _toDisplayString(selectedRow.value.last_time), 1))
                                        : _createCommentVNode("", true),
                                      (!selectedRow.value.isRoot)
                                        ? (_openBlock(), _createBlock(_component_v_btn, {
                                            key: 1,
                                            icon: "",
                                            size: "x-small",
                                            color: "error",
                                            variant: "text",
                                            title: "删除专辑",
                                            onClick: _cache[6] || (_cache[6] = $event => (askDeleteAlbum(selectedRow.value)))
                                          }, {
                                            default: _withCtx(() => [
                                              _createVNode(_component_v_icon, { size: "small" }, {
                                                default: _withCtx(() => [...(_cache[21] || (_cache[21] = [
                                                  _createTextVNode("mdi-delete-outline", -1)
                                                ]))]),
                                                _: 1
                                              })
                                            ]),
                                            _: 1
                                          }))
                                        : _createCommentVNode("", true)
                                    ]))
                                  : _createCommentVNode("", true)
                              ], 64))
                      ]),
                      _: 1
                    }),
                    (pageSize.value !== 'all' && monTotalPages.value > 1)
                      ? (_openBlock(), _createBlock(_component_v_card_actions, {
                          key: 0,
                          class: "pt-0"
                        }, {
                          default: _withCtx(() => [
                            _createVNode(_component_v_pagination, {
                              modelValue: monPage.value,
                              "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((monPage).value = $event)),
                              length: monTotalPages.value,
                              density: "compact",
                              "total-visible": "5"
                            }, null, 8, ["modelValue", "length"])
                          ]),
                          _: 1
                        }))
                      : _createCommentVNode("", true)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_v_col, {
              cols: "12",
              md: "6"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_card, {
                  variant: "tonal",
                  density: "comfortable",
                  class: "h-100"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_card_title, { class: "text-subtitle-2 text-primary text-truncate" }, {
                      default: _withCtx(() => [
                        _createTextVNode(" 文件记录列表 — " + _toDisplayString(curDir.value === ROOT ? '目标目录根下直接转移的文件' : (curDir.value || '请选择专辑')), 1)
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_v_card_text, {
                      class: "pa-1",
                      style: {"max-height":"420px","overflow-y":"auto","scrollbar-gutter":"stable"}
                    }, {
                      default: _withCtx(() => [
                        (loading.value)
                          ? (_openBlock(), _createElementBlock("div", _hoisted_12, [
                              _createVNode(_component_v_progress_linear, { indeterminate: "" })
                            ]))
                          : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(pagedFiles.value, (f) => {
                                return (_openBlock(), _createElementBlock("div", {
                                  key: f.rel,
                                  class: "d-flex align-center ga-1 py-1 px-2"
                                }, [
                                  _createVNode(_component_v_icon, {
                                    size: "small",
                                    color: "grey",
                                    class: "flex-shrink-0"
                                  }, {
                                    default: _withCtx(() => [...(_cache[22] || (_cache[22] = [
                                      _createTextVNode("mdi-music-note-plus", -1)
                                    ]))]),
                                    _: 1
                                  }),
                                  _createElementVNode("span", {
                                    class: "text-body-2 text-truncate",
                                    style: {"flex":"1 1 auto","min-width":"0"},
                                    title: f.rel
                                  }, _toDisplayString(f.rel), 9, _hoisted_13),
                                  (f.time)
                                    ? (_openBlock(), _createElementBlock("span", _hoisted_14, _toDisplayString(f.time), 1))
                                    : _createCommentVNode("", true),
                                  (f.mode)
                                    ? (_openBlock(), _createBlock(_component_v_chip, {
                                        key: 1,
                                        size: "x-small",
                                        color: "primary",
                                        variant: "tonal",
                                        class: "flex-shrink-0"
                                      }, {
                                        default: _withCtx(() => [
                                          _createTextVNode(_toDisplayString(f.mode), 1)
                                        ]),
                                        _: 2
                                      }, 1024))
                                    : _createCommentVNode("", true)
                                ]))
                              }), 128)),
                              (pagedFiles.value.length === 0)
                                ? (_openBlock(), _createElementBlock("div", _hoisted_15, " 当前目录暂无已转移文件记录。 "))
                                : _createCommentVNode("", true)
                            ], 64))
                      ]),
                      _: 1
                    }),
                    (pageSize.value !== 'all' && fileTotalPages.value > 1)
                      ? (_openBlock(), _createBlock(_component_v_card_actions, {
                          key: 0,
                          class: "pt-0"
                        }, {
                          default: _withCtx(() => [
                            _createVNode(_component_v_pagination, {
                              modelValue: filePage.value,
                              "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((filePage).value = $event)),
                              length: fileTotalPages.value,
                              density: "compact",
                              "total-visible": "5"
                            }, null, 8, ["modelValue", "length"])
                          ]),
                          _: 1
                        }))
                      : _createCommentVNode("", true)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        })),
    _createVNode(_component_v_dialog, {
      modelValue: confirm.value.show,
      "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((confirm.value.show) = $event)),
      "max-width": "520"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_v_card, null, {
          default: _withCtx(() => [
            _createVNode(_component_v_card_title, { class: "text-subtitle-1" }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(confirm.value.title), 1)
              ]),
              _: 1
            }),
            _createVNode(_component_v_card_text, null, {
              default: _withCtx(() => [
                _createElementVNode("p", _hoisted_16, _toDisplayString(confirm.value.text), 1),
                _createVNode(_component_v_list, { density: "compact" }, {
                  default: _withCtx(() => [
                    (_openBlock(), _createElementBlock(_Fragment, null, _renderList(confirmModes, (mode) => {
                      return _createVNode(_component_v_list_item, {
                        key: mode.value,
                        active: confirm.value.mode === mode.value,
                        onClick: $event => (setConfirmMode(mode.value))
                      }, {
                        prepend: _withCtx(() => [
                          _createVNode(_component_v_icon, {
                            color: confirm.value.mode === mode.value ? mode.color : ''
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(confirm.value.mode === mode.value ? 'mdi-radiobox-marked' : 'mdi-radiobox-blank'), 1)
                            ]),
                            _: 2
                          }, 1032, ["color"])
                        ]),
                        default: _withCtx(() => [
                          _createVNode(_component_v_list_item_title, null, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(mode.label), 1)
                            ]),
                            _: 2
                          }, 1024),
                          _createVNode(_component_v_list_item_subtitle, null, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(mode.desc), 1)
                            ]),
                            _: 2
                          }, 1024)
                        ]),
                        _: 2
                      }, 1032, ["active", "onClick"])
                    }), 64))
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_v_card_actions, null, {
              default: _withCtx(() => [
                _createVNode(_component_v_spacer),
                _createVNode(_component_v_btn, {
                  color: "grey",
                  variant: "text",
                  onClick: _cache[9] || (_cache[9] = $event => (confirm.value.show = false))
                }, {
                  default: _withCtx(() => [...(_cache[23] || (_cache[23] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_v_btn, {
                  color: "error",
                  variant: "flat",
                  onClick: runConfirm
                }, {
                  default: _withCtx(() => [...(_cache[24] || (_cache[24] = [
                    _createTextVNode("确认执行", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"])
  ]))
}
}

};

export { _sfc_main as default };
