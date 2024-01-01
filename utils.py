
import os
import time

from xerrors.cprint import green, blue


class Timer:

    def __init__(self, localtime=time.localtime(), format_in=None):
        self.time = localtime
        self.year = localtime.tm_year
        self.mon = localtime.tm_mon
        self.hour = localtime.tm_hour
        self.min = localtime.tm_min
        self.sec = localtime.tm_sec

        # for human reading
        self.month = self.mon
        self.minute = self.min
        self.second = self.sec

        self._format = format_in

    def __str__(self):

        if self._format == "human":
            fm = "%Y-%m-%d %H:%M:%S"
        elif self._format == "file":
            fm = "%Y-%m-%d_%H-%M-%S"
        elif self._format is not None:
            fm = self._format
        else:
            fm = "%Y-%m-%d_%H-%M-%S"

        return time.strftime(fm, self.time)


def cur_time(format=None):
    """Get current time in human or file format.

    Args:
        format (str, optional): 'human' or 'file'. Defaults to None.
            human: 2021-09-22 21:30:00
            file: 2021-09-22_21-30-00
            None: 2021-09-22_21-30-00

    Returns:
        Timer: current time
    """

    return Timer(format_in=format)


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


def confirm_value(key, value):
    """实现一个函数，函数接收一个默认值，让用户输入此次任务的tag，如果直接回车，则返回默认值"""
    if value:
        new_value = input(f"\nPlease confirm {green(key)} (current is: {blue(value)}) >>> ")
        if new_value:
            value = new_value

    assert value, "This value can not be empty!"

    return value


def confirm_bool(key, value):
    new_value = "none"

    while new_value not in ["y", "n", ""]:
        new_value = input(f"\nPlease confirm {green(key)} (current is: {blue(value)}) [y]/n >>> ")

    new_value = True if not new_value or new_value == "y" else False
    return new_value