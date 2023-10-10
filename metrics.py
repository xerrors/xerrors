import numpy as np
import scipy

# 计算置信区间的函数
def confidence_interval(data, confidence=0.95):
    """计算置信区间

    Args:
        data (list): 数据
        confidence (float, optional): 置信度. Defaults to 0.95.

    Returns:
        mean (float): 均值
        h (float): 置信区间
    """
    a = 1.0 * np.array(data)
    n = len(a)
    mean, std_error = np.mean(a), scipy.stats.sem(a)
    h = std_error * scipy.stats.t.ppf((1 + confidence) / 2., n - 1)
    return mean, h