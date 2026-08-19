from __future__ import annotations
import json
import math
import os.path

import torch
import numpy as np
from PIL import Image
from diff_disaster_gaussian_rasterization import GaussianTimeRasterizationSettings
from diff_disaster_gaussian_rasterization import GaussianTimeRasterizer
from torch import Tensor

import utils.colmap_util as colmap_util

class Camera:
    """
    Camera data/utilities for the disaster splatting render framework.
    Data is generally stored in the cameras.json file.
    """
    id: str
    rotation: np.ndarray
    position: np.ndarray
    img_name: str
    width: int
    height: int
    fx: float
    fy: float
    t: int
    image: Tensor = None

    def __init__(self, camera_data, image_dictionary_path = None, depth_image_dict = None):
        self.id = camera_data['id']
        self.data = camera_data.copy()
        if 't' not in self.data:
            self.data['t'] = int(0)
        self.t = int(self.data['t'])
        self.position = self.data['position']
        self.rotation = self.data['rotation']
        self.width = self.data['width']
        self.height = self.data['height']
        self.fx = self.data['fx']
        self.fy = self.data['fy']
        self.img_name = self.data['img_name']
        self.depth = None
        self.image = None

        self.load_gt_image(image_dictionary_path)
        self.load_depth_map(depth_image_dict)

        self.settings = self._compute_rasterizer_settings()

    def load_gt_image(self, image_dictionary_path = None):
        if image_dictionary_path is not None and self.image is None:
            img_path = os.path.join(image_dictionary_path, self.data['img_name'])
            if not os.path.exists(img_path):
                img_path = os.path.join(image_dictionary_path, self.data['img_name'] + '.png')
                self.img_name = self.data['img_name'] + '.png'
            if not os.path.exists(img_path):
                img_path = os.path.join(image_dictionary_path, self.data['img_name'] + '.jpg')
                self.img_name = self.data['img_name'] + '.jpg'
            if not os.path.exists(img_path):
                img_path = os.path.join(image_dictionary_path, self.data['img_name'] + '.exr.png')
                self.img_name = self.data['img_name'] + 'exr.png'
            if not os.path.exists(img_path):
                print('image path not found', img_path)

            image_src = Image.open(img_path)

            image = torch.from_numpy(np.array(image_src)) / 255.0
            if len(image.shape) == 3:
                self.image = image.permute(2, 0, 1)
            else:
                self.image = image.unsqueeze(dim=-1).permute(2, 0, 1)

            # check if dimensions of images line up
            gt_img_width, gt_img_height = image_src.size
            if self.width != gt_img_width or self.height != gt_img_height:
                print('Image size mismatch', gt_img_width, gt_img_height, ' -> updating camera data')
                self.data['width'] = gt_img_width
                self.data['height'] = gt_img_height
                self.width = gt_img_width
                self.height = gt_img_height


    def load_depth_map(self, depth_image_dict = None):
        if depth_image_dict is not None and self.depth is None:
            depth_path = os.path.join(depth_image_dict, self.img_name + '.pt')
            if not os.path.exists(depth_path):
                depth_path = os.path.join(depth_image_dict, self.img_name + '.png' + '.pt')
                if not os.path.exists(depth_path):
                    depth_path = os.path.join(depth_image_dict, self.img_name + '.jpg' + '.pt')
            if os.path.exists(depth_path):
                depth_map = torch.load(depth_path, map_location=torch.device('cpu'))
                self.depth = depth_map
            else:
                print('depth image not found', depth_path)

    def _compute_rasterizer_settings(self):
        w = self.width
        h = self.height

        fx = self.fx
        fy = self.fy

        bg = torch.tensor([0, 0, 0], dtype=torch.float32, device="cuda")

        tanfovx = 0.5 * w / fx
        tanfovy = 0.5 * h / fy

        rot = np.array(self.rotation)
        pos = np.array(self.position)
        W2C = np.zeros((4, 4))
        W2C[3, 3] = 1
        W2C[:3, :3] = rot
        W2C[:3, 3] = pos
        Rt = np.linalg.inv(W2C)
        camera_t = Rt[:3, 3]
        camera_r = Rt[:3, :3]
        camera_r = camera_r.transpose()

        world_view_transform = torch.tensor(get_world2_view2(camera_r, camera_t)).transpose(0, 1).cuda()
        projection_matrix = get_projection_matrix(0.01, 100, 2 * math.atan(tanfovx), 2 * math.atan(tanfovy)).transpose(
            0, 1).cuda()
        full_proj_transform = (world_view_transform.unsqueeze(0).bmm(projection_matrix.unsqueeze(0))).squeeze(0)
        campos = torch.tensor(self.position).cuda()

        return GaussianTimeRasterizationSettings(
            image_width=w,
            image_height=h,
            tanfovx=tanfovx,
            tanfovy=tanfovy,
            bg=bg,
            scale_modifier=1.0,
            campos=campos,
            prefiltered=False,
            debug=False,
            antialiasing=False,
            viewmatrix=world_view_transform,
            projmatrix=full_proj_transform,
            sh_degree=0,
            t=self.t,
            validate=False
        )

    def visible_gaussians(self, means):
        rasterizer = GaussianTimeRasterizer(self.settings)
        return rasterizer.in_viewport(means)


