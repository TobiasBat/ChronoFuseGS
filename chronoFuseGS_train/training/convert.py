"""
Converts source Videos / Images to a COLMAP model that servers as input for the following stages.
Parses mp4 and DJI logs files to extract the estimated gps camera positions.
"""

import json
import os
import logging
import time
from argparse import ArgumentParser
import shutil

import cv2
import pymap3d

from utils.bounding_area import BoundingArea, read_in as read_in_bounding_area
from utils.video_src_range import load_video_src_range
import utils.colmap_util as colmap_util



def parse_videos(project_path , out_fps = 0.25, out_size = [1600, 900], bounding_area = None, remove_outside_cameras = True, parse_without_srt = False, blur_threshold = 800):
    os.makedirs(os.path.join(project_path, 'data', 'input'), exist_ok=True)
    src_path = os.path.join(project_path, 'data', 'src-data')
    all_src_files = os.listdir(src_path)

    src_files = []
    for file in all_src_files:
        if file.endswith(".MP4"):
            srt = file[:-3] + 'SRT'
            if srt in all_src_files:
                src_files.append({
                    'video': file,
                    'srt': srt
                })
            elif parse_without_srt:
                print('Could not find log file for', file, '- parsing video without location data')
                src_files.append({
                    'video': file,
                    'srt': None
                })
            else:
                print('Could not find log file: ', srt, '\nignoring mp4')

    video_range_src = os.path.join(src_path, 'video_src_range.json')
    video_ranges = load_video_src_range(video_range_src)

    if bounding_area is not None:
        print('Using Bounding area:', bounding_area.name, 'with coords', bounding_area.bounding_area)

    camera_info = []
    for file in src_files:
        print('Converting Video to frame: ', file['video'])
        if file['srt'] is None:
            c_i = convert_frames_from_dji(project_path, file['video'], None, out_fps=out_fps, out_size=out_size, blur_threshold=blur_threshold)
        else:
            first_frame = 0
            last_frame = 10e10
            print(file['video'], video_ranges)
            if file['video'] in video_ranges:
                first_frame = video_ranges[file['video']].first_frame
                last_frame = video_ranges[file['video']].last_frame
            c_i = convert_frames_from_dji(project_path, file['video'], file['srt'], out_fps=out_fps, bounding_area=bounding_area, out_size=out_size, first_frame=first_frame, last_frame=last_frame, remove_outside_cameras=remove_outside_cameras, blur_threshold=blur_threshold)
        camera_info = camera_info + c_i
        print('Created cameras: ', len(c_i))

    print('Total number of created cameras:', len(camera_info))
    return  camera_info

def parse_exr(project_path):
    out_folder = os.path.join(project_path, 'data', 'input')
    os.makedirs(out_folder, exist_ok=True)
    src_path = os.path.join(project_path, 'data', 'src-data')
    all_src_files = os.listdir(src_path)

    src_files = []
    for file in all_src_files:
        if file.endswith(".exr"):
            convert_cmd = (
                    "magick"
                    + " " + os.path.join(src_path, file)
                   + " -set colorspace RGB -colorspace sRGB"
                    + " " + os.path.join(out_folder, file + ".png")
            )
            exit_code = os.system(convert_cmd)
            if exit_code != 0:
                print('Could not convert file: ', file)
            else:
                print('Converted', file)
                src_files.append(file)
    camera_info = []
    for src_file in src_files:
        camera_info.append({
            "image":  src_file + ".png",
            'src_img': src_file,
        })
    return camera_info

