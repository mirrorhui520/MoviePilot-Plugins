import json
import subprocess
import shutil
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


class FfmpegHelper:
    # 默认限制 ffmpeg 使用的线程数（根据机器调整）
    DEFAULT_THREADS = 1
    # 在目标时间前预seek多少秒（two-stage seek），用来减少解码量同时保留精度
    DEFAULT_PRESEEK_OFFSET = 2.0
    # 子进程超时时间（秒），避免长时间挂起
    DEFAULT_TIMEOUT = 30

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
                  timeout: int = DEFAULT_TIMEOUT):
        """
        使用 ffmpeg 截图（two-stage seek）
        - 为兼顾效率与精度：先快速 seek 到 (t - preseek_offset)（keyframe），再在输入后精确 seek preseek_offset 秒
        - 若 frames 解析失败或 preseek_offset=0 则使用精确 seek（-ss 在 -i 之后）
        """
        if not frames:
            frames = "00:03:01"
        if not video_path or not image_path:
            return False

        # 检查 ffmpeg 是否存在
        if not FfmpegHelper._which("ffmpeg"):
            print("ffmpeg not found in PATH")
            return False

        secs = _time_str_to_seconds(frames)
        # 如果无法解析时间字符串，则直接用原来的精确 seek（慢）
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
            return FfmpegHelper._run_cmd(command, timeout=timeout)

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
            return FfmpegHelper._run_cmd(command, timeout=timeout)

        # two-stage: fast seek then accurate small seek
        # 注意参数顺序：-ss 前置在 -i 之前；第二个 -ss 在输入之后。
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
        ok = FfmpegHelper._run_cmd(command, timeout=timeout)
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
            return FfmpegHelper._run_cmd(fallback, timeout=timeout)
        return True

    @staticmethod
    def extract_wav(video_path: str, audio_path: str, audio_index: str = None,
                    threads: int = DEFAULT_THREADS, timeout: int = DEFAULT_TIMEOUT):
        """
        从视频文件中提取 16000Hz, 16-bit 单声道 wav
        - 加入 -vn 禁止视频处理，限制线程，设置超时
        """
        if not video_path or not audio_path:
            return False
        if not FfmpegHelper._which("ffmpeg"):
            print("ffmpeg not found in PATH")
            return False

        base = ["ffmpeg", "-hide_banner", "-loglevel",
                "error", "-nostdin", "-y", "-i", video_path, "-vn"]
        if audio_index is not None:
            base += ["-map", f"0:a:{audio_index}"]

        base += ["-acodec", "pcm_s16le", "-ac", "1", "-ar",
                 "16000", "-threads", str(threads), audio_path]
        return FfmpegHelper._run_cmd(base, timeout=timeout)

    @staticmethod
    def get_metadata(video_path: str, timeout: int = DEFAULT_TIMEOUT):
        """
        获取视频元数据（ffprobe），使用超时并返回 dict 或 None
        """
        if not video_path:
            return None
        if not FfmpegHelper._which("ffprobe"):
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
                         threads: int = DEFAULT_THREADS, timeout: int = DEFAULT_TIMEOUT):
        """
        从视频中提取字幕。优先使用 -c:s copy 避免重新编码（更快）。
        """
        if not video_path or not subtitle_path:
            return False
        if not FfmpegHelper._which("ffmpeg"):
            print("ffmpeg not found in PATH")
            return False

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
            # 如果用户没有指定字幕流，直接尝试导出第一个字幕流（可能需要 ffmpeg 自动选择）
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-i", video_path,
                "-c:s", "copy",
                "-threads", str(threads),
                subtitle_path
            ]
        return FfmpegHelper._run_cmd(command, timeout=timeout)

# 使用建议：
# - 在 web 服务中不要直接在请求线程里同步调用这些方法（尤其是耗时的音频/字幕操作）。
# - 建议用 ThreadPoolExecutor.submit(...) 或推到专门队列（Celery / RQ），只把结果写回数据库或通知前端。
#
# 示例（简单）:
# from concurrent.futures import ThreadPoolExecutor
# executor = ThreadPoolExecutor(max_workers=2)
# future = executor.submit(FfmpegHelper.get_thumb, video_path, image_path, "00:01:10")
# # future.result(timeout=60) 或者定期查询 future.done()
