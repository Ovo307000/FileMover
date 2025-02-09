from dataclasses import dataclass


@dataclass
class FileStatus:
    """
    文件处理状态的数据类。
    用于跟踪文件处理过程中的状态信息。

    Attributes:
        retry_count: 当前重试次数
        target_directory: 目标目录路径
        hash_value: 文件的哈希值（用于文件比较）
    """
    retry_count: int = 0
    target_directory: str = ""
    hash_value: str = ""
