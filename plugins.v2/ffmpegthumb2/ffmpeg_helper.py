import json
import subprocess
import shutil
import os
from typing import Optional

from app.utils.system import SystemUtils


def _time_str_to_seconds(time_str: str) -> Optional[float]:
    """
    把 "HH:MM:SS[.ms]" 或 "MM:SS" 或 "SS" 等格式转为秒(float)
    """
    try:
        parts = time_str.split(':')
        parts = [float(p) for p in parts]
        seconds = 0.0
        for p in parts:
            seconds = seconds * 60 + p
        return seconds
    except Exception:
        return None


class FfmpegHelper2:
    # 默认限制 ffmpeg 使用的线程数（根据机器调整）
    DEFAULT_THREADS = 1
    # 在目标时间前预seek多少秒（two-stage seek），用来减少解码量同时保留精度
    DEFAULT_PRESEEK_OFFSET = 2.0
    # 子进程超时时间（秒），避免长时间挂起
    DEFAULT_TIMEOUT = 30

    # 全局优化开关：优先从环境变量读取（"1" 开启, "0" 关闭），默认开启
    ENV_FLAG_NAME = "FFMPEG_OPTIMIZATIONS"
    DEFAULT_ENV_FLAG = "1"

    @staticmethod
    def _env_opt_enabled() -> bool:
        val = os.getenv(FfmpegHelper2.ENV_FLAG_NAME,
                        FfmpegHelper2.DEFAULT_ENV_FLAG)
        return val != "0"

    @staticmethod
    def _which(exe_name: str) -> Optional[str]:
        return shutil.which(exe_name)

    @staticmethod
    def _run_cmd(command: list, timeout: int = DEFAULT_TIMEOUT) -> bool:
        """
        统一运行 subprocess 的包装：返回 True/False，不抛出异常（会打印错误）
        """
        try:
            # 使用 timeout 防止进程挂起
            ret = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            if ret.returncode == 0:
                return True
            # 若失败，打印 stderr 用于诊断
            print(f"ffmpeg/ffprobe failed: {' '.join(command)}")
            try:
                print(ret.stderr.decode("utf-8", errors="ignore"))
            except Exception:
                pass
            return False
        except subprocess.TimeoutExpired:
            print(f"ffmpeg/ffprobe timeout: {' '.join(command)}")
            return False
        except Exception as e:
            print("Subprocess run exception:", e)
            return False

    @staticmethod
    def get_thumb(video_path: str, image_path: str, frames: str = None,
                  threads: int = DEFAULT_THREADS, preseek_offset: float = DEFAULT_PRESEEK_OFFSET,
                  timeout: int = DEFAULT_TIMEOUT, enable_optimizations: Optional[bool] = None):
        """
        使用 ffmpeg 截图
        - 如果 enable_optimizations 为 True：使用 two-stage seek（先快速 seek 到 t-preseek_offset，再小范围精确 seek）
        - 如果为 False：使用原始行为（-ss 在 -i 之后的精确 seek，兼容旧逻辑）
        - enable_optimizations 参数优先于环境变量 FFMPEG_OPTIMIZATIONS
        """
        if not frames:
            frames = "00:03:01"
        if not video_path or not image_path:
            return False

        # 决定是否启用优化
        if enable_optimizations is None:
            enable_optimizations = FfmpegHelper2._env_opt_enabled()

        # 检查 ffmpeg 是否存在
        if not FfmpegHelper2._which("ffmpeg"):
            print("ffmpeg not found in PATH")
            return False

        if not enable_optimizations:
            # 保持原始行为（字符串命令、使用 SystemUtils.execute），尽量不更改调用方式
            cmd = 'ffmpeg -i "{video_path}" -ss {frames} -vframes 1 -f image2 "{image_path}"'.format(
                video_path=video_path, frames=frames, image_path=image_path
            )
            # 原代码使用 SystemUtils.execute，这里沿用以保持兼容
            result = SystemUtils.execute(cmd)
            return bool(result)

        # ---- 优化路径 ----
        secs = _time_str_to_seconds(frames)
        # 如果无法解析时间字符串，则直接用精确 seek（-ss 在 -i 之后）
        if secs is None:
            # 精确 seek（准确但慢）
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-i", video_path,
                "-ss", frames,
                "-vframes", "1",
                "-q:v", "2",
                "-threads", str(threads),
                image_path
            ]
            return FfmpegHelper2._run_cmd(command, timeout=timeout)

        # two-stage seek: preseek 到 max(0, secs - preseek_offset)，然后在输入后做 delta 精确 seek
        preseek_secs = max(0.0, secs - float(preseek_offset))
        delta = secs - preseek_secs

        # 如果 preseek_offset 为 0 或 delta 过小（例如 0.0），直接使用精确 seek（-ss after -i）
        if preseek_secs <= 0.0 or preseek_offset <= 0.0:
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-i", video_path,
                "-ss", str(secs),
                "-vframes", "1",
                "-q:v", "2",
                "-threads", str(threads),
                image_path
            ]
            return FfmpegHelper2._run_cmd(command, timeout=timeout)

        # two-stage: fast seek then accurate small seek
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-ss", str(preseek_secs),
            "-i", video_path,
            "-ss", str(delta),
            "-vframes", "1",
            "-q:v", "2",
            "-threads", str(threads),
            image_path
        ]
        ok = FfmpegHelper2._run_cmd(command, timeout=timeout)
        # 若 two-stage 失败，可以回退到精确 seek（更慢但更可能成功）
        if not ok:
            fallback = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-i", video_path,
                "-ss", str(secs),
                "-vframes", "1",
                "-q:v", "2",
                "-threads", str(threads),
                image_path
            ]
            return FfmpegHelper2._run_cmd(fallback, timeout=timeout)
        return True

    @staticmethod
    def extract_wav(video_path: str, audio_path: str, audio_index: str = None,
                    threads: int = DEFAULT_THREADS, timeout: int = DEFAULT_TIMEOUT,
                    enable_optimizations: Optional[bool] = None):
        """
        从视频文件中提取 16000Hz, 16-bit 单声道 wav
        - enable_optimizations 控制是否使用 -vn（避免处理视频轨）等优化
        """
        if not video_path or not audio_path:
            return False
        if not FfmpegHelper2._which("ffmpeg"):
            print("ffmpeg not found in PATH")
            return False

        if enable_optimizations is None:
            enable_optimizations = FfmpegHelper2._env_opt_enabled()

        if not enable_optimizations:
            # 原始行为（尽量保持原来参数）
            if audio_index:
                command = ['ffmpeg', "-hide_banner", "-loglevel", "warning", '-y', '-i', video_path,
                           '-map', f'0:a:{audio_index}',
                           '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000', audio_path]
            else:
                command = ['ffmpeg', "-hide_banner", "-loglevel", "warning", '-y', '-i', video_path,
                           '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000', audio_path]
            ret = subprocess.run(command).returncode
            return ret == 0

        # 优化路径：添加 -vn、限制线程并使用超时
        base = ["ffmpeg", "-hide_banner", "-loglevel",
                "error", "-nostdin", "-y", "-i", video_path, "-vn"]
        if audio_index is not None:
            base += ["-map", f"0:a:{audio_index}"]

        base += ["-acodec", "pcm_s16le", "-ac", "1", "-ar",
                 "16000", "-threads", str(threads), audio_path]
        return FfmpegHelper2._run_cmd(base, timeout=timeout)

    @staticmethod
    def get_metadata(video_path: str, timeout: int = DEFAULT_TIMEOUT):
        """
        获取视频元数据（ffprobe），使用超时并返回 dict 或 None
        """
        if not video_path:
            return None
        if not FfmpegHelper2._which("ffprobe"):
            print("ffprobe not found in PATH")
            return None
        try:
            command = ["ffprobe", "-v", "quiet", "-print_format",
                       "json", "-show_format", "-show_streams", video_path]
            ret = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            if ret.returncode == 0:
                return json.loads(ret.stdout.decode("utf-8", errors="ignore"))
        except subprocess.TimeoutExpired:
            print("ffprobe timeout")
        except Exception as e:
            print("ffprobe exception:", e)
        return None

    @staticmethod
    def extract_subtitle(video_path: str, subtitle_path: str, subtitle_index: str = None,
                         threads: int = DEFAULT_THREADS, timeout: int = DEFAULT_TIMEOUT,
                         enable_optimizations: Optional[bool] = None):
        """
        从视频中提取字幕。
        - enable_optimizations=True 时优先使用 -c:s copy 避免重新编码（更快）。
        - enable_optimizations=False 时尽量保持原始行为（不强制 -c:s copy）。
        """
        if not video_path or not subtitle_path:
            return False
        if not FfmpegHelper2._which("ffmpeg"):
            print("ffmpeg not found in PATH")
            return False

        if enable_optimizations is None:
            enable_optimizations = FfmpegHelper2._env_opt_enabled()

        if not enable_optimizations:
            if subtitle_index:
                command = ['ffmpeg', "-hide_banner", "-loglevel", "warning", '-y', '-i', video_path,
                           '-map', f'0:s:{subtitle_index}',
                           subtitle_path]
            else:
                command = ['ffmpeg', "-hide_banner", "-loglevel",
                           "warning", '-y', '-i', video_path, subtitle_path]
            ret = subprocess.run(command).returncode
            return ret == 0

        # 优化路径
        if subtitle_index is not None:
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-i", video_path,
                "-map", f"0:s:{subtitle_index}",
                "-c:s", "copy",
                "-threads", str(threads),
                subtitle_path
            ]
        else:
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-i", video_path,
                "-c:s", "copy",
                "-threads", str(threads),
                subtitle_path
            ]
        return FfmpegHelper2._run_cmd(command, timeout=timeout)


# 使用说明（要点）
# - 用环境变量控制（优先级低于方法参数）:
#     export FFMPEG_OPTIMIZATIONS=1   # 启用优化（默认）
#     export FFMPEG_OPTIMIZATIONS=0   # 禁用优化（恢复原始行为）
# - 或在调用时传入 enable_optimizations=False/True 覆盖环境变量，例如:
#     FfmpegHelper2.get_thumb(path_video, path_image, enable_optimizations=False)
# - 建议把耗时的提取工作放到后台线程池或任务队列（ThreadPoolExecutor / Celery / RQ）以避免阻塞主线程.