def write_to_json(out_file_path: str, cameras: list[Camera]):
    json_cameras = []
    for camera in cameras:
        Rt = np.zeros((4, 4))
        Rt[:3, :3] = camera.rotation.transpose()
        Rt[:3, 3] = camera.position
        Rt[3, 3] = 1.0

        W2C = np.linalg.inv(Rt)
        pos = W2C[:3, 3]
        rot = W2C[:3, :3]

        serializable_array_2d = [x.tolist() for x in rot]

        json_cameras.append({
            'id': str(camera.id),
            'img_name':camera.img_name,
            'width': camera.width,
            'height': camera.height,
            'position': pos.tolist(),
            'rotation': serializable_array_2d,
            'fy' : fov2focal(camera.fy, camera.height),
            'fx' : fov2focal(camera.fx, camera.width),
            't': camera.t,
        })

    with open(out_file_path, "w") as file:
        file.write(json.dumps(json_cameras, indent=4))

def from_colmap_model(colmap_model_path:str, images_folder:str, camera_info_path: str, type: str = None) -> list[Camera]:
    """
    Utility Function to create a list of cameras from cameras.json / cameras_test.json used by the gsp renderer.
    Using intrinsic / extrinsic camera and image data from the colmap model and the t from
    the camera_info path. If type is provided filters the cameras based on the type defined in
    camera_info.json (so the complete colmap path should be fine).
    :param colmap_model_path:
    :param images_folder:
    :param camera_info_path:
    :param type:
    :return:
    """
    cameras = []
    images_txt_file_path = os.path.join(colmap_model_path, 'images.txt')
    cameras_txt_file_path = os.path.join(colmap_model_path, 'cameras.txt')

    col_imgs, header_lines = colmap_util.parse_images_txt(images_txt_file_path)
    col_cameras = colmap_util.read_cameras_txt(cameras_txt_file_path)

    with open(camera_info_path) as f:
        camera_info = json.load(f)
    camera_info_dict = {}
    for info in camera_info:
        camera_info_dict[info['image']] = info

    for img_name in col_imgs:
        col_img = col_imgs[img_name] # extrinsic
        col_camera = col_cameras[col_img.CAMERA_ID] #intrinsic

        if type is None or camera_info_dict[col_img.NAME.strip()]['type'] == type:
            focal_length_x = float(col_camera.params[0]) #intr.params[0]
            focal_length_y = float(col_camera.params[1]) # intr.params[1]
            FovY = focal2fov(focal_length_y, col_camera.height)
            FovX = focal2fov(focal_length_x, col_camera.width)
            rotation = np.transpose(qvec2rotmat([col_img.QW, col_img.QX, col_img.QY, col_img.QZ]))
            camera_data = {
                'id': col_img.IMAGE_ID,
                'width': col_camera.width,
                'height': col_camera.height,
                'fy': FovY,
                'fx': FovX,
                'position': [col_img.TX, col_img.TY, col_img.TZ],
                'rotation': rotation,
                'img_name': col_img.NAME.strip()
            }
            if 't' in camera_info_dict[col_img.NAME.strip()]:
                camera_data['t'] = camera_info_dict[col_img.NAME.strip()]['t']

            camera = Camera(camera_data, image_dictionary_path=images_folder)
            cameras.append(camera)

    return cameras

def get_cameras(json_cameras, image_dictionary_path = None, info = None, image_type = None):
    print("Getting Cameras ", "type", image_type)
    cameras: list[Camera] = []
    for json_camera in json_cameras:
        use_camera = True
        if info is not None and image_type is not None:
            camera_info = [i for i in info if i['image'] == json_camera['img_name'] or i['image'] == (json_camera['img_name'] + '.png') or i['image'] == (json_camera['img_name'] + '.exr.png')]
            if len(camera_info) != 1:
                use_camera = False
                print("No Camera info or multiple are found. Ignoring Camera")
            elif camera_info[0]["type"] != image_type:
                    use_camera = False
        if use_camera:
            print(" ", json_camera['img_name'])
            camera = Camera(json_camera, image_dictionary_path=image_dictionary_path)
            cameras.append(camera)
    return cameras

def get_times_from_cameras(cameras):
    times = []
    for camera in cameras:
        t = camera.t
        if t not in times:
            times.append(t)

    times.sort()
    return times

