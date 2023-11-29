
import os
import time


def cur_time(format=None):
    """Get current time in human or file format.

    Args:
        format (str, optional): 'human' or 'file'. Defaults to None.
            human: 2021-09-22 21:30:00
            file: 2021-09-22_21-30-00
            None: 2021-09-22_21-30-00

    Returns:
        str: current time
    """

    if format == "human":
        fm = "%Y-%m-%d %H:%M:%S"
    elif format == "file":
        fm = "%Y-%m-%d_%H-%M-%S"
    elif format is not None:
        fm = format
    else:
        fm = "%Y-%m-%d_%H-%M-%S"

    return time.strftime(fm, time.localtime())


def get_gpu_by_user_input():

    try:
        os.system("gpustat")
    except:
        print("WARNING: Try to install gpustat to check GPU status: pip install gpustat")

    gpu = input("\nSelect GPU [0]: ") or "0"

    assert gpu in ["0", "1", "2", "3", "4", "5", "6", "7"], \
        "Can not run scripts on GPU: {}".format(gpu if gpu else "None")
    print("This scripts will use GPU {}".format(gpu))
    return gpu

import psutil

def convert_bytes(byte_size):
    # 定义不同单位的转化关系
    units = ['B', 'KB', 'MB', 'GB', 'TB']

    # 选择合适的单位
    unit_index = 0
    while byte_size >= 1024 and unit_index < len(units) - 1:
        byte_size /= 1024.0
        unit_index += 1

    # 格式化输出
    return f"{byte_size:.2f} {units[unit_index]}"

def get_disk_space(path='/'):
    disk_usage = psutil.disk_usage(path)
    total_space = convert_bytes(disk_usage.total)  # 总空间
    used_space = convert_bytes(disk_usage.used)    # 已用空间
    free_space = convert_bytes(disk_usage.free)    # 剩余空间

    return total_space, used_space, free_space

def print_disk_space(path='/'):
    total_space, used_space, free_space = get_disk_space(path)
    print(f"Disk space: {used_space} / {total_space} ({free_space} free)")
