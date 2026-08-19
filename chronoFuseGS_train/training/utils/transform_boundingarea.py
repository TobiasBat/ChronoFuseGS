import json
import os
import logging
from argparse import ArgumentParser
import shutil

from utils.bounding_area import BoundingArea, read_in as read_in_bounding_area, read_in_file
from utils import colmap_util


def transform_bounding_area(project_path: str, bounding_area: BoundingArea):
    colmap_image_path = os.path.join(project_path, 'data', 'sparse', '0', 'images.txt')
    camera_info_path = os.path.join(project_path, 'data', 'camera_info.json')

    if not os.path.exists(camera_info_path) or not os.path.exists(colmap_image_path):
        print(colmap_image_path, 'or', camera_info_path, "does not exist")
        return

    colmap_images = colmap_util.parse_images_txt(colmap_image_path)[0]
    camera_info = []
    with open(camera_info_path) as f:
        camera_info = json.load(f)

    transformed_bound_area = bounding_area.get_transformed_bound_area(colmap_images, camera_info)
    transformed_bound_area.write(os.path.join(project_path, 'data'))
    return transformed_bound_area


if __name__ == "__main__":
    parser = ArgumentParser("Bounding Area Transformer")
    parser.add_argument("--source", "-s", type=str, required=True)
    parser.add_argument("--bounding_box", "-b", type=str, required=False)

    args = parser.parse_args()
    source = args.source

    if args.bounding_box:
        bounding_area = read_in_file(args.bounding_box, )
    else:
        bounding_area = read_in_bounding_area(os.path.join(source, 'data', 'src-data'))
    bounding_area = transform_bounding_area(source, bounding_area)