"""
Creates the initial multi-temporal model from individual timesteps.
Allows incremental merging of a timestep with an already refined multi-temporal model.
"""

import argparse
import json
import logging
import os
import sys
import time
import shutil

import utils.camera as camera_util
from utils.gaussians import Gaussians
from utils.temporal_activation import ActivationData
from plyfile import PlyData, PlyElement
import numpy as np
from scipy.spatial.transform import Rotation as SciPyRotation
from utils.gaussians import get_heighest_point_cloud_folder
import utils.colmap_util as colmap_util
import utils.fuse_utils as fuse_utils


def _read_num_gaussians_per_t(point_cloud_folder, total_count):
    info_path = os.path.join(point_cloud_folder, 'src_gaussian_info.json')
    if os.path.exists(info_path):
        with open(info_path) as f:
            return json.load(f)['num_gaussians_per_t']
    return [total_count]


# Copies the COLMAP model from source_path_1 to model_path
def copy_model(source_path_1, model_path):
    img_src_path = os.path.join(source_path_1, 'data', 'input')
    out_folder_path = os.path.join(model_path, 'data', 'input')
    os.makedirs(out_folder_path ,exist_ok=True)

    images = os.listdir(img_src_path)
    for image in images:
        src_image_path = os.path.join(img_src_path, image)
        out_image_path = os.path.join(out_folder_path, image)
        if not (os.path.exists(out_image_path) and os.path.samefile(src_image_path, out_image_path)):
            shutil.copy(src_image_path, out_folder_path)
        else:
            print('File already copied -> skipped: ', src_image_path)

    distorted_src_path = os.path.join(source_path_1, 'data', 'distorted')
    distorted_out_path = os.path.join(model_path, 'data', 'distorted')
    dist_sparse_out_path = os.path.join(distorted_out_path, 'sparse', '0')
    os.makedirs(dist_sparse_out_path, exist_ok=True)

    shutil.copy(os.path.join(distorted_src_path, 'database.db'), distorted_out_path)
    dist_sparse_src_path = os.path.join(source_path_1, 'data', 'distorted', 'sparse', '0')
    dist_sparse = os.listdir(dist_sparse_src_path)
    for dist_sparse_file in dist_sparse:
       shutil.copy(os.path.join(dist_sparse_src_path, dist_sparse_file), dist_sparse_out_path)


def get_shared_images(img_info_1, img_info_2):
    shared_images = []
    shared_keys = []
    keys_1 = list(img_info_1.keys())
    keys_2 = list(img_info_2.keys())

    for key in keys_1:
       if key in keys_2:
           shared_keys.append(key)
    for key in shared_keys:
        shared_images.append([img_info_1[key], img_info_2[key]])
    return shared_images


def transformation_between_shared_images(shared_images_info):
    print('Shared Images', len(shared_images_info))
    a_list = [] # should be transformed to b; b = tm @ a
    b_list = [] # ground truth
    for index, image in enumerate(shared_images_info):
        # camera coordinate transformation
        # https://github.com/colmap/colmap/issues/1376
        t_a = np.array([image[1].TX, image[1].TY, image[1].TZ], dtype=np.float64)
        t_b = np.array([image[0].TX, image[0].TY, image[0].TZ], dtype=np.float64)
        q_a = np.array([image[1].QW, image[1].QX, image[1].QY, image[1].QZ], dtype=np.float64)
        q_b = np.array([image[0].QW, image[0].QX, image[0].QY, image[0].QZ], dtype=np.float64)
        r_a = SciPyRotation.from_quat(q_a, scalar_first=True).as_matrix()
        r_b = SciPyRotation.from_quat(q_b, scalar_first=True).as_matrix()
        a_world_pos = (r_a.transpose() @ t_a) * -1
        b_world_pos = (r_b.transpose() @ t_b) * -1
        a_list.append(a_world_pos)
        b_list.append(b_world_pos)
    a = np.array(a_list)
    b = np.array(b_list)
    return fuse_utils.regit_transformation(a, b)