def parse_jpg(project_path, out_width=1600):
    print('Converting JPG files in:', project_path)
    out_folder = os.path.join(project_path, 'data', 'input')
    os.makedirs(out_folder, exist_ok=True)
    src_path = os.path.join(project_path, 'data', 'src-data')
    all_src_files = os.listdir(src_path)

    src_files = []
    for file in all_src_files:
        if file.endswith(".JPG") or file.endswith(".jpeg"):
            out_filename = os.path.splitext(file)[0] + ".png"
            convert_cmd = (
                    "ffmpeg -y"
                    + " -i " + os.path.join(src_path, file)
                    + " -vf scale=" + str(out_width) + ":-1"
                    + " " + os.path.join(out_folder, out_filename)
            )
            exit_code = os.system(convert_cmd)
            if exit_code != 0:
                print('Could not convert file: ', file)
            else:
                print('Converted', file)
                src_files.append(file)
    camera_info = []
    for src_file in src_files:
        out_filename = os.path.splitext(src_file)[0] + ".png"
        camera_info.append({
            "image": out_filename,
            'src_img': src_file,
        })
    return camera_info

def create_initial_camera_info(project_path):
    if os.path.exists(os.path.join(project_path, 'data', 'camera_info.json')):
        print("Camera info already exists, skipping. No new camera info is created.")
        return []
    out_folder = os.path.join(project_path, 'data', 'input')
    os.makedirs(out_folder, exist_ok=True)
    input_path = os.path.join(project_path, 'data', 'input')
    all_src_files = os.listdir(input_path)

    camera_info = []
    src_files = []
    for file in all_src_files:
        if file.endswith(".png"):
                src_files.append(file)

    for src_file in src_files:
        camera_info.append({
            "image":  src_file,
            'src_img': src_file,
        })
    return camera_info

def convert_frames_from_dji(src, video_src, srt_src, src_fps = 29.97, out_fps = 0.25, out_size = [1600, 900], bounding_area = None, first_frame = 0, last_frame = 10e10, remove_outside_cameras=True, blur_threshold=800):
    """
    converts a dji recording and using a corresponding .SRT log file

    :param src: the folder to the project
    :param video_src: file path to video that will be converted
    :param srt_src: to the SRT log file that dji produces
    :param src_fps: fps of the video src
    :param out_fps: output fps; the higher the number the more images are created
    :param out_size: [width, height] of created images
    :param bounding_area:
    :return: list camera_info
    """

    if srt_src is None:
        return convert_frames_without_srt(src, video_src, out_fps=out_fps, out_size=out_size, blur_threshold=blur_threshold)

    src_path = os.path.join(src, 'data', 'src-data', srt_src)
    video_path = os.path.join(src, 'data', 'src-data', video_src)
    video_src_without_appendix = video_src.rsplit('.', 1)[0]

    srt_file = open(str(src_path), "r")
    srt_contents = srt_file.read()
    srt_file.close()

    srt_lines = srt_contents.split("\n\n")
    camera_info = []
    extracted_frame_count = 1
    non_valid_image_names = []

    for frameInfo in srt_lines:
        lines = frameInfo.split("\n")
        if len(lines) == 5:
            input_frame = int(lines[0])
            props = lines[4].replace(" ", " ").replace("[", '').replace("</font>", '').split(']')
            props = props[:-1]

            k = input_frame % (src_fps / out_fps)
            if ((src_fps / out_fps) * 0.5 - 0.5) < k < ((src_fps / out_fps) * 0.5 + 0.5):
                lat = float(props[6].replace(' latitude: ', ''))
                lon = float(props[7].replace(' longitude: ', ''))
                rel_alt = float(props[8].replace(' rel_alt: ', '').split(' ')[0])
                abs_alt = float(props[8].split(' ')[-1])
                ecef = pymap3d.ecef.geodetic2ecef(lat, lon, abs_alt)

                inside_bounding_area = True
                if bounding_area is not None and remove_outside_cameras:
                    inside_bounding_area = bounding_area.is_inside(lat, lon, abs_alt)

                if inside_bounding_area and first_frame <= input_frame <= last_frame:
                    info = {
                        'image': video_src_without_appendix + '_' + str(extracted_frame_count) + '.png',
                        'video_frame': input_frame,
                        'src_video': video_src,
                        'latitude': lat,
                        'longitude': lon,
                        'rel_alt': rel_alt,
                        'abs_alt': abs_alt,
                        'ecef': [ecef[0], ecef[1], ecef[2]],
                    }
                    camera_info.append(info)
                else:
                    non_valid_image_names.append(video_src_without_appendix + '_' + str(extracted_frame_count) + '.png')
                extracted_frame_count += 1
        else:
            print("Srt file seams to have an problem", extracted_frame_count, lines)

    print('number of Frames used: ', len(camera_info), 'of', extracted_frame_count - 1)

    frame_out_name = os.path.join(src, 'data', 'input', video_src_without_appendix + '_%d.png')
    export_command = (
            'ffmpeg -i ' + video_path
            + ' -vf fps=' + str(out_fps)
            + ' -s ' + str(int(out_size[0]))
            + 'x' + str(int(out_size[1]))
            + ' -q:v 1 ' + frame_out_name
    )
    os.system(export_command)

    # remove images again that are not inside bounding area.
    invalid_image_folder = os.path.join(src, 'data', 'invalid')
    os.makedirs(invalid_image_folder, exist_ok=True)

    input_path = os.path.join(src, 'data', 'input')
    for img in non_valid_image_names:
        img_path = os.path.join(input_path, img)
        if os.path.exists(img_path):
            shutil.move(img_path, invalid_image_folder)
            print('moved file', img_path)
        else:
            print('failed to move file', img_path)

    # Removing blurry images and images that are not in frame range
    sharp_camera_info = []
    images_paths_to_be_removed = []
    for camera in camera_info:
        img_path = os.path.join(src, 'data', 'input', camera['image'])
        if not image_blurry(img_path, threshold=blur_threshold):
            print("Adding image", camera['video_frame'])
            sharp_camera_info.append(camera)
        else:
            print('Image is not sharp', camera['image'])
            images_paths_to_be_removed.append(img_path)

    blurry_image_dir = os.path.join(invalid_image_folder, 'blurry')
    os.makedirs(blurry_image_dir, exist_ok=True)
    for img_path in images_paths_to_be_removed:
        if os.path.exists(img_path):
            shutil.move(img_path, blurry_image_dir)
        else:
            print('File to be removed does not exist', img_path)

    return sharp_camera_info


