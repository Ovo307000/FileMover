class ProcessMethod:
    MOVE = 'move'  # 当文件发生变化时，将文件移动到 MOVE_TO 目录，然后删除源文件
    COPY = 'copy'  # 当文件发生变化时，将文件复制到 MOVE_TO 目录，保留源文件

class SyncFolder:
    """
    同步目录, 用于配置源目录和目标目录, 以及是否启用
    """
    source_path: str    # 源目录
    target_path: str    # 目标目录
    enable_status: bool # 是否启用

    def __init__(self, source_path: str, target_path: str, enable_status: bool):
        self.source_path = source_path
        self.target_path = target_path
        self.enable_status = enable_status

MOVE_TO: [str] = {
    r"C:\Users\solow\OneDrive\个人保管库\Images\R18\Anime\AI",
    r"C:\Users\solow\OneDrive\Image\Anime",
}  # 移动到的目录
WATCH_PATH: [str] = [r'A:\ComfyUI_windows_portable\ComfyUI\output']  # 监听的目录

WHITELISTED_EXTENSIONS: [str] = ['.jpg', '.jpeg', '.png', '.gif']  # 监听的文件扩展名
IGNORED_EXTENSIONS: [str] = ['.txt', '.py', '.md', '.gitignore']  # 忽略的文件扩展名
IGNORED_DIRECTORIES: [str] = ['__pycache__']  # 忽略的文件夹

SYNC_FOLDER_PATH_MAPPING: [SyncFolder] = [
    SyncFolder(r'A:\ComfyUI_windows_portable\ComfyUI\output', r'C:\Users\solow\OneDrive\个人保管库\Images\R18\Anime\AI', True),
    ]

RECURSIVE: bool = True  # 是否递归监听子目录
MAX_RETRY: int = 3  # 失败时的重试次数
WAIT_FOR_FILE_FAILED_TO_MOVE_RETRY: float = 5.0  # 失败时的重试间隔
WAIT_FOR_FILE_TO_STABILIZE: float = 1.0  # 等待文件稳定的时间
PROCESS_METHOD: str = ProcessMethod.COPY  # 处理文件的方式，可选值：move, copy
