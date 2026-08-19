"""
Utility to define a time range of a src-video that should be used to export images
"""
from __future__ import annotations
import json
import os
from typing import NamedTuple


class VideoSrcRange(NamedTuple):
    file_name: str
    first_frame: int = -1
    last_frame: int = 10e10


def load_video_src_range(abs_file_path) -> dict[str, VideoSrcRange]:
    if not os.path.exists(abs_file_path):
        return {}
    with open(abs_file_path) as f:
        return {
            r['file_name']: VideoSrcRange(**r)
            for r in json.load(f)
        }
