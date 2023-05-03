
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

    gpu = input("\nSelect GPU >>> ")

    assert gpu and int(gpu) in [0, 1, 2, 3], \
        "Can not run scripts on GPU: {}. Stoped!".format(gpu if gpu else "None")
    print("This scripts will use GPU {}".format(gpu))
    return gpu