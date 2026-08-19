"""
Utility to handle pre-defined bounding areas in real-world coordinates.
"""

from __future__ import annotations
import json
import os
from typing import NamedTuple

import numpy as np
import pymap3d

from utils.fuse_utils import regit_transformation
from scipy.spatial.transform import Rotation as SciPyRotation
from utils.colmap_util import ColmapImage


class BoundingArea(NamedTuple):
    bounding_area: list[list[float]]
    max_altitude: float
    min_altitude: float
    name: str
    format_description: str
    bounding_area_model: list[list[float]] = None

    def get_transformed_bound_area(self, colmap_images: dict[str, ColmapImage], camera_info: list[dict], use_closest = True) -> BoundingArea:
        """
        Returns a new BoundingArea with a transformed bounding area
        All other parameters are equal
        """
        camera_info_dict = {}
        for info in camera_info:
            camera_info_dict[info['image']] = info
        shared_images = camera_info_dict.keys() & colmap_images.keys()

        info_positons = []
        colmap_positions = []

        for key in shared_images:
            info = camera_info_dict[key]
            colmap = colmap_images[key]
            info_positons.append(np.array(info['ecef'], dtype=np.float64))
            colmap_pos = np.array([colmap.TX, colmap.TY, colmap.TZ], dtype=np.float64)
            quat = np.array([colmap.QW, colmap.QX, colmap.QY, colmap.QZ], dtype=np.float64)
            colmap_rot = SciPyRotation.from_quat(quat, scalar_first=True).as_matrix()
            colmap_pos = (colmap_rot.transpose() @ colmap_pos) * -1
            colmap_positions.append(colmap_pos)

        if use_closest and len(info_positons) > 15:
            # We are just using the closest 5% of coordinates
            # otherwise this gets relative unstable
            num_position_used = round(len(info_positons) * 0.05)
            num_position_used = max(num_position_used, 15)
            print("Searching for bounding area transformation using ", len(shared_images), "images")
            print('Using the best', num_position_used, 'positions')

            distances = np.array([np.linalg.norm(pa - pb) for pa, pb in zip(info_positons, colmap_positions)])
            indices_to_remove = np.argsort(distances)[-len(info_positons) + num_position_used:]
            indices_to_keep = [i for i in range(len(info_positons)) if i not in indices_to_remove]
            info_positons = [info_positons[i] for i in indices_to_keep]
            colmap_positions = [colmap_positions[i] for i in indices_to_keep]

        scale = 1
        info_positions_scaled = [p * scale  for p in info_positons]

        scale, R, translate, transformation_mat = regit_transformation(info_positions_scaled, colmap_positions)
        print(np.array2string(transformation_mat, precision=2))

        ecef_bounding_area = []
        for coord in self.bounding_area:
            ecef_bounding_area.append(
                pymap3d.ecef.geodetic2ecef(coord[0], coord[1], self.min_altitude)
            )

        model_bound_area = []
        for ecef in ecef_bounding_area:
            p = np.array([ecef[0], ecef[1], ecef[2], 1])
            p = transformation_mat @ p
            model_bound_area.append(p[:3].tolist())

        return BoundingArea(
            bounding_area=self.bounding_area,
            max_altitude=self.max_altitude,
            min_altitude=self.min_altitude,
            name=self.name,
            format_description=self.format_description,
            bounding_area_model=model_bound_area,
        )

    def is_inside(self, lat: float, lon: float, alt: float):
        """
        Naive check if lat/lon point is inside bounding area;  Computed in lat/lon values
        :param lat: latitude of the point to be checked
        :param lon: longitude of the point to be checked
        :param alt: absolute altitude
        :return: true in case it is inside bounding area
        """
        x = lat
        y = lon

        # points
        x1 = self.bounding_area[0][0]
        y1 = self.bounding_area[0][1]
        x2 = self.bounding_area[1][0]
        y2 = self.bounding_area[1][1]
        x3 = self.bounding_area[2][0]
        y3 = self.bounding_area[2][1]
        x4 = self.bounding_area[3][0]
        y4 = self.bounding_area[3][1]

        # first triangle v1, v2, v4
        first_triangle = inside_triangle(x, y, x1, y1, x2, y2, x4, y4)
        second_triangle = inside_triangle(x, y, x2, y2, x3, y3, x4, y4)
        height = self.min_altitude <= alt <= self.max_altitude

        return (first_triangle or second_triangle) and height

    def write(self, out_dict):
        with open(os.path.join(out_dict, "bounding_area.json"), "w") as f:
            f.write(json.dumps(self._asdict(), indent=4))


def read_in(src_folder_path: str) -> BoundingArea | None:
    bounding_area_file = os.path.join(src_folder_path, 'bounding_area.json')
    if os.path.exists(bounding_area_file):
        with open(bounding_area_file) as f:
            bounding_area_json = json.load(f)
            return BoundingArea(
                bounding_area=bounding_area_json['bounding_area'],
                max_altitude=bounding_area_json['max_altitude'],
                min_altitude=bounding_area_json['min_altitude'],
                name=bounding_area_json['name'],
                format_description=bounding_area_json['format_description']
            )
    print("bounding_area.json not found\n   ", bounding_area_file)
    return None


def read_in_file(bounding_area_file: str) -> BoundingArea | None:
    if os.path.exists(bounding_area_file):
        with open(bounding_area_file) as f:
            bounding_area_json = json.load(f)
            return BoundingArea(
                bounding_area=bounding_area_json['bounding_area'],
                max_altitude=bounding_area_json['max_altitude'],
                min_altitude=bounding_area_json['min_altitude'],
                name=bounding_area_json['name'],
                format_description=bounding_area_json['format_description']
            )
    print("File not found", bounding_area_file)
    return None


def inside_triangle(x: float, y: float, x1: float, y1: float, x2: float, y2: float, x3: float, y3: float):
    denominator = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
    a = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / denominator
    b = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / denominator
    c = 1 - a - b

    return 0 <= a <= 1 and 0 <= b <= 1 and 0 <= c <= 1
