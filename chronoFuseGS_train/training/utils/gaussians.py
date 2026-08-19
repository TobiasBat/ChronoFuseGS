import math
import os
import torch
import numpy as np
import torchvision
from diff_disaster_gaussian_rasterization import GaussianTimeRasterizer
from plyfile import PlyElement, PlyData
from torch import nn

from utils.camera import Camera
from utils.learning_rates import GaussiansLearningRate
from utils.temporal_activation import ActivationData
from utils.loss_utils import ssim


class Gaussians:
    color_activation_mult = 2.0 # 1.5 #1.25 # 2.0
    color_activation_shift = 0.0 # 0.25 #0.375 # 0.0
    def __init__(self, ply, activation: ActivationData, lr: GaussiansLearningRate = None, white_background=False):
        x = np.array(ply['vertex']['x'])
        y = np.array(ply['vertex']['y'])
        z = np.array(ply['vertex']['z'])

        opacities = np.array(ply['vertex']['opacity'])
        opacities = opacities.reshape(-1, 1)
        means = np.stack((x, y, z), axis=-1)

        dc_0 = np.array(ply['vertex']['f_dc_0'])
        dc_1 = np.array(ply['vertex']['f_dc_1'])
        dc_2 = np.array(ply['vertex']['f_dc_2'])
        dcs = np.stack((dc_0, dc_1, dc_2), axis=-1)
        # dcs = dcs * 0.28209479177387814 + 0.5

        sx = np.array(ply['vertex']['scale_0'])
        sy = np.array(ply['vertex']['scale_1'])
        sz = np.array(ply['vertex']['scale_2'])
        scales = np.stack((sx, sy, sz), axis=-1)

        r0 = np.array(ply['vertex']['rot_0'])
        r1 = np.array(ply['vertex']['rot_1'])
        r2 = np.array(ply['vertex']['rot_2'])
        r3 = np.array(ply['vertex']['rot_3'])
        quats = np.stack((r0, r1, r2, r3), axis=-1)

        means_tensor = torch.tensor(means, dtype=torch.float, device="cuda")
        self.means_parameter = torch.nn.Parameter(means_tensor.requires_grad_(True))

        dc_tensor = torch.tensor(dcs).float().cuda()
        self.dc_parameter = nn.Parameter(dc_tensor.requires_grad_(True))

        scale_tensor = torch.tensor(scales).float().cuda()
        self.scale_parameter = nn.Parameter(scale_tensor.requires_grad_(True))

        quat_tensor = torch.tensor(quats).float().cuda()
        self.quat_parameter = nn.Parameter(quat_tensor.requires_grad_(True))

        opacities_tensor = torch.tensor(opacities).float().cuda()
        self.opacities_parameter = nn.Parameter(opacities_tensor.requires_grad_(True))

        self.opacity_activation_parameter = nn.Parameter(
            torch.tensor(activation._opacity).float().cuda().requires_grad_(True)
        )

        color_activation_tensor = torch.tensor(activation.get_color_mat).float().cuda()
        self.activation_color = nn.Parameter(
            color_activation_tensor.requires_grad_(True)
        )

        self.lr = GaussiansLearningRate() if lr is None else lr

        params = self._get_params()

        self.optimizer = torch.optim.Adam(params, lr=1e-3, eps=1e-15)
        self.init_gaussians_number = self.opacities_parameter.size(0)

        bg_color = [1, 1, 1] if white_background else [0, 0, 0]
        self.background = torch.tensor(bg_color, dtype=torch.float32, device="cuda")

        self.num_times = activation.num_t

    _lab_cache: dict = {}

    @classmethod
    def _get_lab_constants(cls, device, dtype):
        key = (str(device), dtype)
        if key not in cls._lab_cache:
            cls._lab_cache[key] = (
                torch.tensor([
                    [0.4124564, 0.3575761, 0.1804375],
                    [0.2126729, 0.7151522, 0.0721750],
                    [0.0193339, 0.1191920, 0.9503041],
                ], device=device, dtype=dtype),
                torch.tensor([0.95047, 1.00000, 1.08883], device=device, dtype=dtype).view(1, 3, 1, 1),
                torch.tensor([
                    [3.2404542, -1.5371385, -0.4985314],
                    [-0.9692660,  1.8760108,  0.0415560],
                    [0.0556434, -0.2040259,  1.0572252],
                ], device=device, dtype=dtype),
            )
        return cls._lab_cache[key]

    @property
    def get_opacity_activation(self):
        return torch.sigmoid(self.opacity_activation_parameter)

    @property
    def get_color_activation(self):
        return torch.sigmoid(self.activation_color) * self.color_activation_mult + self.color_activation_shift

    @property
    def get_color_activation_temperature(self):
        WARM_COLD_ANGLE = 0.2
        axis_a = math.sin(WARM_COLD_ANGLE)
        axis_b = math.cos(WARM_COLD_ANGLE)

        N = self.activation_color.shape[0]
        num_triplets = self.activation_color.shape[1] // 3

        rgb = self.get_color_activation
        rgb = (rgb - self.color_activation_shift) / self.color_activation_mult
        rgb = rgb.reshape(N * num_triplets, 3)
        rgb_4d = rgb.unsqueeze(-1).unsqueeze(-1)

        L, a, b = self.rgb_to_lab(rgb_4d)

        along = a * axis_a + b * axis_b
        a_proj = along * axis_a
        b_proj = along * axis_b


        rgb_proj = self.lab_to_rgb(L, a_proj, b_proj)
        rgb_proj = rgb_proj.squeeze(-1).squeeze(-1)

        final_rgb = (rgb_proj * self.color_activation_mult) + self.color_activation_shift
        return final_rgb.reshape(N, num_triplets * 3)

    @torch.no_grad()
    def project_color_activation(self):
        WARM_COLD_ANGLE = 0.2
        axis_a = math.sin(WARM_COLD_ANGLE)
        axis_b = math.cos(WARM_COLD_ANGLE)

        N = self.activation_color.shape[0]
        num_triplets = self.activation_color.shape[1] // 3

        rgb = self.get_color_activation
        rgb = rgb.reshape(N * num_triplets, 3)
        rgb_4d = rgb.unsqueeze(-1).unsqueeze(-1)

        L, a, b = self.rgb_to_lab(rgb_4d)

        along = a * axis_a + b * axis_b
        a_proj = along * axis_a
        b_proj = along * axis_b

        rgb_proj = self.lab_to_rgb(L, a_proj, b_proj)
        rgb_proj = rgb_proj.squeeze(-1).squeeze(-1)

        p = (rgb_proj - self.color_activation_shift) / self.color_activation_mult
        p = p.clamp(1e-6, 1.0 - 1e-6)
        activated_back = torch.log(p / (1.0 - p))

        activated_back = activated_back.reshape(N, num_triplets * 3)
        self.activation_color.copy_(activated_back)

    @property
    def get_dcs(self):
        return self.dc_parameter * 0.28209479177387814 + 0.5

    @property
    def get_opacity(self):
        return torch.sigmoid(self.opacities_parameter)

    @property
    def get_quat(self):
        return torch.nn.functional.normalize(self.quat_parameter)

    @property
    def get_scale(self):
        return torch.exp(self.scale_parameter)

    @property
    def get_mean3d(self):
        return self.means_parameter

    def _get_params(self):
        parms = [
            {'params': [self.opacity_activation_parameter], 'lr': self.lr.opacity_activation,
             'name': 'opacity_activation'},
            {'params': [self.opacities_parameter], 'lr': self.lr.opacities, 'name': 'opacities'},
            {'params': [self.dc_parameter], 'lr': self.lr.dc, 'name': 'f_dc'},
            {'params': [self.means_parameter], 'lr': self.lr.mean, 'name': 'mean'},
            {'params': [self.scale_parameter], 'lr': self.lr.others, 'name': 'scale'},
            {'params': [self.quat_parameter], 'lr': self.lr.others, 'name': 'quat'},
            {'params': [self.activation_color], 'lr': self.lr.color_activation, 'name': 'color_activation'}
        ]
        return parms

    def create_new_optimizer(self, lr: GaussiansLearningRate):
        if hasattr(self, 'optimizer') and self.optimizer is not None:
            del self.optimizer
        import gc
        gc.collect()
        torch.cuda.empty_cache()

        self.lr = lr
        self.optimizer = torch.optim.Adam(self._get_params(), eps=1e-15)


    @classmethod
    def from_slice(cls, parent: 'Gaussians', start: int, end: int) -> 'Gaussians':
        """Lightweight sub-Gaussians containing only rows [start:end] of parent. Caller must call create_new_optimizer()."""
        instance = cls.__new__(cls)
        instance.means_parameter              = nn.Parameter(parent.means_parameter.data[start:end].clone())
        instance.dc_parameter                 = nn.Parameter(parent.dc_parameter.data[start:end].clone())
        instance.scale_parameter              = nn.Parameter(parent.scale_parameter.data[start:end].clone())
        instance.quat_parameter               = nn.Parameter(parent.quat_parameter.data[start:end].clone())
        instance.opacities_parameter          = nn.Parameter(parent.opacities_parameter.data[start:end].clone())
        instance.opacity_activation_parameter = nn.Parameter(parent.opacity_activation_parameter.data[start:end].clone())
        instance.activation_color             = nn.Parameter(parent.activation_color.data[start:end].clone())
        instance.num_times            = parent.num_times
        instance.background           = parent.background
        instance.lr                   = parent.lr
        instance.init_gaussians_number = end - start
        instance.optimizer            = None
        return instance

    def set_constant_opacity_activation(self, mask, value):
        # self.opacity_activation_parameter[mask] = value
        self.opacity_activation_parameter.masked_fill_(mask, value)


    def write_to_ply_file(self, file_path, mask=None, stats_file=True, additional_stats: dict = None):
        print('Writing to Ply File')

        if mask is None:
            means = self.means_parameter.detach().cpu().numpy()
            dcs = self.dc_parameter.detach().cpu().numpy()
            opacities = self.opacities_parameter.detach().cpu().numpy()
            scale = self.scale_parameter.detach().cpu().numpy()
            quats = self.quat_parameter.detach().cpu().numpy()
            normals = np.zeros_like(means)
        else:
            means = self.means_parameter.detach()[mask].cpu().numpy()
            dcs = self.dc_parameter.detach().cpu()[mask].numpy()
            opacities = self.opacities_parameter.detach()[mask].cpu().numpy()
            scale = self.scale_parameter.detach()[mask].cpu().numpy()
            quats = self.quat_parameter.detach()[mask].cpu().numpy()
            normals = np.zeros_like(means)

        attributes = [
            'x', 'y', 'z',
            'nx', 'ny', 'nz',
            'f_dc_0', 'f_dc_1', 'f_dc_2',
            'opacity',
            'scale_0', 'scale_1', 'scale_2',
            'rot_0', 'rot_1', 'rot_2', 'rot_3'
        ]
        dtype_full = [(attribute, 'f4') for attribute in attributes]

        elements = np.empty(means.shape[0], dtype=dtype_full)
        attributes = np.concatenate((means, normals, dcs, opacities, scale, quats), axis=1)
        elements[:] = list(map(tuple, attributes))
        el = PlyElement.describe(elements, 'vertex')
        PlyData([el]).write(file_path)

    def get_stats(self):
        return{
            'num_gaussians': self.opacities_parameter.shape[0],
            'timesteps': self.opacity_activation_parameter.size(1),
            'lr': dict(self.lr._asdict())
        }

    def get_active_gaussians_masks(self, debug=False):
        activations = self.get_opacity_activation
        opacities = self.get_opacity
        alpha = activations * opacities
        mask = (alpha.cpu().float() < (1 / 255)).all(dim=1)
        mask = ~mask
        if debug:
            sum_invalid = (~mask).sum().item()
            print('Gaussians that are disabled', sum_invalid,
                  '(' + str(round(100 * sum_invalid / opacities.size(0), 1)) + '%)')

        del activations, opacities, alpha
        return mask


    def forward(self, camera: Camera, output_dir=None, output_depth_dir=None, validate=False, time_overwrite=None, only_cold_warm_shift = False, background_color = None):
        camera_settings = camera.settings
        settings_ = camera_settings._replace()
        if validate:
            settings_ = settings_._replace(validate=True)
        if time_overwrite is not None:
            settings_ = settings_._replace(t=time_overwrite)
        if background_color is not None:
            settings_ = settings_._replace(bg=background_color)
        else:
            settings_ = settings_._replace(bg=self.background)
        rasterizer = GaussianTimeRasterizer(settings_)

        mean = self.get_mean3d
        mean2d = torch.zeros_like(mean, dtype=mean.dtype, requires_grad=True, device="cuda") + 0
        opacity = self.get_opacity
        dcs = self.get_dcs
        quat = self.get_quat
        scale = self.get_scale
        opt_act = self.get_opacity_activation
        color_act = self.get_color_activation_temperature if only_cold_warm_shift else self.get_color_activation

        render, radii, depth_image, gaussians_rendered = rasterizer.forward(
            means3D= mean,
            means2D= mean2d,
            opacities=opacity,
            colors_precomp=dcs,
            rotations=quat,
            scales=scale,
            opacity_activation=opt_act,
            color_activiation=color_act
        )

        render = render.clamp(0, 1)


        if output_dir is not None:
            out_image_path = os.path.join(output_dir, 'camera_' + str(camera.data['id']) + ".png")
            print('Writing rendering of camera', camera.id, out_image_path)
            torchvision.utils.save_image(render, out_image_path)

        if output_depth_dir is not None:
            print('Writing depth image of camera', camera.id, output_depth_dir)
            os.makedirs(os.path.join(output_depth_dir), exist_ok=True)
            out_depth_path = os.path.join(output_depth_dir, camera.img_name + ".png")
            print('Out depth path', out_depth_path)
            torchvision.utils.save_image(depth_image, out_depth_path, normalize=True)
            torch.save(depth_image, out_depth_path +'.pt' )

        return render, radii, gaussians_rendered, depth_image

    def evaluate(self, cameras: list[Camera]):
        lambda_dssim = 0.2

        avg_loss = 0.0
        for camera in cameras:
            image, _, __, ___ = self.forward(camera)
            gt_image = camera.image.cuda()
            ll1 = torch.abs((image - gt_image)).mean()
            ssim_value = ssim(image, gt_image)
            loss = (1.0 - lambda_dssim) * ll1 + lambda_dssim * (1.0 - ssim_value)
            avg_loss += loss.cpu().item()
        avg_loss = (avg_loss / len(cameras))
        return avg_loss

    @staticmethod
    def transform_ply_vertex_data(vertex_data, trans_mat, scale_vec, inverted_rot_quat):
        arr = vertex_data.view(np.float32).reshape(len(vertex_data), -1).copy()

        pos_h = np.concatenate([arr[:, :3], np.ones((len(arr), 1), dtype=np.float32)], axis=1)
        arr[:, :3] = (trans_mat @ pos_h.T).T[:, :3]

        arr[:, 10:13] += np.log(scale_vec[:3]).astype(np.float32)

        quats = arr[:, 13:17].copy()
        quats /= np.linalg.norm(quats, axis=1, keepdims=True)
        w1, x1, y1, z1 = inverted_rot_quat
        w2, x2, y2, z2 = quats[:, 0], quats[:, 1], quats[:, 2], quats[:, 3]
        arr[:, 13] = w1*w2 - x1*x2 - y1*y2 - z1*z2
        arr[:, 14] = w1*x2 + x1*w2 + y1*z2 - z1*y2
        arr[:, 15] = w1*y2 - x1*z2 + y1*w2 + z1*x2
        arr[:, 16] = w1*z2 + x1*y2 - y1*x2 + z1*w2

        result = np.empty(len(vertex_data), dtype=vertex_data.dtype)
        result.view(np.float32).reshape(len(result), -1)[:] = arr
        return result

    def rgb_to_lab(self, rgb):
        if rgb.dim() == 3:
            rgb = rgb.unsqueeze(0)
            squeeze = True
        else:
            squeeze = False

        mask = rgb > 0.04045
        rgb_linear = torch.where(mask, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)

        M, white, _ = self._get_lab_constants(rgb.device, rgb.dtype)

        xyz = torch.einsum('nchw,oc->nohw', rgb_linear, M)
        xyz = xyz / white

        epsilon = 0.008856
        kappa = 903.3

        mask_xyz = xyz > epsilon
        f = torch.where(mask_xyz, xyz ** (1.0 / 3.0), (kappa * xyz + 16.0) / 116.0)

        fx, fy, fz = f[:, 0], f[:, 1], f[:, 2]

        L = (116.0 * fy - 16.0).unsqueeze(1)
        a = (500.0 * (fx - fy)).unsqueeze(1)
        b = (200.0 * (fy - fz)).unsqueeze(1)

        if squeeze:
            L, a, b = L.squeeze(0), a.squeeze(0), b.squeeze(0)

        return L, a, b

    def lab_to_rgb(self, L, a, b):
        if L.dim() == 3:
            L, a, b = L.unsqueeze(0), a.unsqueeze(0), b.unsqueeze(0)
            squeeze = True
        else:
            squeeze = False

        fy = (L + 16.0) / 116.0
        fx = a / 500.0 + fy
        fz = fy - b / 200.0

        epsilon = 0.008856
        kappa = 903.3

        xr = torch.where(fx ** 3 > epsilon, fx ** 3, (116.0 * fx - 16.0) / kappa)
        yr = torch.where(L > kappa * epsilon, ((L + 16.0) / 116.0) ** 3, L / kappa)
        zr = torch.where(fz ** 3 > epsilon, fz ** 3, (116.0 * fz - 16.0) / kappa)

        _, white, M_inv = self._get_lab_constants(L.device, L.dtype)
        xyz = torch.cat([xr, yr, zr], dim=1) * white

        # einsum: same fix for the inverse transform
        rgb_linear = torch.einsum('nchw,oc->nohw', xyz, M_inv)  # (N, 3, H, W)

        rgb_linear = rgb_linear.clamp(0.0, 1.0)
        mask = rgb_linear > 0.0031308
        rgb = torch.where(mask,
                          1.055 * rgb_linear ** (1.0 / 2.4) - 0.055,
                          12.92 * rgb_linear)

        rgb = rgb.clamp(0.0, 1.0)

        if squeeze:
            rgb = rgb.squeeze(0)

        return rgb


