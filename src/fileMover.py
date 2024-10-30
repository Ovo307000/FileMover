import asyncio
import os
import shutil
import time

import aiofiles
from loguru import logger
from watchdog.events import FileSystemEventHandler, DirModifiedEvent, FileModifiedEvent
from watchdog.observers import Observer

import configuration


class FileProcessor:
    # 采用 Map 来保存重试次数，键值对为文件路径和重试次数
    retries: dict[str, int] = {}

    @staticmethod
    async def move_changed_file(file_path: str) -> None:
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
            if FileProcessor.retries.get(file_path, 0) < configuration.MAX_RETRY:
                FileProcessor.retries[file_path] = FileProcessor.retries.get(file_path, 0) + 1
                logger.warning(
                    f"Failed to move file {file_path}.\
                    Because of {file_error}, We will retry in {configuration.WAIT_TIME} seconds.\
                    Now retrying {FileProcessor.retries[file_path]}/{configuration.MAX_RETRY}")
                await asyncio.sleep(configuration.WAIT_TIME)
                await FileProcessor.move_changed_file(file_path)
            else:
                logger.error(
                    f"After {configuration.MAX_RETRY} retries, failed to move file {file_path}. Error: {file_error}")
                FileProcessor.retries.pop(file_path)

                logger.info(f"Saving failed file {file_path} to failed_files.txt")
                await FileProcessor.save_failed_file(file_path, file_error)

        except Exception as e:
            logger.error(f"Failed to move file {file_path}. Error: {e}")
            FileProcessor.retries.pop(file_path)

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
            await f.write(f"'{file_path}' failed to move at {time.strftime('%Y-%m-%d %H:%M:%S')} \n \
                            Error: {e}\n")


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
    observer = Observer()  # 创建观察者对象, 用于监视文件系统变化

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
        while True:
            await asyncio.sleep(10)  # 保持主线程运行
            logger.debug("I am still alive~~~ balabalabala~~~")
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == '__main__':
    logger.info("Starting file mover...")

    asyncio.run(monitor_directory())
