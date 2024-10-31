import asyncio
import hashlib
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor

import aiofiles
from loguru import logger
from watchdog.events import FileSystemEventHandler, DirModifiedEvent, FileModifiedEvent
from watchdog.observers import Observer

import configuration


class FileProcessor:
    # 采用 Map 来保存重试次数，键值对为文件路径和重试次数
    retries: dict[str, int] = {}

    # 采用 Map 来保存文件的哈希值，键值对为文件路径和哈希值
    hash_cache: dict[str, str] = {}

    executor = ThreadPoolExecutor(max_workers=256)

    @staticmethod
    async def move_changed_file(file_path: str) -> None:
        # 等待文件稳定
        await FileProcessor.wait_for_file_to_stabilize(file_path)

        try:
            logger.info(f"Moving file {file_path} to {configuration.MOVE_TO}")

            start_time = time.time()

            match configuration.PROCESS_METHOD:
                case configuration.ProcessMethod.MOVE:
                    await asyncio.to_thread(shutil.move, file_path, configuration.MOVE_TO, copy_function=shutil.copy2)
                case configuration.ProcessMethod.COPY:
                    await asyncio.to_thread(shutil.copy, file_path, configuration.MOVE_TO)

            logger.info(
                f"Successfully moved file {file_path} to {configuration.MOVE_TO} in {time.time() - start_time:.2f} seconds")

        except (PermissionError, FileNotFoundError) as file_error:
            logger.error(f"Failed to move file {file_path}. Error: {file_error}")
            await FileProcessor.retry_failed_files(file_path, file_error)

        except Exception as e:
            logger.error(f"Failed to move file {file_path}. Error: {e}")
            FileProcessor.retries.pop(file_path)

    @staticmethod
    async def retry_failed_files(file_path: str, exception: Exception) -> None:
        if FileProcessor.retries.get(file_path, 0) < configuration.MAX_RETRY:
            FileProcessor.retries[file_path] = FileProcessor.retries.get(file_path, 0) + 1
            logger.warning(
                f"Failed to move file {file_path}.\
                Because of {exception}, We will retry in {configuration.WAIT_FOR_FILE_FAILED_TO_MOVE_RETRY} seconds.\
                Now retrying {FileProcessor.retries[file_path]}/{configuration.MAX_RETRY}")
            await asyncio.sleep(configuration.WAIT_FOR_FILE_FAILED_TO_MOVE_RETRY)
            await FileProcessor.move_changed_file(file_path)
        else:
            logger.error(
                f"After {configuration.MAX_RETRY} retries, failed to move file {file_path}. Error: {exception}")
            FileProcessor.retries.pop(file_path)

            logger.info(f"Saving failed file {file_path} to failed_files.txt")
            await FileProcessor.save_failed_file(file_path, exception)

    @staticmethod
    def create_directory_if_not_exists(file_path: str) -> None:
        try:
            if not os.path.exists(file_path):
                os.makedirs(file_path)
        except Exception as e:
            logger.error(f"Failed to create directory {file_path}. Error: {e}")

    @staticmethod
    async def save_failed_file(file_path: str, e: Exception) -> None:
        async with aiofiles.open('failed_files.txt', 'a') as f:
            await f.write(f"""
            [{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}]
             
             Failed to move file `{file_path}`
             Error: {e}
             
             
            """)

    @staticmethod
    async def wait_for_file_to_stabilize(file_path: str) -> bool:
        waiting_count = 0

        while True:
            # 如果文件大小在等待时间内没有变化，那么认为文件已经稳定
            current_size = os.path.getsize(file_path)

            await asyncio.sleep(configuration.WAIT_FOR_FILE_TO_STABILIZE)
            logger.debug(f"Waiting for file {file_path} to stabilize...")
            logger.debug(f"Current file size: {current_size}, Previous file size: {os.path.getsize(file_path)}")

            if current_size == os.path.getsize(file_path):
                logger.info(
                    f"I think file `{file_path}` after `{waiting_count}` times `{current_size} bytes` is finally stabilized.")
                return True
            else:
                waiting_count += 1
                logger.debug(f"File {file_path} is still changing... Waiting for {waiting_count} times...")

    @staticmethod
    def file_hash(file_path: str) -> str:
        if file_path in FileProcessor.hash_cache:
            return FileProcessor.hash_cache[file_path]

        file_hash = hashlib.md5()

        def generate_hash():
            with open(file_path, 'rb') as f:
                while chunk := f.read(4096):
                    file_hash.update(chunk)

        try:
            generate_hash()
        except Exception as e:
            logger.error(f"Failed to generate hash for file {file_path}. Error: {e}")
            return ""

        FileProcessor.hash_cache[file_path] = file_hash.hexdigest()
        return FileProcessor.hash_cache[file_path]

    @staticmethod
    async def sync_folders(source_folder: str, target_folder: str) -> None:
        copied_files_count = 0
        copied_directories_count = 0
        start_time = time.time()

        # 如果目标文件夹不存在，则创建它
        FileProcessor.create_directory_if_not_exists(target_folder)

        tasks = []  # 用于存储异步任务

        # 复制源文件夹的内容到目标文件夹
        for item in os.listdir(source_folder):
            source_path = os.path.join(source_folder, item)
            target_path = os.path.join(target_folder, item)

            # 如果是文件，且文件扩展名在白名单中，且文件哈希值不同，那么复制文件
            if (os.path.isfile(source_path)
                    and source_path.endswith(tuple(configuration.WHITELISTED_EXTENSIONS))):
                tasks.append(FileProcessor.handle_file_copy(source_path, target_path))

            # 如果是目录，递归复制
            elif os.path.isdir(source_path):
                tasks.append(FileProcessor.sync_folders(source_path, target_path))

        results = await asyncio.gather(*tasks)  # 并行执行任务

        # 统计复制的文件和目录数量
        for result in results:
            if isinstance(result, tuple):
                copied_files_count += result[0]
                copied_directories_count += result[1]

        logger.info(
            f"Successfully copied {copied_files_count} files and {copied_directories_count} directories from {source_folder} to {target_folder}")
        logger.info(f"Time taken: {time.time() - start_time:.2f} seconds")

    @staticmethod
    async def handle_file_copy(source_path: str, target_path: str) -> tuple:
        source_path_hash = FileProcessor.file_hash(source_path)
        target_path_hash = FileProcessor.file_hash(target_path)

        # 如果源文件和目标文件的哈希值不同，那么复制文件
        if source_path_hash != target_path_hash:
            logger.info(f"Copying file {source_path} to {target_path}")
            await asyncio.to_thread(shutil.copy, source_path, target_path)
            return 1, 0  # 返回复制的文件和目录数量
        return 0, 0  # 没有复制的文件和目录数量


