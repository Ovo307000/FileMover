"""
文件监控和处理的配置模块。
该模块定义了文件处理器所需的所有配置项，包括文件处理方式、路径配置、重试策略等。
所有配置都使用数据类（dataclass）和枚举（Enum）来确保类型安全和不可变性。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Set


class ProcessMethod(str, Enum):
    """
    文件处理方式的枚举类。
    继承自 str 以支持字符串比较和序列化。
    """
    MOVE = 'move'  # 将文件移动到目标目录，源文件会被删除
    COPY = 'copy'  # 将文件复制到目标目录，源文件会被保留


@dataclass
class SyncFolder:
    """
    同步目录的配置类。
    用于定义源目录和目标目录之间的同步关系。
    
    Attributes:
        source_path: 源目录的路径
        target_path: 目标目录的路径
        enable_status: 是否启用该同步配置
    """
    source_path: str  # 源目录路径
    target_path: str  # 目标目录路径
    enable_status: bool  # 是否启用该配置


@dataclass
class FileConfig:
    """
    文件处理的相关配置。
    定义了文件处理的过滤规则，包括白名单和黑名单。
    
    Attributes:
        whitelisted_extensions: 允许处理的文件扩展名集合
        ignored_extensions: 需要忽略的文件扩展名集合
        ignored_directories: 需要忽略的目录名集合
    """
    whitelisted_extensions: Set[str] = frozenset({'.jpg', '.jpeg', '.png', '.gif'})
    ignored_extensions: Set[str] = frozenset({'.txt', '.py', '.md', '.gitignore'})
    ignored_directories: Set[str] = frozenset({'__pycache__'})


@dataclass
class PathConfig:
    """
    路径相关的配置。
    定义了文件监控和处理的路径配置。
    
    Attributes:
        move_to: 文件处理后的目标目录集合
        watch_paths: 需要监控的源目录列表
        sync_folders: 需要同步的目录配置列表
    """
    move_to: Set[str] = frozenset({r"C:\Users\solow\OneDrive\Image\Ai"})
    watch_paths: List[str] = field(default_factory=lambda: [r'A:\ComfyUI_windows_portable\ComfyUI\output'])
    sync_folders: List[SyncFolder] = field(default_factory=lambda: [
        SyncFolder(
            r'A:\ComfyUI_windows_portable\ComfyUI\output',
            r'C:\Users\solow\OneDrive\个人保管库\Images\R18\Anime\AI',
            True
        )
    ])


@dataclass
class RetryConfig:
    """
    重试策略的配置。
    定义了文件处理失败时的重试行为。
    
    Attributes:
        max_retries: 最大重试次数
        wait_for_retry: 重试之间的等待时间（秒）
        wait_for_stabilize: 等待文件稳定的时间（秒）
        move_timeout: 文件处理的超时时间（秒）
    """
    max_retries: int = 3
    wait_for_retry: float = 5.0
    wait_for_stabilize: float = 1.0
    move_timeout: float = 30.0


@dataclass
class Config:
    """
    全局配置类。
    整合了所有配置项，提供了一个统一的配置接口。
    
    Attributes:
        file: 文件处理相关的配置
        path: 路径相关的配置
        retry: 重试策略的配置
        process_method: 文件处理方式
        recursive: 是否递归监控子目录
    """
    file: FileConfig = field(default_factory=FileConfig)
    path: PathConfig = field(default_factory=PathConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    process_method: ProcessMethod = ProcessMethod.COPY
    recursive: bool = True


# 创建全局配置实例
config = Config()
