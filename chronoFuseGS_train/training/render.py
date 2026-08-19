"""
Renders all cameras of a model and copies its ground truth images.
Pre-step for metric.py
"""
import argparse
import json
import os
import shutil

import torchvision
from plyfile import PlyData

from utils.camera import get_cameras
from utils.gaussians import Gaussians
from utils.temporal_activation import ActivationData

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Disaster Renderer")
    parser.add_argument('--source', '-s', type=str, required=True)
    parser.add_argument('--model', '-m', type=str, required=False)
    parser.add_argument('--iteration', '-i', nargs="+", type=int, required=True)
    parser.add_argument('--all_cameras', action='store_true')
    parser.add_argument('--file_extension', type=str, default='.png')
    parser.add_argument('--folder', type=str, default=None)

    args = parser.parse_args()

    if args.model is None:
        model_path = os.path.join(args.source, 'output')
    else:
        model_path = args.model

    for iteration in args.iteration:
        if args.folder is not None:
            model_folder_name = args.folder
        elif iteration == 0:
            model_folder_name = 'initial_0'
        else:
            model_folder_name = 'refined_' + str(iteration)
        ply_folder = os.path.join(model_path, 'point_cloud', model_folder_name)

        print('Rendering ply folder', ply_folder)

        ply_path = os.path.join(ply_folder, 'point_cloud.ply')
        activation_path = os.path.join(ply_folder, 'activation.ply')
        camera_path = os.path.join(ply_folder, 'cameras.json')
        camera_info_path = os.path.join(args.source, 'data', 'camera_info.json')
        image_path = os.path.join(args.source, 'data', 'images')

        if not os.path.exists(camera_info_path):
            print('Camera info path does not exist', camera_info_path)
            continue
        if not os.path.exists(activation_path):
            print('Activation path does not exist', activation_path)
            continue
        if not os.path.exists(ply_path):
            print('Ply path does not exist', ply_path)
            continue
        if not os.path.exists(camera_path):
            print('camera_path does not exist', camera_path)
            continue
        if not os.path.exists(image_path):
            print('Image path does not exist', image_path)
            continue

        with open(camera_path, 'r') as file:
            json_cameras_data = json.load(file)
        with open(camera_info_path, 'r') as file:
            json_cameras_info = json.load(file)
        ply = PlyData.read(ply_path)
        activation = ActivationData(len(ply['vertex'].data), activation_path)
        gaussians = Gaussians(ply, activation)

        if args.all_cameras:
            cameras = get_cameras(json_cameras_data, info=json_cameras_info)
        else:
            cameras = get_cameras(json_cameras_data, info=json_cameras_info, image_type="test")

        out_folder = os.path.join(model_path, 'test', model_folder_name)
        gt_folder = os.path.join(out_folder, 'gt')
        renders_folder = os.path.join(out_folder, 'renders')
        os.makedirs(gt_folder, exist_ok=True)
        os.makedirs(renders_folder, exist_ok=True)

        for gt_camera in cameras:
            p = os.path.join(image_path, gt_camera.img_name + args.file_extension)
            if os.path.exists(p):
                shutil.copy(p, gt_folder)

        for c in cameras:
            render, *_ = gaussians.forward(c)
            render_file_path = os.path.join(renders_folder, c.img_name + args.file_extension)
            torchvision.utils.save_image(render, render_file_path)
        print('Done with rendering', iteration)
