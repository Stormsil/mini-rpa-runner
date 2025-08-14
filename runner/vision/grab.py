# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Tuple
import numpy as np
import mss


# bbox: (left, top, width, height)
def grab_bgr(bbox: Tuple[int, int, int, int]) -> np.ndarray:
    left, top, width, height = bbox
    region = {
        "left": int(left),
        "top": int(top),
        "width": int(width),
        "height": int(height),
    }
    with mss.mss() as sct:
        shot = sct.grab(region)  # BGRA
        arr = np.array(shot, dtype=np.uint8)
        return arr[:, :, :3]  # BGR