def init_new_images_to_colmap_model(source_path_1, source_paths_2, model_path, multiple_cameras, fix_existing_images=False):
    merged_images = ''
    for src_2 in source_paths_2:
        second_images = os.listdir(os.path.join(src_2, 'data', 'input'))

        for second_image in second_images:
            merged_images += second_image + '\n'
            shutil.copy(os.path.join(src_2, 'data', 'input', second_image),
                        os.path.join(model_path, 'data', 'input'))
    print('Added Images: ' + merged_images)
    with open(os.path.join(model_path, 'data', 'merged_images.txt'), "w") as f:
        f.write(merged_images)

    colmap_command = "colmap"
    data_cmd = "cd " + os.path.join(model_path, 'data')
    # feature match of new images
    feature_extractor_cmd = (
            colmap_command + " feature_extractor"
            + " --database_path distorted/database.db"
            + " --image_path input"
            + " --image_list_path merged_images.txt"
            + " --ImageReader.camera_model OPENCV"
            + " --SiftExtraction.use_gpu 1"
    )
    if multiple_cameras:
        feature_extractor_cmd += " --ImageReader.single_camera 0"
    else:
        feature_extractor_cmd += " --ImageReader.single_camera 1"

    print('Feature extraction', feature_extractor_cmd)
    exit_code = os.system(data_cmd + " && " + feature_extractor_cmd)
    if exit_code != 0:
        logging.error(f"Feature extractor command failed with exit code {exit_code}")
        exit(exit_code)

    # match to existing images in database
    matcher_cmd = (
            colmap_command + " vocab_tree_matcher"
            + " --database_path distorted/database.db"
            + " --SiftMatching.use_gpu 1"
            + " --VocabTreeMatching.match_list_path  merged_images.txt"
    )
    print('Vocab matching', matcher_cmd)
    exit_code = os.system(data_cmd + " && " + matcher_cmd)
    if exit_code != 0:
        logging.error(f"Matcher command failed with exit code {exit_code}")
        exit(exit_code)
    # Bundle adjustment
    mapper_cmd = (
            colmap_command + " mapper"
            + " --database_path distorted/database.db"
            + " --input_path distorted/sparse/0"
            + " --image_path input"
            + " --output_path distorted/sparse/0"
            + " --Mapper.ba_global_function_tolerance=0.000001"
            + " --Mapper.ba_use_gpu 1"
    )
    if fix_existing_images:
        mapper_cmd += " --Mapper.fix_existing_frames 1"

    print('mapper cmd', mapper_cmd)
    exit_code = os.system(data_cmd + " && " + mapper_cmd)
    if exit_code != 0:
        logging.error(f"Mapper failed with code {exit_code}. Exiting.")
        exit(exit_code)

    # Image undistortion
    img_undist_cmd = (
            colmap_command + " image_undistorter"
            + " --image_path input"
            + " --input_path distorted/sparse/0"
            + " --output_path ./"
            + " --output_type COLMAP"
    )
    exit_code = os.system(data_cmd + " && " + img_undist_cmd)
    if exit_code != 0:
        logging.error(f"Image undistorter failed with code {exit_code}. Exiting.")
        exit(exit_code)

    images_src_1 = os.listdir(os.path.join(source_path_1, 'data', 'images'))
    images_folder = os.path.join(model_path, 'data', 'images')

    for image in images_src_1:
        if not os.path.exists(os.path.join(images_folder, image)):
            shutil.copy(os.path.join(source_path_1, 'data', 'images', image), images_folder)

    for src_2 in source_paths_2:
        images_src_2 = os.listdir(os.path.join(src_2, 'data', 'images'))
        for image in images_src_2:
            if not os.path.exists(os.path.join(images_folder, image)):
                shutil.copy(os.path.join(src_2, 'data', 'images', image), images_folder)

    files = os.listdir(os.path.join(model_path, 'data', 'sparse'))
    os.makedirs(os.path.join(model_path, 'data', 'sparse', '0'), exist_ok=True)

    # Copy each file from the source directory to the destination directory
    for file in files:
        if file == '0':
            continue
        source_file = os.path.join(model_path, 'data', 'sparse', file)
        destination_file = os.path.join(model_path, 'data', 'sparse', '0', file)
        shutil.move(source_file, destination_file)

    model_convert_cmd = colmap_command + " model_converter" \
                        + " --input_path " + os.path.join(model_path, "data", "sparse", "0") \
                        + " --output_path " + os.path.join(model_path, "data", "sparse", '0') \
                        + " --output_type TXT"
    os.system(model_convert_cmd)