def transform_json_camera(camera, tm):
    positon = np.array(camera['position'])
    pos4 = np.append(positon, [1])
    pos4 = tm @ pos4.transpose()
    camera['position'] = pos4[:3].tolist()

    rot_mat = np.eye(4)
    rot_mat[:3, :3] = np.array(camera['rotation'])
    rot_mat = tm @ rot_mat
    camera['rotation'] = rot_mat[:3, :3].tolist()

    return camera

def manipulate_check_json_cameras(camera_file_path, target_model_path, trans_mat, t_shift):
    with open(camera_file_path, 'r') as file:
        cameras_1 = json.load(file)
    registered_cameras = []
    for camera in cameras_1:
        image_path = os.path.join(target_model_path, 'data', 'images', camera['img_name'])

        # some version of gaussian splatting do not store the suffix in img_name
        if not os.path.exists(image_path):
            image_path = os.path.join(target_model_path, 'data', 'images', camera['img_name'] + '.png')
        if not os.path.exists(image_path):
            image_path = os.path.join(target_model_path, 'data', 'images', camera['img_name'] + '.jpg')
        if not os.path.exists(image_path):
            image_path = os.path.join(target_model_path, 'data', 'images', camera['img_name'] + '.exr' + '.png')

        if os.path.exists(image_path):
            image_src = Image.open(image_path)
            image = np.array(image_src)
            camera = transform_json_camera(camera, trans_mat)
            camera['id'] = str(t_shift) + '_' + str(camera['id'])
            if 't' in camera:
                camera['t'] = camera['t'] + t_shift
            else:
                camera['t'] = t_shift
            camera['height'] = image.shape[0]
            camera['width'] = image.shape[1]
            registered_cameras.append(camera.copy())
        else:
            print('image path not found', image_path)
    return registered_cameras

def resize_images_in_folder(in_folder, out_folder, resolution):
    images = os.listdir(in_folder)
    for image in images:
        cmd = (
                "ffmpeg"
                + " -i " + os.path.join(in_folder, image)
                + " -vf scale=iw/" + str(resolution) + ":ih/" + str(resolution)
                + " " + os.path.join(out_folder, image)
        )
        error = os.system(cmd)
        if error != 0:
            print('Failed to resize image', os.path.join(in_folder, image))
            print('Error code:', error)

def focal2fov(focal, pixels):
    return 2*math.atan(pixels/(2*focal))

def fov2focal(fov, pixels):
    return pixels / (2 * math.tan(fov / 2))

def qvec2rotmat(qvec):
    return np.array([
        [1 - 2 * qvec[2]**2 - 2 * qvec[3]**2,
         2 * qvec[1] * qvec[2] - 2 * qvec[0] * qvec[3],
         2 * qvec[3] * qvec[1] + 2 * qvec[0] * qvec[2]],
        [2 * qvec[1] * qvec[2] + 2 * qvec[0] * qvec[3],
         1 - 2 * qvec[1]**2 - 2 * qvec[3]**2,
         2 * qvec[2] * qvec[3] - 2 * qvec[0] * qvec[1]],
        [2 * qvec[3] * qvec[1] - 2 * qvec[0] * qvec[2],
         2 * qvec[2] * qvec[3] + 2 * qvec[0] * qvec[1],
         1 - 2 * qvec[1]**2 - 2 * qvec[2]**2]])

## copied from orig. impl.
def get_projection_matrix(znear, zfar, fovX, fovY):
    tanHalfFovY = math.tan((fovY / 2))
    tanHalfFovX = math.tan((fovX / 2))

    top = tanHalfFovY * znear
    bottom = -top
    right = tanHalfFovX * znear
    left = -right

    P = torch.zeros(4, 4)

    z_sign = 1.0

    P[0, 0] = 2.0 * znear / (right - left)
    P[1, 1] = 2.0 * znear / (top - bottom)
    P[0, 2] = (right + left) / (right - left)
    P[1, 2] = (top + bottom) / (top - bottom)
    P[3, 2] = z_sign
    P[2, 2] = z_sign * zfar / (zfar - znear)
    P[2, 3] = -(zfar * znear) / (zfar - znear)

    return P

# copied from orig. impl.
def get_world2_view2(R, t, translate=np.array([.0, .0, .0]), scale=1.0):
    Rt = np.zeros((4, 4))
    Rt[:3, :3] = R.transpose()
    Rt[:3, 3] = t
    Rt[3, 3] = 1.0

    C2W = np.linalg.inv(Rt)
    cam_center = C2W[:3, 3]
    cam_center = (cam_center + translate) * scale
    C2W[:3, 3] = cam_center
    Rt = np.linalg.inv(C2W)
    return np.float32(Rt)
