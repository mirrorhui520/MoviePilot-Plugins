# -*- coding: utf-8 -*-
"""
实时同步插件：监控目录文件变化，按配置的转移方式（复制/移动/硬链接）同步到目的目录。
参考项目：jxxghp/MoviePilot-Plugins 中的 linkmonitor 插件。
"""
import datetime
import re
import shutil
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from watchfiles import Change, watch

from app import schemas
from app.core.config import settings
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType
from app.utils.system import SystemUtils

# 转移方式中文描述
TRANSFER_NAMES: Dict[str, str] = {
    "copy": "复制",
    "move": "移动",
    "link": "硬链接",
}

# 目标文件已存在且选择跳过时的返回标记
EXISTS_SKIPPED = "__EXISTS_SKIPPED__"

# 转移记录在插件数据中的键名（独立于日志，使用插件自身的数据存储）
RECORD_KEY = "transferred"

# 删除操作可选模式
DELETE_MODES: Dict[str, str] = {
    "both": "同时删除目标文件并从记录移除",
    "target": "仅删除目标目录真实文件（保留记录）",
    "record": "仅从记录中移除（保留目标文件）",
}

# 记录键的分隔符（避免路径包含该字符）
RECORD_SEP = "\x00"

# 详情页 UI 状态存储键（当前选中的监控目录 / 专辑目录）
UI_STATE_KEY = "linksync_ui_state"

# 根目录下直接转移文件的特殊标识（无专辑目录包裹）
ROOT_MARK = "_ROOT_"


def _has_suffix_in(file_path: Path, extensions: List[str]) -> bool:
    """
    判断文件后缀是否命中给定扩展名列表。
    """
    if not file_path.suffix:
        return False
    return file_path.suffix.casefold() in {ext.casefold() for ext in extensions}


def _is_download_tmp_file(file_path: Path) -> bool:
    """
    判断文件是否为下载器尚未完成的临时文件。
    """
    return _has_suffix_in(file_path, settings.DOWNLOAD_TMPEXT)


class WatchfilesEvent:
    """
    watchfiles 目录监控事件。
    """

    def __init__(self, src_path: str, is_directory: bool):
        """
        初始化目录监控事件。
        :param src_path: 事件路径
        :param is_directory: 是否为目录
        """
        self.src_path = src_path
        self.dest_path = src_path
        self.is_directory = is_directory


class WatchfilesObserver:
    """
    基于 watchfiles 的目录监控适配器。
    """

    def __init__(self, timeout: int = 10, force_polling: Optional[bool] = None):
        """
        初始化目录监控适配器。
        :param timeout: 兼容模式轮询间隔秒数
        :param force_polling: 是否强制轮询，None 表示自动选择平台原生模式
        """
        self._force_polling = force_polling
        self._poll_delay_ms = max(int(timeout * 1000), 300)
        self._stop_event = threading.Event()
        self._thread = None
        self._handler = None
        self._path = None
        self._recursive = True

    def schedule(self, handler: Any, path: str, recursive: bool = True):
        """
        设置监控处理器和路径。
        :param handler: 事件处理器
        :param path: 监控路径
        :param recursive: 是否递归监控
        """
        self._handler = handler
        self._path = path
        self._recursive = recursive

    def start(self):
        """
        启动目录监控线程。
        """
        if not self._handler or not self._path:
            raise ValueError("目录监控处理器或路径未设置")
        if not Path(self._path).exists():
            raise FileNotFoundError(f"监控目录不存在：{self._path}")
        if not Path(self._path).is_dir():
            raise NotADirectoryError(f"监控路径不是目录：{self._path}")
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """
        停止目录监控线程。
        """
        self._stop_event.set()

    def join(self, timeout: Optional[float] = None):
        """
        等待目录监控线程退出。
        :param timeout: 最大等待秒数
        """
        if self._thread:
            self._thread.join(timeout=timeout)

    def _run(self):
        """
        运行 watchfiles 监控循环，快速模式异常时回退到轮询。
        """
        try:
            self._run_watch(force_polling=self._force_polling)
        except Exception as err:
            if self._stop_event.is_set():
                return
            if self._force_polling is True:
                logger.error(f"{self._path} 目录监控发生错误：{err}")
                logger.debug(traceback.format_exc())
                return
            logger.warn(f"{self._path} 快速模式监控失败，自动切换到兼容模式：{err}")
            try:
                self._run_watch(force_polling=True)
            except Exception as fallback_err:
                if not self._stop_event.is_set():
                    logger.error(f"{self._path} 兼容模式监控失败：{fallback_err}")
                    logger.debug(traceback.format_exc())

    def _run_watch(self, force_polling: Optional[bool]):
        """
        执行 watchfiles 监控。
        :param force_polling: 是否强制轮询
        """
        for changes in watch(
                self._path,
                stop_event=self._stop_event,
                rust_timeout=1000,
                yield_on_timeout=True,
                force_polling=force_polling,
                poll_delay_ms=self._poll_delay_ms,
                recursive=self._recursive,
                ignore_permission_denied=True):
            if self._stop_event.is_set():
                break
            if not changes:
                continue
            for change_type, event_path in sorted(changes, key=lambda item: item[1]):
                self._handler.dispatch(change_type=change_type, event_path=event_path)


class FileMonitorHandler:
    """
    目录监控响应类。
    """

    def __init__(self, monpath: str, sync: Any):
        """
        初始化目录监控响应类。
        :param monpath: 监控目录
        :param sync: 插件实例
        """
        self._watch_path = monpath
        self.sync = sync

    def dispatch(self, change_type: Change, event_path: str):
        """
        分发 watchfiles 事件。
        :param change_type: 事件类型
        :param event_path: 事件路径
        """
        if change_type not in {Change.added, Change.modified}:
            return
        path = Path(event_path)
        if not path.exists():
            return
        is_directory = path.is_dir()
        if not is_directory and _is_download_tmp_file(path):
            return
        event = WatchfilesEvent(src_path=event_path, is_directory=is_directory)
        text = "修改" if change_type == Change.modified else "创建"
        self.sync.event_handler(event=event, text=text,
                                mon_path=self._watch_path, event_path=event_path)


