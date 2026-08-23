import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,openBlock:_openBlock,createBlock:_createBlock} = await importShared('vue');


const {ref,inject} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: {
  initialConfig: { type: Object, default: () => ({}) },
  api: { type: Object, default: () => ({}) },
  nativeSubscribe: { type: Function, default: null },
},
  emits: ['save', 'close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
inject('moviepilot:toast', null);

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
});

const modeItems = [
  { title: '兼容模式', value: 'compatibility' },
  { title: '性能模式', value: 'fast' },
];
const transferItems = [
  { title: '硬链接', value: 'link' },
  { title: '复制', value: 'copy' },
  { title: '移动', value: 'move' },
];
const existsItems = [
  { title: '跳过', value: 'skip' },
  { title: '覆盖', value: 'overwrite' },
];
const deleteItems = [
  { title: '同时删除目标文件并从记录移除', value: 'both' },
  { title: '仅删除目标目录真实文件（保留记录）', value: 'target' },
  { title: '仅从记录中移除（保留目标文件）', value: 'record' },
];

function saveConfig() {
  emit('save', config.value);
}

return (_ctx, _cache) => {
  const _component_v_switch = _resolveComponent("v-switch");
  const _component_v_col = _resolveComponent("v-col");
  const _component_v_select = _resolveComponent("v-select");
  const _component_v_text_field = _resolveComponent("v-text-field");
  const _component_v_textarea = _resolveComponent("v-textarea");
  const _component_v_alert = _resolveComponent("v-alert");
  const _component_v_row = _resolveComponent("v-row");
  const _component_v_btn = _resolveComponent("v-btn");
  const _component_v_form = _resolveComponent("v-form");

  return (_openBlock(), _createBlock(_component_v_form, {
    class: "pa-6",
    style: {"overflow-x":"hidden","overflow-y":"auto","max-width":"100%","min-width":"0","max-height":"calc(100dvh - 170px)","scrollbar-gutter":"stable"}
  }, {
    default: _withCtx(() => [
      _createVNode(_component_v_row, null, {
        default: _withCtx(() => [
          _createVNode(_component_v_col, {
            cols: "12",
            md: "4"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_switch, {
                modelValue: config.value.enabled,
                "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((config.value.enabled) = $event)),
                label: "启用插件",
                color: "primary"
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode(_component_v_col, {
            cols: "12",
            md: "4"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_switch, {
                modelValue: config.value.notify,
                "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((config.value.notify) = $event)),
                label: "发送通知",
                color: "primary"
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode(_component_v_col, {
            cols: "12",
            md: "4"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_switch, {
                modelValue: config.value.onlyonce,
                "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((config.value.onlyonce) = $event)),
                label: "立即运行一次",
                color: "primary"
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode(_component_v_col, {
            cols: "12",
            md: "4"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_select, {
                modelValue: config.value.mode,
                "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((config.value.mode) = $event)),
                items: modeItems,
                label: "监控模式",
                density: "compact",
                "hide-details": ""
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode(_component_v_col, {
            cols: "12",
            md: "4"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_select, {
                modelValue: config.value.transfer_type,
                "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((config.value.transfer_type) = $event)),
                items: transferItems,
                label: "转移方式",
                density: "compact",
                "hide-details": ""
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode(_component_v_col, {
            cols: "12",
            md: "4"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_text_field, {
                modelValue: config.value.size,
                "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((config.value.size) = $event)),
                label: "最小文件大小（KB）",
                density: "compact",
                "hide-details": ""
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode(_component_v_col, {
            cols: "12",
            md: "4"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_text_field, {
                modelValue: config.value.flush_interval,
                "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((config.value.flush_interval) = $event)),
                label: "通知汇总刷新间隔（秒）",
                density: "compact",
                "hide-details": "",
                placeholder: "默认3，实时事件间隔内聚合为一条通知"
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode(_component_v_col, {
            cols: "12",
            md: "4"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_text_field, {
                modelValue: config.value.concurrency,
                "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((config.value.concurrency) = $event)),
                label: "并发转移数",
                density: "compact",
                "hide-details": "",
                placeholder: "默认4，全量同步并行转移数量"
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode(_component_v_col, {
            cols: "12",
            md: "4"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_select, {
                modelValue: config.value.exists_mode,
                "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((config.value.exists_mode) = $event)),
                items: existsItems,
                label: "目标已存在处理",
                density: "compact",
                "hide-details": ""
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode(_component_v_col, {
            cols: "12",
            md: "6"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_select, {
                modelValue: config.value.delete_mode,
                "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((config.value.delete_mode) = $event)),
                items: deleteItems,
                label: "详情页删除模式",
                density: "compact",
                "hide-details": ""
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode(_component_v_col, { cols: "12" }, {
            default: _withCtx(() => [
              _createVNode(_component_v_text_field, {
                modelValue: config.value.cron,
                "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((config.value.cron) = $event)),
                label: "定时全量同步周期",
                density: "compact",
                "hide-details": "",
                placeholder: "5位cron表达式，留空关闭"
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode(_component_v_col, { cols: "12" }, {
            default: _withCtx(() => [
              _createVNode(_component_v_textarea, {
                modelValue: config.value.monitor_dirs,
                "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((config.value.monitor_dirs) = $event)),
                label: "监控目录",
                rows: "5",
                placeholder: "每一行一个目录，支持以下几种配置方式：\n监控目录\n监控目录:转移目的目录"
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode(_component_v_col, { cols: "12" }, {
            default: _withCtx(() => [
              _createVNode(_component_v_textarea, {
                modelValue: config.value.exclude_keywords,
                "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((config.value.exclude_keywords) = $event)),
                label: "排除关键词",
                rows: "2",
                placeholder: "每一行一个关键词"
              }, null, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode(_component_v_col, { cols: "12" }, {
            default: _withCtx(() => [
              _createVNode(_component_v_alert, {
                type: "info",
                variant: "tonal"
              }, {
                default: _withCtx(() => [...(_cache[13] || (_cache[13] = [
                  _createTextVNode(" 转移方式：硬链接不占用额外空间、复制会生成副本、移动会删除源文件。 最小文件大小：小于最小文件大小的文件将直接复制，其余按转移方式处理。 目标已存在处理：跳过则不重复转移，覆盖会先删除已存在目标再转移。 通知为批量汇总：全量同步结束后发送一次，实时模式下按“通知汇总刷新间隔”聚合发送。 ", -1)
                ]))]),
                _: 1
              })
            ]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode(_component_v_row, { class: "mt-2" }, {
        default: _withCtx(() => [
          _createVNode(_component_v_col, {
            cols: "12",
            class: "d-flex justify-end"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_btn, {
                color: "primary",
                variant: "flat",
                onClick: saveConfig
              }, {
                default: _withCtx(() => [...(_cache[14] || (_cache[14] = [
                  _createTextVNode("保存", -1)
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
  }))
}
}

};

export { _sfc_main as default };
