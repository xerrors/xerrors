import os
import unicodedata
import string

import numpy as np
from matplotlib import pyplot as plt

def check_data(data, dims=2):
    '''Check whether the data is a 2D array.

    Args:
        data: Data to check.
        dims: Number of dimensions.

    Returns:
        None
    '''
    # 判断是否是 cuda 的数据
    if hasattr(data, 'device') and data.device != 'cpu':
        data = data.cpu()

    # 判断 data 是否为 2D array，如果是 pytorch 的 tensor，需要转换为 numpy array
    if hasattr(data, "numpy"):
        data = data.numpy()

    if len(data.shape) != dims:
        raise ValueError("data should be {}D array".format(dims))

    return data

def plot_matrix(data, title=None, path=None, show=False, dpi=900):
    '''Plot matrix as heatmap.

    Args:
        data: 2D array.
        title: Title of the plot.
        path: Path to save the plot.
        show: Whether to show the plot.
        dpi: Dots per inch.

    Returns:
        None
    '''

    data = check_data(data, dims=2)

    fig, ax = plt.subplots()
    im = ax.matshow(data, cmap="YlGnBu")

    # Loop over data dimensions and create text annotations.
    # if the data is too large, do not show the text
    if data.shape[0] < 16 and data.shape[1] < 16:

        # We want to show all ticks...
        ax.set_xticks(np.arange(len(data[0])))
        ax.set_yticks(np.arange(len(data)))
        # ... and label them with the respective list entries

        ax.set_xticklabels(np.arange(len(data[0])))
        ax.set_yticklabels(np.arange(len(data)))

        for i in range(len(data)):
            for j in range(len(data[0])):
                text = ax.text(j, i, "{:.2f}".format(data[i, j]), ha="center", va="center", color="black")

    if title:
        ax.set_title(title)
        path = os.path.join("debug", clean_filename(title) + ".png")

    if path is None:
        os.makedirs("debug", exist_ok=True)
        path = os.path.join("debug", "plot_matrix.png")

    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    print("Save plot to {}".format(path))

    if show:
        plt.show()


def clean_filename(filename, replace=" ", char_limit=255):
    # replace spaces
    for r in replace:
        filename = filename.replace(r, "_")

    # keep only valid ascii chars
    cleaned_filename = (unicodedata.normalize("NFKD", filename).encode("ASCII", "ignore").decode())

    # keep only whitelisted chars
    whitelist = "-_.() %s%s" % (string.ascii_letters, string.digits)
    cleaned_filename = "".join(c for c in cleaned_filename if c in whitelist)
    return cleaned_filename[:char_limit]


from .cprint import error
def log(condition, msg):
    if condition:
        error("DEBUG", msg)