class LinkSync(_PluginBase):
    # 插件名称
    plugin_name = "实时同步"
    # 插件描述
    plugin_desc = "监控目录文件变化，按原文件名复制、移动或硬链接到目的目录。"
    # 插件图标
    plugin_icon = "sync_file.png"
    # 插件版本
    plugin_version = "1.4"
    # 插件作者
    plugin_author = "mirrorhui520"
    # 作者主页
    author_url = "https://github.com/mirrorhui520"
    # 插件配置项ID前缀
    plugin_config_prefix = "linksync_"
    # 加载顺序
    plugin_order = 4
    # 可使用的用户级别
    user_level = 1

    # 私有属性
    _scheduler = None
    _observer = []
    _enabled = False
    _notify = False
    _onlyonce = False
    _cron = None
    _size = 0
    # 监控目录
    _monitor_dirs = ""
    _exclude_keywords = ""
    # 转移方式 copy/move/link
    _transfer_type = "link"
    # 通知防抖汇总间隔（秒），实时事件在该间隔内聚合为一条通知
    _flush_interval = 3
    # 全量同步并发转移数
    _concurrency = 4
    # 目标文件已存在时的处理方式 skip/overwrite
    _exists_mode = "skip"
    # 详情页删除操作的默认模式 both/target/record（JSON 页面无响应式 select，故在设置中选择、页面构建时读取）
    _delete_mode = "both"

    # 模式 compatibility/fast
    _mode = "fast"
    # 存储源目录与目的目录关系
    _dirconf: Dict[str, Optional[Path]] = {}
    # 退出事件
    _event = threading.Event()
    # 转移结果统计（用于通知汇总）
    _notify_success = 0
    _notify_skip = 0
    _notify_fail = 0
    _notify_lock = threading.Lock()
    _flush_timer = None
    # 是否处于全量同步中（全量同步期间不触发增量防抖通知）
    _full_sync = False
    # 并发转移线程池
    _executor: Optional[ThreadPoolExecutor] = None

    def init_plugin(self, config: dict = None):
        # 清空配置
        self._dirconf = {}

        # 读取配置
        if config:
            self._enabled = config.get("enabled")
            self._notify = config.get("notify")
            self._onlyonce = config.get("onlyonce")
            self._mode = config.get("mode")
            self._monitor_dirs = config.get("monitor_dirs") or ""
            self._exclude_keywords = config.get("exclude_keywords") or ""
            self._transfer_type = config.get("transfer_type") or "link"
            self._cron = config.get("cron")
            self._size = config.get("size") or 0
            self._flush_interval = abs(int(config.get("flush_interval") or 3))
            self._concurrency = max(1, int(config.get("concurrency") or 4))
            self._exists_mode = config.get("exists_mode") or "skip"
            self._delete_mode = config.get("delete_mode") or "both"

        # 停止现有任务
        self.stop_service()

        # 重置转移结果统计
        self.__reset_notify()

        if self._enabled or self._onlyonce:

            # 初始化并发转移线程池
            self._executor = ThreadPoolExecutor(max_workers=self._concurrency,
                                                thread_name_prefix="linksync")

            # 读取目录配置
            monitor_dirs = self._monitor_dirs.split("\n")
            if not monitor_dirs:
                return
            for mon_path in monitor_dirs:
                # 格式源目录:目的目录
                if not mon_path:
                    continue

                # 存储目的目录
                if SystemUtils.is_windows():
                    if mon_path.count(":") > 1:
                        paths = [mon_path.split(":")[0] + ":" + mon_path.split(":")[1],
                                 mon_path.split(":")[2] + ":" + mon_path.split(":")[3]]
                    else:
                        paths = [mon_path]
                else:
                    paths = mon_path.split(":")

                # 目的目录
                if len(paths) > 1:
                    mon_path = paths[0]
                    target_path = Path(paths[1])
                    self._dirconf[mon_path] = target_path
                else:
                    logger.warn(f"{mon_path} 未配置目的目录，将不会进行同步")
                    self.systemmessage.put(f"{mon_path} 未配置目的目录，将不会进行同步！", title="实时同步")
                    continue

                # 启用目录监控
                if self._enabled:
                    # 检查媒体库目录是不是下载目录的子目录
                    try:
                        if target_path and target_path.is_relative_to(Path(mon_path)):
                            logger.warn(f"{target_path} 是监控目录 {mon_path} 的子目录，无法监控")
                            self.systemmessage.put(f"{target_path} 是下载目录 {mon_path} 的子目录，无法监控", title="实时同步")
                            continue
                    except Exception as e:
                        logger.debug(str(e))
                        pass

                    try:
                        if self._mode == "compatibility":
                            # 兼容模式，目录同步性能降低且NAS不能休眠，但可以兼容挂载的远程共享目录如SMB
                            observer = WatchfilesObserver(timeout=10, force_polling=True)
                        else:
                            # 内部处理系统操作类型选择最优解
                            observer = WatchfilesObserver(timeout=10, force_polling=None)
                        self._observer.append(observer)
                        observer.schedule(FileMonitorHandler(mon_path, self), path=mon_path, recursive=True)
                        observer.daemon = True
                        observer.start()
                        logger.info(f"{mon_path} 的目录监控服务启动")
                    except Exception as e:
                        err_msg = str(e)
                        if "inotify" in err_msg and "reached" in err_msg:
                            logger.warn(
                                f"目录监控服务启动出现异常：{err_msg}，请在宿主机上（不是docker容器内）执行以下命令并重启："
                                + """
                                     echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf
                                     echo fs.inotify.max_user_instances=524288 | sudo tee -a /etc/sysctl.conf
                                     sudo sysctl -p
                                     """)
                        else:
                            logger.error(f"{mon_path} 启动目录监控失败：{err_msg}")
                        self.systemmessage.put(f"{mon_path} 启动目录监控失败：{err_msg}", title="实时同步")

            # 运行一次定时服务
            if self._onlyonce:
                # 定时服务管理器
                self._scheduler = BackgroundScheduler(timezone=settings.TZ)
                logger.info("目录监控服务启动，立即运行一次")
                self._scheduler.add_job(func=self.sync_all, trigger='date',
                                        run_date=datetime.datetime.now(
                                            tz=pytz.timezone(settings.TZ)) + datetime.timedelta(seconds=3)
                                        )
                # 关闭一次性开关
                self._onlyonce = False
                # 保存配置
                self.__update_config()

                # 启动定时服务
                if self._scheduler.get_jobs():
                    self._scheduler.print_jobs()
                    self._scheduler.start()

    def __update_config(self):
        """
        更新配置
        """
        self.update_config({
            "enabled": self._enabled,
            "notify": self._notify,
            "onlyonce": self._onlyonce,
            "mode": self._mode,
            "transfer_type": self._transfer_type,
            "monitor_dirs": self._monitor_dirs,
            "exclude_keywords": self._exclude_keywords,
            "cron": self._cron,
            "size": self._size,
            "flush_interval": self._flush_interval,
            "concurrency": self._concurrency,
            "exists_mode": self._exists_mode,
            "delete_mode": self._delete_mode
        })

    @eventmanager.register(EventType.PluginAction)
    def remote_sync(self, event: Event):
        """
        远程全量同步
        """
        if event:
            event_data = event.event_data
            if not event_data or event_data.get("action") != "realtime_sync":
                return
            self.post_message(channel=event.event_data.get("channel"),
                              title="开始实时同步 ...",
                              userid=event.event_data.get("user"))
        self.sync_all()
        if event:
            self.post_message(channel=event.event_data.get("channel"),
                              title="实时同步完成！", userid=event.event_data.get("user"))

    def sync_all(self):
        """
        立即运行一次，全量同步目录中所有文件
        """
        logger.info("开始全量实时同步 ...")
        # 重置统计与待发送通知
        self.__cancel_flush()
        self.__reset_notify()
        # 标记全量同步，期间增量防抖通知不触发
        self._full_sync = True
        # 收集所有待处理文件
        tasks = []
        for mon_path in self._dirconf.keys():
            # 遍历目录下所有文件
            for file_path in SystemUtils.list_files(Path(mon_path), ['.*']):
                tasks.append((str(file_path), mon_path))
        try:
            # 并发转移
            if self._executor and tasks:
                try:
                    list(self._executor.map(lambda item: self.__handle_file(item[0], item[1]), tasks))
                except Exception as e:
                    logger.error(f"全量实时同步发生错误：{e}")
            else:
                for file_path, mon_path in tasks:
                    self.__handle_file(file_path, mon_path)
        finally:
            self._full_sync = False
            self.__cancel_flush()
        # 所有文件处理完毕，先输出完成日志，再汇总发送一次通知
        logger.info("全量实时同步完成！")
        self.__flush_notify()

    def event_handler(self, event, mon_path: str, text: str, event_path: str):
        """
        处理文件变化
        :param event: 事件
        :param mon_path: 监控目录
        :param text: 事件描述
        :param event_path: 事件文件路径
        """
        if not event.is_directory:
            # 文件发生变化
            logger.debug("文件%s：%s" % (text, event_path))
            if self._executor:
                self._executor.submit(self.__handle_file, event_path, mon_path)
            else:
                self.__handle_file(event_path, mon_path)

    @staticmethod
    def _transfer_file(src_path: Path, mon_path: str,
                       target_path: Path, transfer_type: str = "link",
                       exists_mode: str = "skip") -> Tuple[bool, str]:
        """
        对文件做纯同步处理，不做识别重命名，提供监控模块调用
        :param src_path: 源文件
        :param mon_path: 监控目录
        :param target_path: 目标目录
        :param transfer_type: 转移方式 copy/move/link
        :param exists_mode: 目标文件已存在时的处理方式 skip/overwrite
        """
        # 计算相对路径
        try:
            rel_path = src_path.relative_to(Path(mon_path))
        except ValueError:
            return False, "文件路径不在监控目录内"
        new_path = target_path / rel_path

        # 目标文件已存在
        if new_path.exists():
            if exists_mode == "overwrite":
                # 覆盖：先删除已存在的目标文件
                try:
                    new_path.unlink()
                except Exception as err:
                    return False, f"覆盖前删除已存在文件失败：{err}"
            else:
                return True, EXISTS_SKIPPED

        # 创建目标目录
        if not new_path.parent.exists():
            new_path.parent.mkdir(parents=True, exist_ok=True)
        # 转移
        if transfer_type == "copy":
            code, errmsg = SystemUtils.copy(src_path, new_path)
        elif transfer_type == "move":
            code, errmsg = SystemUtils.move(src_path, new_path)
        else:
            # 直接硬链接，避免 SystemUtils.link 的中间重命名损耗
            try:
                new_path.hardlink_to(src_path)
                code, errmsg = 0, ""
            except Exception as err:
                code, errmsg = -1, str(err)
        return True if code == 0 else False, errmsg

    def __handle_file(self, event_path: str, mon_path: str):
        """
        同步一个文件
        :param event_path: 事件文件路径
        :param mon_path: 监控目录
        """
        file_path = Path(event_path)
        try:
            if not file_path.exists():
                return
            if _is_download_tmp_file(file_path):
                return

            # 回收站及隐藏的文件不处理
            if event_path.find('/@Recycle/') != -1 \
                    or event_path.find('/#recycle/') != -1 \
                    or event_path.find('/.') != -1 \
                    or event_path.find('/@eaDir') != -1:
                logger.debug(f"{event_path} 是回收站或隐藏的文件")
                return

            # 命中过滤关键字不处理
            if self._exclude_keywords:
                for keyword in self._exclude_keywords.split("\n"):
                    if keyword and re.findall(keyword, event_path):
                        logger.info(f"{event_path} 命中过滤关键字 {keyword}，不处理")
                        return

            # 判断文件大小，小于最小文件大小的文件直接复制，其余按配置的转移方式处理
            if self._size and float(self._size) > 0 and file_path.stat().st_size < float(self._size) * 1024:
                logger.info(f"{event_path} 文件大小小于最小文件大小，复制...")
                _transfer_type = "copy"
            else:
                _transfer_type = self._transfer_type if self._transfer_type in TRANSFER_NAMES else "link"

            # 转移方式中文名
            transfer_name = TRANSFER_NAMES.get(_transfer_type, "硬链接")

            # 查询转移目的目录
            target: Path = self._dirconf.get(mon_path)
            if not target:
                logger.warn(f"{mon_path} 未配置目的目录，将不会进行同步")
                return

            # 优先跳过已有转移记录的文件：记录命中即跳过，不再走目标目录存在性查询
            try:
                rel = str(file_path.relative_to(Path(mon_path)))
            except ValueError:
                rel = ""
            if rel and self.__record_key(mon_path, rel) in self.__get_records():
                with self._notify_lock:
                    self._notify_skip += 1
                logger.info(f"{file_path.name} 已在转移记录中，跳过")
                return

            # 开始转移
            state, errmsg = self._transfer_file(src_path=file_path, mon_path=mon_path,
                                                target_path=target, transfer_type=_transfer_type,
                                                exists_mode=self._exists_mode)

            # 成功转移（非跳过）则写入转移记录，供 UI 管理与“记录命中”跳过使用
            if state and errmsg != EXISTS_SKIPPED:
                self.__add_record(mon_path=mon_path, src_path=file_path,
                                  target=target, transfer_name=transfer_name)

            # 统计结果，汇总到通知中
            with self._notify_lock:
                if errmsg == EXISTS_SKIPPED:
                    self._notify_skip += 1
                    logger.info(f"{file_path.name} 文件已存在，跳过成功")
                elif state:
                    self._notify_success += 1
                    logger.info(f"{file_path.name} {transfer_name}成功")
                else:
                    self._notify_fail += 1
                    logger.warn(f"{file_path.name} {transfer_name}失败：{errmsg}")

            # 增量监控时防抖汇总通知；全量同步期间不触发，由全量结束统一汇总
            if self._notify and not self._full_sync:
                self.__schedule_notify()

        except Exception as e:
            with self._notify_lock:
                self._notify_fail += 1
            if self._notify and not self._full_sync:
                self.__schedule_notify()
            logger.error("目录监控发生错误：%s - %s" % (str(e), traceback.format_exc()))

    # ==================== 转移记录相关 ====================

    def __record_key(self, mon_path: str, rel: str) -> str:
        """生成记录唯一键"""
        return f"{mon_path}{RECORD_SEP}{rel}"

    def __get_records(self) -> Dict[str, dict]:
        """读取全部转移记录（字典：记录键 -> 记录内容）"""
        records = self.get_data(RECORD_KEY)
        return dict(records or {})

    def __save_records(self, records: Dict[str, dict]):
        """写回全部转移记录"""
        self.save_data(RECORD_KEY, records)

    def __add_record(self, mon_path: str, src_path: Path, target: Path,
                     transfer_name: str):
        """
        新增/更新一条转移记录
        :param mon_path: 监控目录
        :param src_path: 源文件
        :param target: 目的目录根
        :param transfer_name: 转移方式中文名
        """
        try:
            rel = str(src_path.relative_to(Path(mon_path)))
        except ValueError:
            return
        # 转移记录同步锁
        lock = getattr(self, "_record_lock", None)
        if lock is None:
            lock = self._record_lock = threading.Lock()
        with lock:
            records = self.__get_records()
            records[self.__record_key(mon_path, rel)] = {
                "mon_path": mon_path,
                "rel": rel,
                "src": str(src_path),
                "target": str(target / rel),
                "mode": transfer_name,
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            self.__save_records(records)

    def __remove_record(self, mon_path: str, rel: str) -> bool:
        """移除一条转移记录，返回是否存在过"""
        lock = getattr(self, "_record_lock", None)
        if lock is None:
            lock = self._record_lock = threading.Lock()
        with lock:
            records = self.__get_records()
            key = self.__record_key(mon_path, rel)
            if key in records:
                del records[key]
                self.__save_records(records)
                return True
        return False

    def __target_root(self, mon_path: str) -> Optional[Path]:
        """
        获取某监控目录对应的目的目录根。
        插件启用时优先使用内存配置；未启用时从记录中反推。
        """
        tgt = self._dirconf.get(mon_path)
        if tgt:
            return tgt
        for rec in self.__get_records().values():
            if rec.get("mon_path") == mon_path and rec.get("rel") and rec.get("target"):
                root = Path(rec["target"])
                for _ in Path(rec["rel"]).parts:
                    root = root.parent
                return root
        return None

    def __remove_on_disk(self, path: Path) -> Tuple[bool, str]:
        """删除磁盘上的文件或目录"""
        try:
            if not path.exists():
                return True, "目标不存在"
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink()
            return True, ""
        except Exception as e:
            return False, str(e)

    def __get_ui(self) -> dict:
        """读取详情页当前选中状态（mon=监控目录 / dir=专辑目录或根标记）"""
        return dict(self.get_data(UI_STATE_KEY) or {})

    def __save_ui(self, ui: dict):
        """写回详情页当前选中状态"""
        self.save_data(UI_STATE_KEY, ui)

    def __reset_notify(self):
        """
        重置转移结果统计
        """
        with self._notify_lock:
            self._notify_success = 0
            self._notify_skip = 0
            self._notify_fail = 0

    def __cancel_flush(self):
        """
        取消尚未触发的防抖通知定时器
        """
        timer = self._flush_timer
        self._flush_timer = None
        if timer:
            try:
                timer.cancel()
            except Exception:
                pass

    def __schedule_notify(self):
        """
        实时模式下防抖：重置定时器，间隔内不再有新事件时发送一条汇总通知
        """
        self.__cancel_flush()
        if self._flush_interval <= 0:
            self.__flush_notify()
            return
        timer = threading.Timer(self._flush_interval, self.__flush_notify)
        timer.daemon = True
        self._flush_timer = timer
        timer.start()

    def __flush_notify(self):
        """
        汇总发送一条转移结果通知
        """
        self._flush_timer = None
        with self._notify_lock:
            success = self._notify_success
            skip = self._notify_skip
            fail = self._notify_fail
            self._notify_success = 0
            self._notify_skip = 0
            self._notify_fail = 0
        total = success + skip + fail
        if not self._notify or total == 0:
            return
        text = f"本批转移完成：成功 {success} 个"
        if skip:
            text += f"，跳过 {skip} 个"
        text += f"，失败 {fail} 个（共 {total} 个）"
        self.post_message(
            mtype=NotificationType.Manual,
            title="实时同步完成！",
            text=text
        )

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """
        定义远程控制命令
        :return: 命令关键字、事件、描述、附带数据
        """
        return [{
            "cmd": "/realtime_sync",
            "event": EventType.PluginAction,
            "desc": "实时同步",
            "category": "管理",
            "data": {
                "action": "realtime_sync"
            }
        }]

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/realtime_sync",
                "endpoint": self.sync,
                "methods": ["GET"],
                "summary": "实时同步",
                "description": "实时同步",
            },
            {
                "path": "/delete",
                "endpoint": self.delete_record,
                "methods": ["GET"],
                "summary": "删除转移项",
                "description": "按模式删除目标文件/记录",
            },
            {
                "path": "/clear",
                "endpoint": self.clear,
                "methods": ["GET"],
                "summary": "清空目标目录",
                "description": "清空指定监控（或不指定则全部）目的目录内容",
            },
            {
                "path": "/refresh",
                "endpoint": self.refresh_page,
                "methods": ["GET"],
                "summary": "刷新列表",
                "description": "仅用于详情页触发页面重绘以重新加载转移记录列表",
            },
            {
                "path": "/select_dir",
                "endpoint": self.select_dir,
                "methods": ["GET"],
                "summary": "切换查看目录",
                "description": "记录当前选中的监控目录与专辑目录，触发详情页重绘按目录过滤文件记录列表",
            },
        ]

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务
        [{
            "id": "服务ID",
            "name": "服务名称",
            "trigger": "触发器：cron/interval/date/CronTrigger.from_crontab()",
            "func": self.xxx,
            "kwargs": {} # 定时器参数
        }]
        """
        if self._enabled and self._cron:
            return [{
                "id": "LinkSync",
                "name": "全量同步定时服务",
                "trigger": CronTrigger.from_crontab(self._cron),
                "func": self.sync_all,
                "kwargs": {}
            }]

    def sync(self, apikey: str) -> schemas.Response:
        """
        API调用目录同步
        """
        if apikey != settings.API_TOKEN:
            return schemas.Response(success=False, message="API密钥错误")
        self.sync_all()
        return schemas.Response(success=True)

    def delete_record(self, apikey: str, mon_path: str = "", rel: str = "",
                      mode: str = "both", is_dir: int = 0) -> schemas.Response:
        """
        删除转移项（文件或目录）
        :param apikey: API 密钥
        :param mon_path: 监控目录
        :param rel: 相对路径（文件或目录）
        :param mode: both/target/record
        :param is_dir: 是否按目录删除
        """
        if apikey != settings.API_TOKEN:
            return schemas.Response(success=False, message="API密钥错误")
        if not mon_path or not rel:
            return schemas.Response(success=False, message="参数不完整")
        mode = mode if mode in DELETE_MODES else "both"
        records = self.__get_records()
        deleted_files = 0
        try:
            if not is_dir:
                # 按单文件删除
                rec = records.get(self.__record_key(mon_path, rel))
                if rec and mode in ("both", "target"):
                    ok, _ = self.__remove_on_disk(Path(rec["target"]))
                    deleted_files = 1 if ok else 0
                if mode in ("both", "record"):
                    self.__remove_record(mon_path, rel)
            else:
                # 按目录删除：删除该目录下全部目标产物与记录
                prefix = rel.rstrip("/") + "/"
                root = self.__target_root(mon_path)
                folder_tgt = (root / Path(rel)) if root else None
                if mode in ("both", "target"):
                    if folder_tgt and not folder_tgt.is_relative_to(root.resolve()):
                        return schemas.Response(success=False, message="非法路径")
                    if folder_tgt:
                        deleted_files = int(folder_tgt.exists())
                        _ok, _ = self.__remove_on_disk(folder_tgt)
                if mode in ("both", "record"):
                    matched = [k for k, v in records.items()
                               if v.get("mon_path") == mon_path
                               and v.get("rel", "").startswith(prefix)]
                    for k in matched:
                        del records[k]
                    self.__save_records(records)
                    # 记录变化可能影响已删除文件统计
            return schemas.Response(success=True,
                                    message="处理完成：目标文件 %s 个" % deleted_files)
        except Exception as e:
            logger.error("删除转移项失败：%s - %s" % (str(e), traceback.format_exc()))
            return schemas.Response(success=False, message=f"删除失败：{e}")

    def clear(self, apikey: str, mon_path: str = "",
              mode: str = "both") -> schemas.Response:
        """
        清空目的目录下所有文件与记录（不指定 mon_path 则清空全部）
        :param apikey: API 密钥
        :param mon_path: 监控目录，为空表示全部
        :param mode: both/target/record
        """
        if apikey != settings.API_TOKEN:
            return schemas.Response(success=False, message="API密钥错误")
        mode = mode if mode in DELETE_MODES else "both"
        records = self.__get_records()
        # 确定要处理的监控目录集合
        mons = set(self._dirconf.keys())
        if mon_path:
            mons = {mon_path}
        mons.update(r.get("mon_path") for r in records.values() if r.get("mon_path"))
        deleted_dir, deleted_file = 0, 0
        try:
            for m in mons:
                root = self.__target_root(m)
                if root and mode in ("both", "target") and root.exists():
                    for child in root.iterdir():
                        try:
                            if child.is_dir():
                                shutil.rmtree(child, ignore_errors=True)
                                deleted_dir += 1
                            else:
                                child.unlink()
                                deleted_file += 1
                        except Exception:
                            pass
                if mode in ("both", "record"):
                    records = {k: v for k, v in records.items()
                               if v.get("mon_path") != m}
            if mode in ("both", "record"):
                self.__save_records(records)
            return schemas.Response(success=True,
                                    message=f"清除完成：目录 {deleted_dir} 个，文件 {deleted_file} 个")
        except Exception as e:
            logger.error("清空目的目录失败：%s - %s" % (str(e), traceback.format_exc()))
            return schemas.Response(success=False, message=f"清除失败：{e}")

    def refresh_page(self, apikey: str) -> schemas.Response:
        """
        详情页“刷新列表”按钮：仅返回成功，点击后触发前端重新拉取 get_page 并重绘。
        """
        if apikey != settings.API_TOKEN:
            return schemas.Response(success=False, message="API密钥错误")
        return schemas.Response(success=True, message="已刷新")

    def select_dir(self, apikey: str, mon_path: str = "", rel: str = "") -> schemas.Response:
        """
        详情页切换查看的目录：记录当前选中的监控目录与专辑目录，
        触发前端重绘 get_page 以按所选专辑过滤文件记录列表。
        :param mon_path: 当前监控目录
        :param rel: 选中的专辑目录名，"_ROOT_" 表示查看目标目录根下文件
        """
        if apikey != settings.API_TOKEN:
            return schemas.Response(success=False, message="API密钥错误")
        ui = self.__get_ui()
        ui["mon"] = mon_path or ""
        ui["dir"] = rel or ""
        self.__save_ui(ui)
        return schemas.Response(success=True, message="已切换查看目录")

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'notify',
                                            'label': '发送通知',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'onlyonce',
                                            'label': '立即运行一次',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'mode',
                                            'label': '监控模式',
                                            'items': [
                                                {'title': '兼容模式', 'value': 'compatibility'},
                                                {'title': '性能模式', 'value': 'fast'}
                                            ]
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'transfer_type',
                                            'label': '转移方式',
                                            'items': [
                                                {'title': '硬链接', 'value': 'link'},
                                                {'title': '复制', 'value': 'copy'},
                                                {'title': '移动', 'value': 'move'}
                                            ]
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'size',
                                            'label': '最小文件大小（KB）',
                                            'placeholder': ''
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'flush_interval',
                                            'label': '通知汇总刷新间隔（秒）',
                                            'placeholder': '默认3，实时事件间隔内聚合为一条通知'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'concurrency',
                                            'label': '并发转移数',
                                            'placeholder': '默认4，全量同步并行转移数量'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'exists_mode',
                                            'label': '目标已存在处理',
                                            'items': [
                                                {'title': '跳过', 'value': 'skip'},
                                                {'title': '覆盖', 'value': 'overwrite'}
                                            ]
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'delete_mode',
                                            'label': '详情页删除模式',
                                            'items': [
                                                {'title': '同时删除目标文件并从记录移除', 'value': 'both'},
                                                {'title': '仅删除目标目录真实文件（保留记录）', 'value': 'target'},
                                                {'title': '仅从记录中移除（保留目标文件）', 'value': 'record'}
                                            ]
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'cron',
                                            'label': '定时全量同步周期',
                                            'placeholder': '5位cron表达式，留空关闭'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'monitor_dirs',
                                            'label': '监控目录',
                                            'rows': 5,
                                            'placeholder': '每一行一个目录，支持以下几种配置方式：\n'
                                                           '监控目录\n'
                                                           '监控目录:转移目的目录\n'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'exclude_keywords',
                                            'label': '排除关键词',
                                            'rows': 2,
                                            'placeholder': '每一行一个关键词'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'text': '转移方式：硬链接不占用额外空间、复制会生成副本、移动会删除源文件。'
                                                   '最小文件大小：小于最小文件大小的文件将直接复制，其余按转移方式处理。'
                                                   '目标已存在处理：跳过则不重复转移，覆盖会先删除已存在目标再转移。'
                                                   '通知为批量汇总：全量同步结束后发送一次，实时模式下按“通知汇总刷新间隔”聚合发送。'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "notify": False,
            "onlyonce": False,
            "mode": "fast",
            "transfer_type": "link",
            "monitor_dirs": "",
            "exclude_keywords": "",
            "cron": "",
            "size": "",
            "flush_interval": 3,
            "concurrency": 4,
            "exists_mode": "skip",
            "delete_mode": "both"
        }

    # ==================== 详情页（get_page）相关 ====================

    # ---- 删除/清空三种模式的通用按钮构造 ----

    @staticmethod
    def _del_btn_params(mon_path: str, rel: str, is_dir: int, mode: str) -> dict:
        """文件/目录删除事件的 click 参数"""
        return {
            "apikey": settings.API_TOKEN,
            "mon_path": mon_path,
            "rel": rel,
            "mode": mode,
            "is_dir": 1 if is_dir else 0,
        }

    @staticmethod
    def _clear_btn_params(mon_path: str, mode: str) -> dict:
        """清空事件（mon_path 为空表示全部）的 click 参数"""
        return {
            "apikey": settings.API_TOKEN,
            "mon_path": mon_path,
            "mode": mode,
        }

    def _mode_group(self, api_path: str, params_func, prefix: str) -> dict:
        """
        构造“删除/清空”的三种模式按钮组：
        - both   删文件+清记录
        - target 仅删目标文件
        - record 仅清记录
        每个按钮各自以对应模式执行，点击后经页面 action 重新刷新列表。
        """
        specs = [
            ("both", "文件+记录", "error", "flat"),
            ("target", "仅删文件", "error", "tonal"),
            ("record", "仅清记录", "grey-darken-2", "tonal"),
        ]
        return {
            "component": "VBtnGroup",
            "props": {"density": "compact", "rounded": "sm"},
            "content": [
                {
                    "component": "VBtn",
                    "props": {"size": "x-small", "color": color, "variant": variant},
                    "text": label,
                    "events": {"click": {
                        "api": api_path,
                        "method": "get",
                        "params": params_func(mode),
                    }},
                }
                for mode, label, color, variant in specs
            ],
        }

    def _page_row(self, content: List[dict], indent: int) -> dict:
        """生成一行带缩进的记录行"""
        return {
            "component": "div",
            "props": {
                "class": "d-flex align-center ga-1",
                "style": f"padding-left: {indent * 16}px",
            },
            "content": content,
        }

    @staticmethod
    def _top_dirs(rels: Dict[str, dict]):
        """由转移记录聚合出目标目录下的一级专辑目录及根文件

        返回 (tops, roots)：
        - tops: 有序 dict，一级目录名 -> 该目录下全部文件相对路径列表
        - roots: 直接位于目标目录根下的文件相对路径列表
        仅依据已有转移记录重建，无需读取磁盘。
        """
        tops: Dict[str, list] = {}
        roots: list = []
        for rel in rels:
            parts = [p for p in rel.split("/") if p]
            if len(parts) == 1:
                roots.append(rel)
            else:
                tops.setdefault(parts[0], []).append(rel)
        return tops, roots

    def _album_row(self, name: str, rels: List[str], cur: str,
                   mon_path: str) -> dict:
        """一级专辑目录行：点目录名切换下方文件列表 + 三种删除模式按钮"""
        selected = (name == cur)
        return self._page_row([
            {"component": "VBtn",
             "props": {
                 "size": "x-small",
                 "variant": "tonal" if selected else "text",
                 "color": "primary" if selected else "default",
                 "prepend-icon": "mdi-check" if selected else "mdi-folder",
             },
             "text": f"{name}（{len(rels)}）",
             "events": {"click": {
                 "api": "plugin/LinkSync/select_dir",
                 "method": "get",
                 "params": {"apikey": settings.API_TOKEN,
                            "mon_path": mon_path, "rel": name},
             }}},
            {"component": "div", "props": {"class": "flex-grow-1"}},
            self._mode_group("plugin/LinkSync/delete",
                             lambda m: self._del_btn_params(mon_path, name, 1, m),
                             prefix="删专辑"),
        ], 0)

    def _root_switch(self, roots: List[str], cur: str, mon_path: str) -> dict:
        """目标目录根下直接转移文件的切换行（仅查看，不提供删除）"""
        selected = (cur == ROOT_MARK)
        return self._page_row([
            {"component": "VBtn",
             "props": {
                 "size": "x-small",
                 "variant": "tonal" if selected else "text",
                 "color": "primary" if selected else "default",
                 "prepend-icon": "mdi-check" if selected else "mdi-format-list-bulleted",
             },
             "text": f"根目录下文件（{len(roots)}）",
             "events": {"click": {
                 "api": "plugin/LinkSync/select_dir",
                 "method": "get",
                 "params": {"apikey": settings.API_TOKEN,
                            "mon_path": mon_path, "rel": ROOT_MARK},
             }}},
            {"component": "div", "props": {"class": "flex-grow-1"}},
        ], 0)

    def _file_line(self, rel: str, rec: dict, indent: int) -> dict:
        """纯展示一条文件转移记录（名称 + 时间 + 方式），不提供删除"""
        info = []
        if rec.get("time"):
            info.append({"component": "span",
                         "props": {"class": "text-caption text-grey"},
                         "text": f'{rec.get("time")}'})
        if rec.get("mode"):
            info.append({"component": "VChip",
                         "props": {"size": "x-small", "color": "primary", "variant": "tonal"},
                         "text": rec["mode"]})
        return self._page_row([
            {"component": "VIcon", "props": {"icon": "mdi-music-note-plus",
                                             "size": "small", "color": "grey"}},
            {"component": "div", "props": {"class": "flex-grow-1 text-body-2 ms-1 text-truncate"},
             "text": rel},
            *info,
        ], indent)

    def get_page(self) -> List[dict]:
        """
        拼装插件详情展示页（管理已转移记录，目录版块 + 文件记录列表分离）：
        - 顶部操作区：刷新列表 / 立即全量同步 / 一键清空全部目标目录（三种模式）
        - 监控目录切换（存在多个监控目录时）
        - 目录版块：按目标目录下的一级专辑目录列出转移记录，每个专辑提供三种删除模式，
          点击某个专辑目录即筛选下方文件记录列表（不会一次性展开全部，避免卡顿）
        - 文件记录列表：仅显示当前选中专辑下的已转移文件记录（名称/时间/方式，仅展示）
        - 记录存于插件自身数据，独立于日志；点击目录后自动重绘，也可手动“刷新列表”。
        """
        records = self.__get_records()

        tips_row = {
            "component": "VRow",
            "content": [
                {
                    "component": "VCol",
                    "props": {"cols": 12},
                    "content": [
                        {
                            "component": "VAlert",
                            "props": {"type": "info", "variant": "tonal",
                                      "density": "comfortable"},
                            "text": "下方目录版块按目标目录下的一级专辑目录列出转移记录，"
                                    "点击某个专辑目录，下方文件记录列表即筛选出该专辑下所有已转移文件（仅展示、不逐条删除）。"
                                    "每个专辑提供三种删除模式：「文件+记录」同时删除该专辑及其记录、「仅删文件」只删真实文件、「仅清记录」只清除记录。"
                                    "记录存于插件自身数据，与日志相互独立。",
                        }
                    ],
                }
            ],
        }
        action_row = {
            "component": "VRow",
            "content": [
                {
                    "component": "VCol",
                    "props": {"cols": 12, "md": 4},
                    "content": [
                        {"component": "VBtn",
                         "props": {"color": "primary", "variant": "flat"},
                         "text": "刷新列表",
                         "events": {"click": {
                             "api": "plugin/LinkSync/refresh",
                             "method": "get",
                             "params": {"apikey": settings.API_TOKEN},
                         }}}
                    ],
                },
                {
                    "component": "VCol",
                    "props": {"cols": 12, "md": 4},
                    "content": [
                        {"component": "VBtn",
                         "props": {"color": "primary", "variant": "tonal"},
                         "text": "立即全量同步",
                         "events": {"click": {
                             "api": "plugin/LinkSync/realtime_sync",
                             "method": "get",
                             "params": {"apikey": settings.API_TOKEN},
                         }}}
                    ],
                },
                {
                    "component": "VCol",
                    "props": {"cols": 12, "md": 4},
                    "content": [
                        {
                            "component": "div",
                            "props": {"class": "d-flex align-center ga-2"},
                            "content": [
                                {"component": "span",
                                 "props": {"class": "text-caption text-grey-darken-1"},
                                 "text": "清空全部目标目录："},
                                self._mode_group("plugin/LinkSync/clear",
                                                 lambda m: self._clear_btn_params("", m),
                                                 prefix="清空"),
                            ],
                        }
                    ],
                },
            ],
        }
        count_line = {
            "component": "div",
            "props": {"class": "text-body-2 text-grey"},
            "text": f"共 {len(records)} 条转移记录（停止自动实时刷新，可点击上方“刷新列表”手动更新）。",
        }

        # 无记录时直接返回提示
        if not records:
            return [{
                "component": "div",
                "props": {"class": "d-flex flex-column ga-3"},
                "content": [tips_row, action_row, {"component": "div", "props": {
                    "class": "text-center text-grey pa-4"},
                    "text": "暂无转移记录，新文件转移完成后会出现在这里。"}],
            }]

        # 按监控目录分组
        by_mon: Dict[str, Dict[str, dict]] = {}
        for rec in records.values():
            m = rec.get("mon_path") or ""
            by_mon.setdefault(m, {})[rec.get("rel") or ""] = rec

        mons = list(by_mon.keys())
        ui = self.__get_ui()
        cur_mon = ui.get("mon") if ui.get("mon") in mons else mons[0]
        rels = by_mon[cur_mon]
        top_rels, root_rels = self._top_dirs(rels)
        order = list(top_rels.keys())
        cur = ui.get("dir", "")
        # 归一化选中的专辑目录：无效值则回退到第一个
        if cur != ROOT_MARK and cur not in order:
            cur = order[0] if order else ROOT_MARK

        # 计算当前文件列表
        if cur == ROOT_MARK:
            file_rels = root_rels
            list_title = f"目标目录根下直接转移的文件（{len(file_rels)} 条）"
        elif cur:
            file_rels = top_rels[cur]
            list_title = f"{cur} 下的已转移文件记录（{len(file_rels)} 条）"
        else:
            file_rels = []
            list_title = "暂无专辑目录"

        content = [tips_row, action_row, count_line]

        # 监控目录切换（存在多个监控目录时）
        if len(mons) > 1:
            mon_btns = []
            for m in mons:
                chosen = (m == cur_mon)
                mon_btns.append({
                    "component": "VBtn",
                    "props": {"size": "small", "density": "compact",
                              "variant": "flat" if chosen else "outlined",
                              "color": "primary" if chosen else "default",
                              "prepend-icon": "mdi-check" if chosen else "mdi-folder-multiple"},
                    "text": f"{m}（{len(by_mon[m])}）",
                    "events": {"click": {
                        "api": "plugin/LinkSync/select_dir",
                        "method": "get",
                        "params": {"apikey": settings.API_TOKEN,
                                   "mon_path": m, "rel": cur},
                    }},
                })
            content.append({
                "component": "VRow",
                "props": {"class": "align-center"},
                "content": [
                    {"component": "VCol", "props": {"cols": 12, "sm": "auto"},
                     "content": [{"component": "span",
                                  "props": {"class": "text-caption text-grey-darken-1"},
                                  "text": "切换监控目录："}]},
                    {"component": "VCol",
                     "content": [{"component": "div",
                                  "props": {"class": "d-flex flex-wrap ga-1"},
                                  "content": mon_btns}]},
                ],
            })

        # 目录版块：一级专辑目录（每种删除三种模式）
        album_rows = []
        for name in order:
            album_rows.append(self._album_row(name, top_rels[name], cur, cur_mon))
        if root_rels:
            album_rows.append(self._root_switch(root_rels, cur, cur_mon))
        content.append({
            "component": "VCard",
            "props": {"variant": "tonal", "density": "comfortable"},
            "content": [
                {"component": "VCardTitle",
                 "props": {"class": "text-subtitle-2 text-primary"},
                 "content": [{"component": "div",
                              "text": f"目录版块（{cur_mon}）— 点击专辑切换下方列表"}]},
                {"component": "VCardText",
                 "props": {"class": "pa-1"},
                 "content": album_rows if album_rows else
                            [{"component": "div",
                              "props": {"class": "text-grey text-caption pa-2"},
                              "text": "该监控目录暂无转移记录"}]},
            ],
        })

        # 文件记录列表：当前选中专辑下的文件（仅展示）
        file_rows = [self._file_line(rel, rels.get(rel) or {}, 0) for rel in sorted(file_rels)]
        content.append({
            "component": "VCard",
            "props": {"variant": "tonal", "density": "comfortable"},
            "content": [
                {"component": "VCardTitle",
                 "props": {"class": "text-subtitle-2 text-primary"},
                 "content": [{"component": "div", "text": f"文件记录列表 — {list_title}"}]},
                {"component": "VCardText",
                 "props": {"class": "pa-1"},
                 "content": file_rows if file_rows else
                            [{"component": "div",
                              "props": {"class": "text-grey text-caption pa-2"},
                              "text": "当前目录暂无已转移文件记录。"}]},
            ],
        })

        return [{
            "component": "div",
            "props": {"class": "d-flex flex-column ga-3"},
            "content": content,
        }]

    def stop_service(self):
        """
        退出插件
        """
        if self._observer:
            for observer in self._observer:
                try:
                    observer.stop()
                    observer.join()
                except Exception as e:
                    print(str(e))
        self._observer = []
        if self._scheduler:
            self._scheduler.remove_all_jobs()
            if self._scheduler.running:
                self._event.set()
                self._scheduler.shutdown()
                self._event.clear()
            self._scheduler = None
        # 关闭并发转移线程池
        if self._executor:
            try:
                self._executor.shutdown(wait=False)
            except Exception as e:
                print(str(e))
            self._executor = None
        # 取消待发送的防抖通知并清理统计
        self.__cancel_flush()
        self.__reset_notify()