def convert_frames_without_srt(src, video_src, out_fps=0.25, out_size=[1600, 900], blur_threshold=800):
    """
    Extracts frames from a video that has no corresponding .SRT log file.
    Since there is no location data, the resulting camera_info entries have
    no latitude/longitude/altitude/ecef fields, and no bounding area or
    frame range filtering is applied.

    :return: list camera_info
    """
    video_path = os.path.join(src, 'data', 'src-data', video_src)
    video_src_without_appendix = video_src.rsplit('.', 1)[0]

    frame_out_name = os.path.join(src, 'data', 'input', video_src_without_appendix + '_%d.png')
    export_command = (
            'ffmpeg -i ' + video_path
            + ' -vf fps=' + str(out_fps)
            + ' -s ' + str(int(out_size[0]))
            + 'x' + str(int(out_size[1]))
            + ' -q:v 1 ' + frame_out_name
    )
    os.system(export_command)

    input_path = os.path.join(src, 'data', 'input')
    extracted_images = sorted(
        f for f in os.listdir(input_path)
        if f.startswith(video_src_without_appendix + '_') and f.endswith('.png')
    )

    camera_info = [{'image': img, 'src_video': video_src} for img in extracted_images]

    # Removing blurry images
    invalid_image_folder = os.path.join(src, 'data', 'invalid')
    blurry_image_dir = os.path.join(invalid_image_folder, 'blurry')
    os.makedirs(blurry_image_dir, exist_ok=True)

    sharp_camera_info = []
    for camera in camera_info:
        img_path = os.path.join(input_path, camera['image'])
        if not image_blurry(img_path, threshold=blur_threshold):
            print("Adding image", camera['image'])
            sharp_camera_info.append(camera)
        else:
            print('Image is not sharp', camera['image'])
            shutil.move(img_path, blurry_image_dir)

    return sharp_camera_info


