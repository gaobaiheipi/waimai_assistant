# utils/model_downloader.py
import os
import threading
from kivy.clock import Clock
from typing import Callable, Optional

from utils.paths import get_models_dir


class ModelDownloader:
    """静默模型下载器"""

    def __init__(self):
        self.is_downloading = False
        self.download_complete = False
        self.download_progress = 0
        self.status = "等待下载"
        self._callbacks = []

    def check_model_exists(self) -> bool:
        """检查0.5B模型是否存在"""
        model_path = os.path.join(get_models_dir(), "Qwen2.5-0.5B-Instruct")
        key_file = os.path.join(model_path, "model.safetensors")

        if os.path.exists(key_file):
            # 检查文件大小是否合理（至少100MB）
            if os.path.getsize(key_file) > 100 * 1024 * 1024:
                return True
        return False

    def start_download(self, callback: Optional[Callable] = None):
        """后台静默下载"""
        if self.is_downloading or self.check_model_exists():
            if callback:
                callback(True, "模型已存在")
            return

        self.is_downloading = True
        if callback:
            self._callbacks.append(callback)

        def _download():
            try:
                from huggingface_hub import snapshot_download

                local_path = os.path.join(get_models_dir(), "Qwen2.5-0.5B-Instruct")
                os.makedirs(local_path, exist_ok=True)

                print("[下载] 开始后台下载0.5B模型...")

                # 使用镜像下载
                snapshot_download(
                    repo_id="Qwen/Qwen2.5-0.5B-Instruct",
                    local_dir=local_path,
                    local_dir_use_symlinks=False,
                    endpoint="https://hf-mirror.com",
                    resume_download=True,
                )

                self.download_complete = True
                print("[下载] 模型下载完成")

                for cb in self._callbacks:
                    Clock.schedule_once(lambda dt: cb(True, "下载完成"), 0)

            except Exception as e:
                print(f"[下载] 失败: {e}")
                for cb in self._callbacks:
                    Clock.schedule_once(lambda dt: cb(False, str(e)), 0)
            finally:
                self.is_downloading = False

        threading.Thread(target=_download, daemon=True).start()


model_downloader = ModelDownloader()