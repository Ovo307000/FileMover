class ProcessMethod:
    MOVE = 'move'  # 当文件发生变化时，将文件移动到 MOVE_TO 目录，然后删除源文件
    COPY = 'copy'  # 当文件发生变化时，将文件复制到 MOVE_TO 目录，保留源文件


MOVE_TO: str = r'C:\Users\solow\OneDrive\个人保管库\Images\R18\Anime\AI'  # 监听到文件变化后，将文件移动到此目录
WATCH_PATH: [str] = [r'A:\ComfyUI_windows_portable\ComfyUI\output']  # 监听的目录

WHITELISTED_EXTENSIONS: [str] = ['.jpg', '.jpeg', '.png', '.gif']  # 监听的文件扩展名
IGNORED_EXTENSIONS: [str] = ['.txt', '.py', '.md', '.gitignore']  # 忽略的文件扩展名
IGNORED_DIRECTORIES: [str] = ['__pycache__']  # 忽略的文件夹

SYNC_FOLDER: bool = True  # 是否同步文件夹
SYNC_FOLDER_PATH_MAP: dict = {
    # 源目录: 目标目录, 例如: r'A:\ComfyUI_windows_portable\ComfyUI\output': r'C:\Users\solow\OneDrive\Images\Anime\R18'
    # 如果你有多个源目录需要同一个目标目录，可以这样配置：
    # r'A:\ComfyUI_windows_portable\ComfyUI\output': r'C:\Users\solow\OneDrive\Images\Anime\R18',
    # r'A:\ComfyUI_windows_portable\ComfyUI\output2': r'C:\Users\solow\OneDrive\Images\Anime\R18'
    # 当 SYNC_FOLDER 为 True 时，会将源目录下的文件同步到目标目录，不会删除源文件，只会复制

        r'A:\ComfyUI_windows_portable\ComfyUI\output': r'C:\Users\solow\OneDrive\Images\Anime\R18'
    }

RECURSIVE: bool = True  # 是否递归监听子目录
MAX_RETRY: int = 3  # 失败时的重试次数
WAIT_FOR_FILE_FAILED_TO_MOVE_RETRY: float = 5.0  # 失败时的重试间隔
WAIT_FOR_FILE_TO_STABILIZE: float = 1.0  # 等待文件稳定的时间
PROCESS_METHOD: str = ProcessMethod.COPY  # 处理文件的方式，可选值：move, copy
