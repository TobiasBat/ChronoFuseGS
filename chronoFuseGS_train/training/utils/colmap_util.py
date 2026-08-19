from __future__ import annotations

import os
from typing import NamedTuple

import numpy as np
from plyfile import PlyElement, PlyData

class ColmapImage(NamedTuple):
    IMAGE_ID: int
    QW: float
    QX: float
    QY: float
    QZ: float
    TX: float
    TY: float
    TZ: float
    CAMERA_ID: str
    NAME: str
    original_line: str
    point_line: str

class ColmapCamera(NamedTuple):
    id: int
    model: str
    width: int
    height: int
    params: list[str]

class ColmapPoints3D(NamedTuple):
    POINT3D_ID: int
    X: float
    Y: float
    Z: float
    R: float
    G: float
    B: float
    ERROR: float
    TRACK: list

    def to_str_line(self, dummy_track = None):
        line = str(self.POINT3D_ID) + ' ' + str(self.X) + ' ' + str(self.Y) + ' ' + str(self.Z)
        line += ' ' + str(self.R) + ' ' + str(self.G) + ' ' + str(self.B) + ' ' + str(self.ERROR)
        if dummy_track is not None:
            line += ' ' + str(dummy_track)
        else:
            for t in self.TRACK:
                line += ' ' + str(t)
        line += '\n'
        return line

def read_cameras_txt(camera_txt_file_path) -> dict[str, ColmapCamera]:
    cameras: dict[str, ColmapCamera] = {}
    with open(camera_txt_file_path, "r") as f:
        all_lines = f.readlines()
        header = all_lines[:3]
        lines = all_lines[3:]
        print(lines)
        for line in lines:
            elements = line.split(" ")
            cameras[elements[0]] = ColmapCamera(
                id=int(elements[0]),
                model=elements[1],
                width=int(elements[2]),
                height=int(elements[3]),
                params=elements[4:],
            )
    return cameras


def parse_images_txt(images_src) -> tuple[dict[str, ColmapImage], list[str]]:
    images: dict[str, ColmapImage] = {}

    with open(images_src, "r") as f:
        all_lines = f.readlines()
        header_lines = all_lines[:4]
        lines = all_lines[4:]
        for index, fullLine in enumerate(lines):
            if index % 2 == 0:
                line = fullLine.split(" ")

                images[line[9].strip()] = ColmapImage(
                    IMAGE_ID=int(line[0]),
                    QW=float(line[1]), QX=float(line[2]), QY=float(line[3]), QZ=float(line[4]),
                    TX=float(line[5]), TY=float(line[6]), TZ=float(line[7]),
                    CAMERA_ID=line[8],
                    NAME=line[9],
                    original_line=lines[index],
                    point_line=lines[index + 1]
                )
    return images, header_lines


def read_points3d_txt(points_3d_file_path) -> tuple[list[str], list[ColmapPoints3D]]:
    points: list[ColmapPoints3D] = []
    with open(points_3d_file_path, "r") as f:
        all_lines = f.readlines()
        header_lines = [
            all_lines[0].strip(),
            all_lines[1].strip(),
            all_lines[2].strip()
        ]

        point_lines = all_lines[3:]
        for line_str in point_lines:
            line_str = line_str.strip()
            line = line_str.split(" ")
            points.append(ColmapPoints3D(
                POINT3D_ID=int(line[0]),
                X=float(line[1]), Y=float(line[2]), Z=float(line[3]),
                R=float(line[4]), G=float(line[5]), B=float(line[6]),
                ERROR=float(line[7]),
                TRACK=line[8:],
            ))
    return header_lines, points


def write_points3d_txt(points_3d_file_path, header_lines: list[str], points: list[ColmapPoints3D]) -> None:
    content = ''
    for line_str in header_lines:
        content += line_str
        content += '\n'

    for point in points:
        content += point.to_str_line("1 0")

    # print("Writing content to",points_3d_file_path, "\n", content)
    with open(points_3d_file_path, "w") as f:
        f.write(content)


def convert_to_txt(project_path):
    cmp_convert = ("colmap" + " model_converter"
                   + " --input_path " + os.path.join(project_path, 'data', 'sparse', '0')
                   + " --output_path " + os.path.join(project_path, 'data', 'sparse', '0')
                   + " --output_type TXT"
                   )
    print(cmp_convert)
    os.system(cmp_convert)


def convert_to_binary(project_path):
    cmp_convert = ("colmap" + " model_converter"
                   + " --input_path " + os.path.join(project_path, 'data', 'sparse', '0')
                   + " --output_path " + os.path.join(project_path, 'data', 'sparse', '0')
                   + " --output_type BIN"
                   )
    print(cmp_convert)
    os.system(cmp_convert)


def convert_points3d_txt_to_ply(project_path):
    """
    Manually converting a colmap points3D file to a ply file.
    Because autmatic model converter will not work if the integrety
    of the reconstruction is not valid. (when adding new points)
    :param project_path:
    :return:
    """
    points_3d_file_path = os.path.join(project_path, 'data', 'sparse', '0', 'points3D.txt')

    if not os.path.exists(points_3d_file_path):
        convert_to_txt(project_path)
    header_lines, points = read_points3d_txt(points_3d_file_path)

    xyz = []
    rgb = []
    nxyz = []
    for point in points:
        xyz.append([point.X, point.Y, point.Z])
        rgb.append([point.R, point.G, point.B])
        nxyz.append([0,0,0])

    xyz = np.array(xyz)
    rgb = np.array(rgb)
    nxyz = np.array(nxyz)

    vertex_data = np.empty(len(points), dtype=[
        ('x', 'f4'), ('y', 'f4'), ('z', 'f4'),
        ('nx', 'f4'), ('ny', 'f4'), ('nz', 'f4'),
        ('red', 'f4'), ('green', 'f4'), ('blue', 'f4')
    ])

    vertex_data['x'] = xyz[:, 0]
    vertex_data['y'] = xyz[:, 1]
    vertex_data['z'] = xyz[:, 2]
    vertex_data['nx'] = nxyz[:, 0]
    vertex_data['ny'] = nxyz[:, 1]
    vertex_data['nz'] = nxyz[:, 2]
    vertex_data['red'] = rgb[:, 0]
    vertex_data['green'] = rgb[:, 1]
    vertex_data['blue'] = rgb[:, 2]

    el = PlyElement.describe(vertex_data, 'vertex')
    PlyData([el]).write(os.path.join(project_path, 'data', 'sparse', '0', 'points3D.ply'))