def get_heighest_point_cloud_folder(path, only_prefix=None, output_folder='output'):
    """
    Returns the path to the highest-ranked point cloud subfolder under
    output/point_cloud or pup/<lowest>/point_cloud.
    Ranking: refined_x > refined_x-1 > initial > iteration_x

    :param path: project folder containing an output/ or pup/ directory
    :param only_prefix: limit to folders with this prefix (e.g. 'initial'); default None considers all
    :param output_folder: 'output' or 'pup'
    """
    if output_folder not in ('output', 'pup'):
        raise ValueError('output_folder must be either "output" or "pup"')

    if output_folder == 'pup':
        pup_folder = os.path.join(path, 'pup')
        pup_sub_folders = os.listdir(pup_folder)
        lowest_sub_folder = min(pup_sub_folders, key=int)
        point_cloud_folder = os.path.join(pup_folder, lowest_sub_folder, 'point_cloud')
    else:
        point_cloud_folder = os.path.join(path, output_folder, 'point_cloud')

    print('Searching for the highest point cloud in: ', point_cloud_folder)
    sub_folders = os.listdir(point_cloud_folder)
    if len(sub_folders) == 0:
        return None

    def get_folder_order_index(prefix):
        return {'iteration': 0, 'initial': 1, 'refined': 2}.get(prefix, -1)

    highest_folder = None
    for folder in sub_folders:
        folder_parts = folder.split('_')
        if not (only_prefix is None or only_prefix == folder_parts[0]):
            continue
        if highest_folder is None:
            highest_folder = folder
            continue
        highest_parts = highest_folder.split('_')
        if folder_parts[0] == highest_parts[0]:
            if int(folder_parts[1]) > int(highest_parts[1]):
                highest_folder = folder
        elif get_folder_order_index(folder_parts[0]) > get_folder_order_index(highest_parts[0]):
            highest_folder = folder

    return os.path.join(point_cloud_folder, highest_folder)