def matching(data_path, multiple_cameras: bool):
    print("Multiple Cameras", multiple_cameras)
    os.makedirs(os.path.join(data_path, "distorted", "sparse"), exist_ok=True)

    colmap_command = "colmap"
    use_gpu = True
    camera = 'OPENCV'
    data_path_cmd = "cd " + data_path

    ## Feature extraction
    feat_extract_cmd = (
            colmap_command + " feature_extractor"
            + " --database_path distorted/database.db"
            + " --image_path input"
            + " --ImageReader.camera_model " + camera
            + " --SiftExtraction.use_gpu " + str(use_gpu)
    )

    if multiple_cameras:
        feat_extract_cmd += " --ImageReader.single_camera 0"
    else:
        feat_extract_cmd += " --ImageReader.single_camera 1"

    exit_code = os.system(data_path_cmd + " && " + feat_extract_cmd)
    if exit_code != 0:
        logging.error(f"Feature extraction failed with code {exit_code}. Exiting.")
        exit(exit_code)

    ## Feature matching
    feat_matching_cmd = (
            colmap_command + " exhaustive_matcher"
            + " --database_path distorted/database.db"
            + " --SiftMatching.use_gpu " + str(use_gpu)
    )
    exit_code = os.system(data_path_cmd + " && " + feat_matching_cmd)
    if exit_code != 0:
        logging.error(f"Feature matching failed with code {exit_code}. Exiting.")
        exit(exit_code)

    ### Bundle adjustment
    mapper_cmd = (
            colmap_command + " mapper"
            + " --database_path distorted/database.db"
            + " --image_path input"
            + " --output_path distorted/sparse"
            + " --Mapper.ba_global_function_tolerance=0.000001" #only synthetic so fare
    )
    exit_code = os.system(data_path_cmd + " && " + mapper_cmd)
    if exit_code != 0:
        logging.error(f"Mapper failed with code {exit_code}. Exiting.")
        exit(exit_code)

    auto_align_cmd = (
        colmap_command + " model_orientation_aligner"
        + " --image_path input"
        + " --input_path distorted/sparse/0"
        + " --output_path distorted/sparse/0"
    )

    exit_code = os.system(data_path_cmd + " && " + auto_align_cmd)
    if exit_code != 0:
        logging.error(f"Auto aligning failed with code {exit_code}. Exiting.")
        exit(exit_code)

    # Image undistortion
    img_undist_cmd = (
            colmap_command + " image_undistorter"
            + " --image_path input"
            + " --input_path distorted/sparse/0"
            + " --output_path ./"
            + " --output_type COLMAP"
    )
    exit_code = os.system(data_path_cmd + " && " + img_undist_cmd)
    if exit_code != 0:
        logging.error(f"Mapper failed with code {exit_code}. Exiting.")
        exit(exit_code)

    files = os.listdir(data_path + "/sparse")
    os.makedirs(data_path + "/sparse/0", exist_ok=True)
    # Copy each file from the source directory to the destination directory
    for file in files:
        if file == '0':
            continue
        source_file = os.path.join(data_path, "sparse", file)
        destination_file = os.path.join(data_path, "sparse", "0", file)
        shutil.move(source_file, destination_file)


def update_camera_info(project_dir):
    """
    Updates camera_info_json to include if a camera is registered in model.
    In case data/camera_json does not exist, it will be created.
    :param project_dir: path of the whole project
    """
    data_dir = os.path.join(project_dir, "data")
    images_dir = os.path.join(project_dir, "data", "images")
    camera_info_path = os.path.join(data_dir, "camera_info.json")

    camera_info = []
    if os.path.exists(camera_info_path):
        with open(camera_info_path) as f:
            camera_info = json.load(f)

        camera_images_names = []

        for camera in camera_info:
            image_path = os.path.join(images_dir, camera["image"])
            if os.path.exists(image_path):
                camera["registered"] = True
                camera_images_names.append(camera["image"])
            else:
                camera["registered"] = False

        # llffhold
        llffhold = 8
        camera_images_names.sort()

        test_image_names = []
        train_image_names = []
        for idx, image_name in enumerate(camera_images_names):
            if idx % llffhold == 0:
                test_image_names.append(image_name)
            else:
                train_image_names.append(image_name)
        print("Test Cameras")
        for test in test_image_names:
            print(" ", test)

        print("Train Cameras")
        for train in train_image_names:
            print(" ", train)

        for camera in camera_info:
            if camera["image"] in test_image_names:
                camera["type"] = "test"
            elif camera["image"] in train_image_names:
                camera["type"] = "train"
            else:
                camera["type"] = "ignored"


    else:
        raise Exception(f"Camera info file {camera_info_path} does not exist. Not Implemented yet to create one")

    with open(os.path.join(data_dir, "camera_info.json"), "w") as f:
        f.write(json.dumps(camera_info, indent=4))