def combine_activation(point_cloud_src_1, point_cloud_srcs_2, num_gaussians_1, nums_gaussians_2, point_cloud_out_folder) -> list[int]:
    src_1_act = ActivationData(num_gaussians_1, os.path.join(point_cloud_src_1, 'activation.ply'))
    srcs_2_act = []
    num_ts = [src_1_act.num_t]
    for index, src_2 in enumerate(point_cloud_srcs_2):
        src_2_act = ActivationData(nums_gaussians_2[index], os.path.join(src_2, 'activation.ply'))
        srcs_2_act.append(src_2_act)
        num_ts.append(src_2_act.num_t)
    src_act = [src_1_act] + srcs_2_act
    print(src_act, len(src_act), len( srcs_2_act))
    combined_act = ActivationData.combine_multiple(src_act)
    print(combined_act)
    combined_act.write(point_cloud_out_folder)

    return num_ts


def combine_ply_data(plydata_1, plydatas_2, src_path_1: str, src_paths_2: list[str], model_path, point_cloud_out_folder):
    # extract the old and merged rotations and scales
    src_1_images, _ = colmap_util.parse_images_txt(
        os.path.join(src_path_1, 'data', 'sparse', '0', 'images.txt'))
    merged_images, _ = colmap_util.parse_images_txt(
        os.path.join(model_path, 'data', 'sparse', '0', 'images.txt'))

    # compute transformation matrices based on shared images
    shared_img_1 = get_shared_images(merged_images, src_1_images)
    print("Shared Images for 1: ", len(shared_img_1))
    scale_1, rot_mat_1, _, trans_mat_1 = transformation_between_shared_images(shared_img_1)
    quat_inv_1 = SciPyRotation.from_matrix(rot_mat_1[:3, :3]).as_quat(scalar_first=True)
    quat_inv_1 = np.array([
        quat_inv_1[0],
        -quat_inv_1[1],
        -quat_inv_1[2],
        -quat_inv_1[3]
    ])

    scales_2 = []
    trans_mats_2 = []
    quats_inv_2 = []
    for src_2 in src_paths_2:
        src_2_images, _ = colmap_util.parse_images_txt(
            os.path.join(src_2, 'data', 'sparse', '0', 'images.txt'))

        shared_img_2 = get_shared_images(merged_images, src_2_images)
        print("Shared Images for 2: ", len(shared_img_2))
        scale_2, rot_mat_2, _, trans_mat_2 = transformation_between_shared_images(shared_img_2)
        quat_inv_2 = SciPyRotation.from_matrix(rot_mat_2[:3, :3]).as_quat(scalar_first=True)
        quat_inv_2 = np.array([
            quat_inv_2[0],
            -quat_inv_2[1],
            -quat_inv_2[2],
            -quat_inv_2[3]
        ])
        scales_2.append(scale_2)
        trans_mats_2.append(trans_mat_2)
        quats_inv_2.append(quat_inv_2)

    print('Transforming ply data ...')
    arrays = [Gaussians.transform_ply_vertex_data(plydata_1['vertex'].data, trans_mat_1, scale_1, quat_inv_1)]
    for index, plydata_2 in enumerate(plydatas_2):
        arrays.append(Gaussians.transform_ply_vertex_data(
            plydata_2['vertex'].data, trans_mats_2[index], scales_2[index], quats_inv_2[index]
        ))

    vertex = np.concatenate(arrays)
    vertex_elements = PlyElement.describe(vertex, 'vertex')
    out_points_path = os.path.join(point_cloud_out_folder, 'point_cloud.ply')
    out_points_path_tmp = out_points_path + '.tmp'

    print('Writing ply data to', out_points_path)
    PlyData([vertex_elements]).write(out_points_path_tmp)
    shutil.move(out_points_path_tmp, out_points_path)

    return trans_mat_1, trans_mats_2


