class ProcessMethod:
    MOVE = 'move'   # 当文件发生变化时，将文件移动到 MOVE_TO 目录，然后删除源文件
    COPY = 'copy'   # 当文件发生变化时，将文件复制到 MOVE_TO 目录，保留源文件

MOVE_TO:str = r'C:\Users\solow\OneDrive\Images\Anime\R18'               # 监听到文件变化后，将文件移动到此目录
WATCH_PATH:[str] = [r'A:\ComfyUI_windows_portable\ComfyUI\output']      # 监听的目录

WHITELISTED_EXTENSIONS:[str] = ['.jpg', '.jpeg', '.png', '.gif']        # 监听的文件扩展名
IGNORED_EXTENSIONS:[str] = ['.txt', '.py', '.md', '.gitignore']         # 忽略的文件扩展名
IGNORED_DIRECTORIES:[str] = ['__pycache__']                             # 忽略的文件夹

RECURSIVE:bool = True                                                   # 是否递归监听子目录
MAX_RETRY:int = 3                                                       # 失败时的重试次数
PROCESS_METHOD:str = ProcessMethod.COPY                                 # 处理文件的方式，可选值：move, copy