def transform_bounding_area(project_path: str, bounding_area: BoundingArea):
    colmap_image_path = os.path.join(project_path, 'data', 'sparse', '0', 'images.txt')
    camera_info_path = os.path.join(project_path, 'data', 'camera_info.json')

    if not os.path.exists(camera_info_path):
        print(colmap_image_path, 'or', camera_info_path, "does not exist")
        return

    colmap_images, _ = colmap_util.parse_images_txt(colmap_image_path)
    camera_info = []
    with open(camera_info_path) as f:
        camera_info = json.load(f)
    transformed_bound_area = bounding_area.get_transformed_bound_area(colmap_images, camera_info)
    transformed_bound_area.write(os.path.join(project_path, 'data'))
    return transformed_bound_area


def image_blurry(image_path, threshold=800):
    # Load image in grayscale
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print('Could not read image', image_path)
        return False
    laplacian = cv2.Laplacian(img, cv2.CV_64F)
    variance = laplacian.var()

    print(f"Laplacian variance: {variance:.2f}", "for image", image_path)
    return variance < threshold


if __name__ == "__main__":
    parser = ArgumentParser("Colmap converter")
    parser.add_argument("--sources", "-s", nargs="+", type=str, required=True, help='One or more project folders, each containing a data/src-data/ subdirectory with the raw source files.')
    parser.add_argument("--parse_video",  action="store_true")
    parser.add_argument('--parse_video_without_srt', action='store_true')
    parser.add_argument('--parse_exr', action='store_true')
    parser.add_argument('--parse_jpg', action='store_true')

    parser.add_argument("--skip_sfm", action="store_true")
    parser.add_argument('--out_fps', default=0.25, type=float)
    parser.add_argument('--width', default=1600, type=int)
    parser.add_argument('--height', default=900, type=int)
    parser.add_argument('--remove_outside_cameras', action='store_true')
    parser.add_argument('--multiple_cameras', action='store_true')
    parser.add_argument('--blur_threshold', default=800, type=int)

    args = parser.parse_args()
    sources = args.sources

    print("Removing outside cameras:", args.remove_outside_cameras)

    start_time = time.time()
    for source in sources:

        bounding_area = read_in_bounding_area(os.path.join(source, 'data', 'src-data'))

        cam_info = []

        if args.parse_video:
           cam_info += parse_videos(
               source,
               out_fps=args.out_fps,
               out_size = [args.width, args.height],
               bounding_area=bounding_area,
               remove_outside_cameras=args.remove_outside_cameras,
               parse_without_srt=args.parse_video_without_srt,
               blur_threshold=args.blur_threshold
           )

        if args.parse_exr:
            cam_info += parse_exr(source)

        if args.parse_jpg:
            cam_info += parse_jpg(source, out_width=args.width)

        if not args.parse_video and not args.parse_exr and not args.parse_jpg:
            cam_info += create_initial_camera_info(source)

        if len(cam_info) != 0:
            with open(os.path.join(source, 'data', 'camera_info.json'), "w") as f:
                f.write(json.dumps(cam_info, indent=4))

        if args.skip_sfm: # to just convert the images
            continue

        matching(os.path.join(source,'data'), args.multiple_cameras)

        update_camera_info(source)

    print("Elapsed time:", time.time() - start_time)