def merge(source_path_1, source_paths_2, model_path, merge_iteration, multiple_cameras, consider_pup_1=False, consider_pup_2=False, fix_existing_images=False):
    # First load old ply data
    src_1_output = 'output'
    src_2_outputs = []
    if consider_pup_1 and os.path.exists(os.path.join(source_path_1, 'pup')):
        src_1_output = 'pup'
    for src_2 in source_paths_2:
        if consider_pup_2 and os.path.exists(os.path.join(src_2, 'pup')):
            src_2_outputs.append('pup')
        else:
            src_2_outputs.append('output')

    point_cloud_src_1 = get_heighest_point_cloud_folder(source_path_1, output_folder=src_1_output)
    point_cloud_srcs_2 = []
    for index, src_2 in enumerate(source_paths_2):
        point_cloud_srcs_2.append(get_heighest_point_cloud_folder(src_2, output_folder=src_2_outputs[index]))
    print('For src 1 using point cloud folder', point_cloud_src_1)
    print('For src 2 using point cloud folder', point_cloud_srcs_2)

    # Create the new out folder
    point_cloud_out_folder = os.path.join(model_path, 'output', 'point_cloud', 'initial_' + str(merge_iteration))
    os.makedirs(point_cloud_out_folder, exist_ok=True)

    if not os.path.samefile(source_path_1, model_path):
        copy_model(source_path_1, model_path)
    init_new_images_to_colmap_model(source_path_1, source_paths_2, model_path, multiple_cameras, fix_existing_images=fix_existing_images)

    plydata_1 = PlyData.read(os.path.join(point_cloud_src_1, 'point_cloud.ply'))
    plydatas_2 = []
    for pc_src_2 in point_cloud_srcs_2:
        plydatas_2.append(
            PlyData.read(os.path.join(pc_src_2, 'point_cloud.ply'))
        )
    num_gaussians_1 = len(plydata_1['vertex'].data)
    nums_gaussians_2 = []
    for ply_2 in plydatas_2:
        nums_gaussians_2.append(len(ply_2['vertex'].data))

    nums_per_t_1 = _read_num_gaussians_per_t(point_cloud_src_1, num_gaussians_1)
    nums_per_t_2 = []
    for i, pc_src_2 in enumerate(point_cloud_srcs_2):
        nums_per_t_2.extend(_read_num_gaussians_per_t(pc_src_2, nums_gaussians_2[i]))

    trans_mat_1, trans_mats_2 = combine_ply_data(plydata_1, plydatas_2, source_path_1, source_paths_2, model_path, point_cloud_out_folder)
    num_ts = combine_activation(point_cloud_src_1, point_cloud_srcs_2, num_gaussians_1, nums_gaussians_2, point_cloud_out_folder)
    trans_mat = [trans_mat_1] + trans_mats_2

    num_ts_start = []
    next_start = 0
    for num_t_i in num_ts:
        num_ts_start.append(next_start)
        next_start = next_start + num_t_i


    # transform and combine cameras
    # Ensure that all cameras from all Gaussian sets are part of the combined cameras
    point_cloud_srcs = [point_cloud_src_1] + point_cloud_srcs_2
    json_cameras = []
    for index, pc_src in enumerate(point_cloud_srcs):
        camera_path = os.path.join(pc_src, 'cameras.json')
        if not os.path.exists(camera_path):
            camera_path = os.path.join(os.path.dirname(os.path.dirname(pc_src)), 'cameras.json')
        if not os.path.exists(camera_path):
            print('Could not find cameras.json for src 1')

        print('Path to src camera json', camera_path)
        registered_cameras_i = camera_util.manipulate_check_json_cameras(camera_path, model_path, trans_mat[index], num_ts_start[index])
        json_cameras = json_cameras + registered_cameras_i

    print('Writing camera data ...')
    with open(os.path.join(point_cloud_out_folder, 'cameras.json'), 'w') as f:
        f.write(json.dumps(json_cameras, indent=4))

    # Camera info
    src_paths = [source_path_1] + source_paths_2
    camera_info = []
    for index, src_path in enumerate(src_paths):
        camera_info_path = os.path.join(src_path, 'data', 'camera_info.json')
        with open(camera_info_path) as f:
            camera_info_i = json.load(f)

        for camera in camera_info_i:
            if 't' in camera:
                camera['t'] = camera['t'] + num_ts_start[index]
            else:
                camera['t'] = num_ts_start[index]
        camera_info = camera_info + camera_info_i

    # Updating if the camera in camera_info has an image in the image Folder
    # can also be true if there is an image but the image is not registered
    # in the combined model
    for camera in camera_info:
        image_path = os.path.join(model_path, 'data', 'images', camera["image"])
        if os.path.exists(image_path):
            camera["registered"] = True
        else:
            camera["registered"] = False

    with open(os.path.join(model_path, 'data', 'camera_info.json'), 'w') as f:
        f.write(json.dumps(camera_info, indent=4))

    return nums_per_t_1, nums_per_t_2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Merging to Multi-Temporal Model")
    parser.add_argument("--sources", "-s", nargs="+", type=str, required=True)
    parser.add_argument("--merged_model", "-m", type=str, required=True)
    parser.add_argument("--pup", action='store_true', help='Use the pruned model from the pup folder instead of the output folder. Falls back to output if pup folder is not present.')
    parser.add_argument('--multiple_cameras', action='store_true')
    parser.add_argument('--fix_existing_images', action='store_true', help='Pass --Mapper.fix_existing_images 1 to COLMAP mapper (requires COLMAP >= 3.9). Fixes poses of already-registered images during bundle adjustment, only optimizing newly added ones.')

    args = parser.parse_args(sys.argv[1:])

    sources = args.sources
    time_start = time.time()
    stats_logs = vars(args) | {'time_start': time_start}
    os.makedirs(args.merged_model, exist_ok=True)

    if len(sources) < 2:
        raise Exception("At least two source models are needed")

    print("Considering Pup", args.pup)

    num_g_1, num_g_2 = merge(sources[0], sources[1:], args.merged_model, 0, args.multiple_cameras,
                                 consider_pup_1=args.pup, consider_pup_2=args.pup, fix_existing_images=args.fix_existing_images)

    time_end = time.time()
    out_pc_folder = os.path.join(args.merged_model, 'output', 'point_cloud', 'initial_0')

    with open(os.path.join(out_pc_folder, 'src_gaussian_info.json'), 'w') as f:
        f.write(json.dumps({
            "num_gaussians_per_t": num_g_1 + num_g_2,
            "pup": args.pup,
            "sources": sources,
            "time_elapsed": time_end - time_start,
        }, indent=4))

    stats_logs['num_gaussians_per_t'] = num_g_1 + num_g_2
    stats_logs['time_end'] = time_end
    stats_logs['time_elapsed'] = time_end - time_start
    stats_logs['time_elapsed_minutes'] = (time_end - time_start) / 60

    with open(os.path.join(out_pc_folder, 'stats.json'), 'w') as f:
        f.write(json.dumps(stats_logs, indent=4))

