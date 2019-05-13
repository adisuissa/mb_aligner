import cv2
import numpy as np
from .fs_access import FSAccess

def read_image_file(fname_url):
    with FSAccess(fname_url, True) as image_f:
        img_buf = image_f.read()
        np_arr = np.frombuffer(img_buf, np.uint8)
        img = cv2.imdecode(np_arr, 0)
    return img