class DirectoryEventHandler(FileSystemEventHandler):
    def __init__(self, loop):
        super().__init__()
        self.loop = loop  # 保存事件循环

    def on_created(self, event: DirModifiedEvent | FileModifiedEvent) -> None:
        if event.is_directory:
            logger.debug(f"Directory modified: {event.src_path} but we are not interested in directories :(")
            return

        logger.info(f"File {event.src_path} has been {event.event_type}")

        # 如果文件是被修改的，且文件扩展名在白名单中，那么移动文件
        if event.src_path.endswith(tuple(configuration.WHITELISTED_EXTENSIONS)):
            # 在主线程的事件循环中安全地调度异步任务
            asyncio.run_coroutine_threadsafe(FileProcessor.move_changed_file(event.src_path), self.loop)
        else:
            logger.info(f"File {event.src_path} is not in the whitelist. Ignoring.")


async def monitor_directory():
    event_loop = asyncio.get_running_loop()  # 获取当前事件循环
    observer = Observer()  # 创建观察者对象，用于监视文件系统变化

    for directory in configuration.WATCH_PATH:
        # 创建目录，为了避免在移动文件时出现目录不存在的错误
        FileProcessor.create_directory_if_not_exists(directory)
        # 创建事件处理器，用于处理文件系统事件
        event_handler = DirectoryEventHandler(event_loop)

        # 根据配置递归或非递归地监视目录，然后将事件处理器添加到观察者对象中
        if configuration.RECURSIVE:
            observer.schedule(event_handler, directory, recursive=True)
        else:
            observer.schedule(event_handler, directory, recursive=False)

    observer.start()

    try:
        logger.info(f"Monitoring directory {configuration.WATCH_PATH[0]}")

        # 将文件同步操作放入一个异步任务中
        if configuration.SYNC_FOLDER:
            logger.info("Starting to sync folders...")
            for source_folder, target_folder in configuration.SYNC_FOLDER_PATH_MAP.items():
                asyncio.create_task(FileProcessor.sync_folders(source_folder, target_folder))

        while True:
            await asyncio.sleep(10)  # 保持主线程运行

            logger.debug("Main thread is still running...")
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == '__main__':
    logger.info("Starting file mover...")

    asyncio.run(monitor_directory())
