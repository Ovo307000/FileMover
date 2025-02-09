"""
文件监控和处理模块。
该模块实现了文件系统监控和自动处理功能，支持文件的移动、复制和失败重试。
主要功能：
1. 监控指定目录的文件变化
2. 根据配置的规则处理新文件
3. 处理失败时进行重试
4. 记录处理失败的文件
"""

import asyncio
import hashlib
import os
import shutil
import time
from typing import Dict, Optional, List

import aiofiles
from loguru import logger
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from watchdog.observers import Observer

from configuration import ProcessMethod, config
from file.FileStatus import FileStatus


class FileProcessor:
    """
    文件处理器类。
    负责执行文件的实际处理操作，包括移动、复制、重试等。
    """

    def __init__(self):
        """初始化文件处理器，创建文件状态字典。"""
        self._file_tracking_dict: Dict[str, FileStatus] = {}

    def obtain_file_status(self, source_file_path: str) -> FileStatus:
        """
        获取文件的处理状态，如果不存在则创建新的状态。
        Args:
            file_path: 文件路径
        Returns:
            FileStatus: 文件的处理状态对象
        """
        if file_path not in self._file_tracking_dict:
            self._file_tracking_dict[file_path] = FileStatus()
        return self._file_tracking_dict[file_path]

    async def move_changed_file(self, file_path: str) -> None:
        """
        处理变化的文件。
        等待文件稳定后，根据配置将文件移动或复制到目标目录。

        Args:
            file_path: 要处理的文件路径
        """
        # 检查文件是否稳定，防止处理未写完的文件
        if not await self.wait_for_file_to_stabilize(file_path):
            logger.error(f"File {file_path} failed to stabilize")
            return

        # 判断是否白名单内，喵，如果文件类型不允许，就不屑处理啦
        if not self.is_whitelisted(file_path):
            logger.info(f"File {file_path} is not in the whitelist. Ignoring.")
            return

        # 从配置中获取目标目录列表（转换为List）并调用 move_file 进行移动操作
        await self.move_file(file_path, list(config.path.move_to), ProcessMethod.MOVE)

    def is_whitelisted(self, file_path: str) -> bool:
        """
        检查文件是否在白名单中。

        Args:
            file_path: 要检查的文件路径

        Returns:
            bool: 如果文件扩展名在白名单中返回 True，否则返回 False
        """
        return any(file_path.endswith(ext) for ext in config.file.whitelisted_extensions)

    async def move_file(self, source_file_path: str, target_file_paths: List[str], process_type: ProcessMethod) -> None:
        """
        移动或复制文件到目标目录。

        Args:
            source_file_path: 源文件路径
            target_file_paths: 目标目录列表
            process_type: 处理类型（移动或复制）
        """
        try:
            logger.info(f"Processing file {source_file_path} with method {process_type} to targets {target_file_paths}")

            # 遍历目标目录列表，处理每个目标目录, 移动或复制文件, 具体处理方式由 move_method 决定
            for target_directory in target_file_paths:
                await self.process_file_movement(source_file_path, target_directory, process_type)

        except (PermissionError, FileNotFoundError) as exception:
            logger.error(f"Failed to process file {source_file_path}. Error: {exception}")
            await self.handle_failed_file(source_file_path, target_file_paths[0], exception)

        except Exception as exception:
            logger.error(f"Unexpected error while processing {source_file_path}: {exception}")
            await self.save_failed_file(source_file_path, target_file_paths[0], exception)

    # 处理文件移动操作
    async def process_file_movement(self, source_file_path: str, target_directory: str,
                                    process_type: ProcessMethod) -> None:
        """
        处理文件移动操作。
        将文件移动到目标目录。

        Args:
            source_file_path: 源文件路径
            target_directory: 目标目录路径
            process_type: 处理类型（移动或复制）
        """
        start_time = time.time()
        os.makedirs(target_directory, exist_ok=True)
        target_path = os.path.join(target_directory, os.path.basename(source_file_path))

        match process_type:
            case ProcessMethod.MOVE:
                await asyncio.to_thread(shutil.move, source_file_path, target_path)
                logger.info(
                    f"Successfully moved file {source_file_path} to {target_directory} in {time.time() - start_time:.2f} seconds")
            case ProcessMethod.COPY:
                await asyncio.to_thread(shutil.copy2, source_file_path, target_path)
                logger.info(
                    f"Successfully copied file {source_file_path} to {target_directory} in {time.time() - start_time:.2f} seconds")

    async def handle_failed_file(self, file_path: str, target_directory: str, error: Exception) -> None:
        """
        处理文件处理失败的情况，根据配置的重试策略进行重试，超过重试次数后记录失败信息。

        Args:
            file_path: 失败的文件路径
            target_directory: 目标目录路径
            error: 导致失败的异常
        """
        status = self.obtain_file_status(file_path)

        if status.retry_count < config.retry.max_retries:
            status.retry_count += 1
            status.target_directory = target_directory
            logger.warning(
                f"Retrying to process file {file_path}. Attempt {status.retry_count}/{config.retry.max_retries}")
            await asyncio.sleep(config.retry.wait_for_retry)
            # 直接重试整个处理流程
            await self.move_changed_file(file_path)
        else:
            logger.error(f"Failed to process file {file_path} after {config.retry.max_retries} attempts")
            await self.save_failed_file(file_path, target_directory, error)
            self._file_tracking_dict.pop(file_path, None)

    async def wait_for_file_to_stabilize(self, source_file_path: str) -> bool:
        """
        等待文件大小稳定，用于确保文件写入完成。

        Args:
            source_file_path: 要监控的文件路径

        Returns:
            bool: 如果文件在超时时间内稳定返回 True，否则返回 False
        """
        start_time = time.time()
        last_size = -1

        while time.time() - start_time < config.retry.move_timeout:
            try:
                current_size = os.path.getsize(source_file_path)
                if current_size == last_size:
                    return True
                last_size = current_size
                await asyncio.sleep(config.retry.wait_for_stabilize)
            except OSError as e:
                logger.error(f"Error checking file size: {e}")
                return False

        return False

    async def save_failed_file(self, source_file_path: str, target_directory: str, error: Exception) -> None:
        """
        将处理失败的文件信息记录到日志文件。

        Args:
            file_path: 失败的文件路径
            target_directory: 目标目录路径
            error: 导致失败的异常
        """
        async with aiofiles.open('failed_files.txt', 'a') as f:
            await f.write(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Failed to process {source_file_path} to {target_directory}: {error}\n")

    async def get_file_hash(self, source_file_path: str) -> Optional[str]:
        """
        计算文件的 MD5 哈希值。
        结果会被缓存以提高性能。

        Args:
            source_file_path: 要计算哈希的文件路径

        Returns:
            Optional[str]: 文件的 MD5 哈希值，如果计算失败则返回 None
        """
        status = self.obtain_file_status(source_file_path)
        if status.hash_value:
            return status.hash_value

        try:
            file_hash = hashlib.md5()
            async with aiofiles.open(source_file_path, 'rb') as f:
                while chunk := await f.read(8192):
                    file_hash.update(chunk)

            status.hash_value = file_hash.hexdigest()
            return status.hash_value
        except Exception as exception:
            logger.error(f"Failed to generate hash for {source_file_path}: {exception}")
            return None


class DirectoryEventHandler(FileSystemEventHandler):
    """
    目录事件处理器，监听文件系统事件并触发相应的处理操作。
    """

    def __init__(self, processor: FileProcessor, loop: asyncio.AbstractEventLoop):
        """
        初始化事件处理器。

        Args:
            processor: 文件处理器实例
            loop: 事件循环实例
        """
        super().__init__()
        self.processor = processor
        self.loop = loop

    def on_created(self, event: FileModifiedEvent) -> None:
        """
        处理文件创建事件，当新文件创建时，将其加入处理队列。

        Args:
            event: 文件系统事件对象
        """
        if event.is_directory:
            return

        logger.info(f"File {event.src_path} has been created")
        asyncio.run_coroutine_threadsafe(self.processor.move_changed_file(event.src_path), self.loop)

    async def on_modified(self, event: FileModifiedEvent) -> None:
        """
        处理文件修改事件，当文件被修改时，将其加入处理队列。

        Args:
            event: 文件系统事件对象
        """
        if event.is_directory:
            return
        logger.info(f"File {event.src_path} has been modified")
        # 可根据需要添加文件修改处理逻辑


async def monitor_directory() -> None:
    """
    启动目录监控。
    创建文件处理器和观察者，开始监控配置的目录。
    """
    processor = FileProcessor()
    event_loop = asyncio.get_running_loop()
    observer = Observer()

    for watch_path in config.path.watch_paths:
        if not os.path.exists(watch_path):
            os.makedirs(watch_path)

        event_handler = DirectoryEventHandler(processor, event_loop)
        observer.schedule(event_handler, watch_path, recursive=config.recursive)

    observer.start()

    try:
        logger.info(f"Monitoring directories: {', '.join(config.path.watch_paths)}")
        logger.info(f"Target directories: {', '.join(config.path.move_to)}")
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == '__main__':
    logger.info("Starting file mover...")
    asyncio.run(monitor_directory())
