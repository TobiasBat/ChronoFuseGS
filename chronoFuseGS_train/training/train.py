"""
Refines a Multi-Temporal Gaussian Model
"""

import argparse
import math
import sys
import os
import json
from random import randint, random
import copy
import time
import torch
import torchvision
from plyfile import PlyData
from tqdm import tqdm
import lpips

from utils.camera import get_cameras, Camera
from utils.gaussians import Gaussians
from utils.fuse_utils import copy_meta_files
from utils.learning_rates import GaussiansLearningRate, DEFAULT_LR, LARGE_SCALE_LR, CROSS_TIMESTEP_INIT_LR
from utils.gaussians import get_heighest_point_cloud_folder
from utils.temporal_activation import ActivationData
from utils.loss_utils import ssim

# gaussians at time t that are rendered from at least one camera are marked with true, otherwise false
def _validatable_gaussians(gaussians: Gaussians, cameras: list[Camera]):
    opacity_activation = gaussians.get_opacity_activation
    is_validated = torch.zeros_like(opacity_activation, dtype=torch.bool, device="cuda")
    for camera in cameras:
        _, radii, gaussians_rendered, __ = gaussians.forward(camera, validate=True)# forward(gaussians, camera.settings, validate=True)
        t = camera.t
        mask = gaussians_rendered > 0
        is_validated[:, t].logical_or_(mask)

    return is_validated


def combined_refinement(gaussians: Gaussians, cameras: list[Camera], train_it: int, validate_it: int = 2000, lambda_dssim = 0.2, change_diff_weight = 0.1, opacity_manipulation_reset: float = 0.5):

    progress_bar = tqdm(range(0, train_it), desc="Training progress")

    with torch.no_grad():
        op_act_diff_start = torch.diff(gaussians.opacity_activation_parameter, dim=-1)

    if opacity_manipulation_reset != 1.0:
        with torch.no_grad():
            tuned_down_op = torch.logit(torch.sigmoid(
                gaussians.opacities_parameter.clone()
            ) * opacity_manipulation_reset)
            gaussians.opacities_parameter.copy_(tuned_down_op)

    for iteration in range(1, train_it + 1):

        random_index = randint(0, len(cameras) - 1)
        camera = cameras[random_index]

        image, _, rendered_gaussians, depth_image = gaussians.forward(camera)
        gt_image = camera.image.cuda()

        ll1 = torch.abs((image - gt_image)).mean()
        ssim_value = ssim(image, gt_image)

        # limiting the difference of the opacity activation
        # it has rather limid effect
        op_act_diff = torch.diff(gaussians.opacity_activation_parameter, dim=-1)
        change_diff_loss = torch.abs(op_act_diff_start - op_act_diff).mean()

        loss = (1.0 - lambda_dssim) * ll1 + lambda_dssim * (1.0 - ssim_value) + change_diff_weight * change_diff_loss
        loss.backward()

        with torch.no_grad():
            if iteration % 10 == 0:
                progress_bar.set_postfix({"Loss": f"{loss.item():.{7}f}"})
                progress_bar.update(10)

            if iteration == train_it:
                progress_bar.close()

            if validate_it > 0 and iteration % validate_it == 0:
                is_validated = _validatable_gaussians(gaussians, cameras)
                not_validatable = torch.logical_not(is_validated)
                gaussians.set_constant_opacity_activation(not_validatable, -4 * math.e)

            gaussians.optimizer.step()
            gaussians.optimizer.zero_grad(set_to_none=True)

    if validate_it > 0:
        with torch.no_grad():
            print('Doing final validation ...')
            is_validated = _validatable_gaussians(gaussians, cameras)
            gaussians.set_constant_opacity_activation(~is_validated, -4 * math.e)

    return 0


def write_results(out_gaussians: Gaussians, out_path: str, trained_it: int, pc_folder_name: str = None, prune: bool = False, gaussian_info: dict = None):
    output_dir = os.path.join(out_path, 'output', 'point_cloud', 'refined_' + str(trained_it))
    if pc_folder_name is not None:
        output_dir = os.path.join(out_path, 'output', 'point_cloud', pc_folder_name)
    os.makedirs(output_dir, exist_ok=True)

    ply_file = os.path.join(output_dir, 'point_cloud.ply')
    activation_file_ply = os.path.join(output_dir, 'activation.ply')

    if prune:
        mask = out_gaussians.get_active_gaussians_masks(debug=True)
        ActivationData.write_activation_data(
            None,
            opacity=out_gaussians.opacity_activation_parameter.detach()[mask].cpu().numpy(),
            color=gaussian_set.activation_color.detach()[mask].cpu().numpy(),
            filepath_ply=activation_file_ply
        )
        out_gaussians.write_to_ply_file(ply_file, mask=mask)
        print("Removed Gaussians: ", (~mask).sum().item())
    else:
        mask = None
        ActivationData.write_activation_data(
            None,
            opacity=out_gaussians.opacity_activation_parameter.detach().cpu().numpy(),
            color=gaussian_set.activation_color.detach().cpu().numpy(),
            filepath_ply=activation_file_ply
        )
        out_gaussians.write_to_ply_file(ply_file)

    if gaussian_info is not None:
        updated_info = dict(gaussian_info)
        if mask is not None:
            mask_np = mask.cpu().numpy()
            start, updated_counts = 0, []
            for count in gaussian_info['num_gaussians_per_t']:
                updated_counts.append(int(mask_np[start:start + count].sum()))
                start += count
            updated_info['num_gaussians_per_t'] = updated_counts
        with open(os.path.join(output_dir, 'src_gaussian_info.json'), 'w') as f:
            f.write(json.dumps(updated_info, indent=4))

    return output_dir


def init_cross_timestep(gaussians: Gaussians, cameras: list[Camera], num_per_t: list[int],
                  train_it: int, lr: GaussiansLearningRate, update_c_act=True, update_op_act=True, cross_timestep_different_padding = 0.15, init_op_act_mult = 0.5, debug_folder: str = None, new_t: list = None):
    # new_t: indices of timesteps that are genuinely new (not yet cross-initialized).
    # Already-trained timesteps still run but only against new-t cameras and only
    # write new-t columns — preserving established relationships while learning new ones.
    # None (default) = treat all timesteps as new → original behaviour.
    print('Updating Color act', update_c_act)
    print('Updating Opacity act', update_op_act)
    print('With learning rate', lr)

    times = list(range(0, gaussians.opacity_activation_parameter.size()[1]))
    progress_bar = tqdm(range(0, train_it), desc="cross-timestep init")
    start_op_act = gaussians.opacity_activation_parameter.clone()
    result_op_act = gaussians.opacity_activation_parameter.clone()
    result_color_act = gaussians.activation_color.clone()
    start_color_act = gaussians.activation_color.clone()

    time_id_ranges = []
    for t in times:
        if t == 0:
            time_id_ranges.append([0, num_per_t[t]])
        else:
            time_id_ranges.append([time_id_ranges[t - 1][1], time_id_ranges[t - 1][1] + num_per_t[t]])

    lpips_fn = lpips.LPIPS(net='alex', spatial=True).cuda()  # or 'alex' for faster forward pass, 'vgg' should have better gradients

    # free parent optimizer — each t-block uses a sub_g with its own small optimizer
    if gaussians.optimizer is not None:
        del gaussians.optimizer
        gaussians.optimizer = None
        torch.cuda.empty_cache()

    # init for time after time
    iteration = 0
    for t, id_range in enumerate(time_id_ranges):
        is_new_t = new_t is None or t in new_t
        # already-trained t: train only against new cameras — no point re-learning established relationships
        cameras_not_t = [c for c in cameras if c.t != t] if is_new_t \
                   else [c for c in cameras if c.t in new_t]

        n_sub = id_range[1] - id_range[0]
        col = start_op_act.shape[1]
        with torch.no_grad():
            sub_g = Gaussians.from_slice(gaussians, id_range[0], id_range[1])
            # broadcast t-column (attenuated) across all T columns as starting activation
            init_op = torch.logit(
                torch.sigmoid(start_op_act[id_range[0]:id_range[1], t:t+1]) * init_op_act_mult
            ).expand(n_sub, col)
            sub_g.opacity_activation_parameter.data.copy_(init_op)
            sub_g.activation_color.data.copy_(start_color_act[id_range[0]:id_range[1]])
        sub_g.create_new_optimizer(copy.deepcopy(lr))

        t_iter = train_it // len(time_id_ranges)
        total_iter_t = t_iter
        while t_iter > 0:
            random_index = randint(0, len(cameras_not_t) - 1)
            camera = cameras_not_t[random_index]

            progress = min(float(t_iter) / (float(total_iter_t) * 1.0), 1.0)

            bg_color = torch.tensor([progress * random() for _ in range(3)], dtype=torch.float32, device="cuda")
            image, *_ = sub_g.forward(camera, only_cold_warm_shift=update_c_act, background_color=bg_color)
            gt_image = camera.image.cuda()

            with torch.no_grad():
                # lpips requires [-1, 1], shape (N, 3, H, W)
                image_11 = image * 2 - 1
                gt_image_11 = gt_image * 2 - 1
                different = lpips_fn(image_11.unsqueeze(0), gt_image_11.unsqueeze(0))
                different = different.squeeze(0)  # (1, H, W)

                low = 0.5 - (0.5 - cross_timestep_different_padding) * progress  # 0.5 → padding
                high = 0.5 + (0.5 - cross_timestep_different_padding) * progress  # 0.5 → 1 - padding
                k = different * (high - low) + low

            bg_image = torch.ones_like(image) * bg_color.view(-1, 1, 1)

            l1_color = torch.abs(gt_image - image)
            dis_loss = torch.abs(bg_image - image)
            loss = (k * dis_loss + (1 - k) * l1_color).mean()
            loss.backward()

            if iteration % 100 == 0 and debug_folder is not None:
                torchvision.utils.save_image(image, os.path.join(debug_folder, f'{t}_{t_iter}_0_image.jpg'))

            with torch.no_grad():
                if iteration % 10 == 0:
                    progress_bar.set_postfix({"Loss": f"{loss.item():.{7}f}"})
                    progress_bar.update(10)

                sub_g.optimizer.step()
                if update_c_act:
                    sub_g.project_color_activation()
                sub_g.optimizer.zero_grad(set_to_none=True)

            t_iter -= 1
            iteration += 1

        # now we combine the result to update col t of result op_act
        with torch.no_grad():
            # Detect which gaussians have been trained & are not rendered at one point
            valid_gaussians_sub = _validatable_gaussians(sub_g, cameras_not_t)
            sub_in_range = torch.ones(n_sub, col, dtype=torch.bool, device='cuda')
            sub_in_range[:, t] = False  # don't reset own-t column
            sub_gaussians_to_reset = (~valid_gaussians_sub) & sub_in_range
            print('\nGaussians that are not validated', sub_gaussians_to_reset.float().sum().item())

            comp_op_a = sub_g.opacity_activation_parameter.clone()
            comp_op_a.masked_fill_(sub_gaussians_to_reset, -math.e * 2)
            # keep values for the time the gaussians where actually trained on
            comp_op_a[:, t:t+1] = start_op_act[id_range[0]:id_range[1], t:t+1]
            comp_color_a = sub_g.activation_color.clone()                # (n_sub, T*3)
            comp_color_a[:, t*3:t*3+3] = start_color_act[id_range[0]:id_range[1], t*3:t*3+3]

            if update_op_act:
                if is_new_t:
                    result_op_act[id_range[0]:id_range[1], :] = comp_op_a
                else:
                    # only write new-t columns; established columns stay as start_op_act
                    for nt in new_t:
                        result_op_act[id_range[0]:id_range[1], nt:nt+1] = comp_op_a[:, nt:nt+1]
                print(result_op_act)
            if update_c_act:
                if is_new_t:
                    result_color_act[id_range[0]:id_range[1], :] = comp_color_a
                else:
                    # only write new-t columns; established columns stay as start_color_act
                    for nt in new_t:
                        result_color_act[id_range[0]:id_range[1], nt*3:(nt+1)*3] = comp_color_a[:, nt*3:(nt+1)*3]
                print(result_color_act)

    progress_bar.close()

    # Copying result tensors to gaussian model
    with torch.no_grad():
        gaussians.opacity_activation_parameter.copy_(result_op_act)
        gaussians.activation_color.copy_(result_color_act)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Disaster Renderer")
    parser.add_argument('--source', '-s', type=str, required=True)
    parser.add_argument('--model', '-m', type=str, required=False)
    parser.add_argument('--iterations', '-i', type=int, default=10000)
    parser.add_argument('--iter_init', type=int, default=3000)

    parser.add_argument('--validation_it', default=2000, type=int, help='Num iterations after which Op activation off for gaussian not rendered in any gt of a time. Only main training')
    parser.add_argument('--save_steps', action='store_true',
                        help='Save intermediate model checkpoints after each training stage (e.g. after cross-timestep initialization).')
    parser.add_argument('--ignore_cross_timestep_init', action='store_true', help='Skip cross-timestep initialization before combined refinement')
    parser.add_argument('--new_t', nargs='+', type=int, default=None, help='Timestep indices that are new and need cross-timestep init. Default: all timesteps.')
    parser.add_argument('--cross_timestep_different_padding', type=float, default=0.15)
    parser.add_argument('--debug_folder', type=str, default=None, help='If set, saves debug images from cross-timestep init every 100 iterations to this folder.')
    parser.add_argument('--change_diff_weight', type=float, default=0.1)
    parser.add_argument('--large_scale', '-l', action='store_true', help='Intended for large outdoor scenes. Decreases the position learning rate and uses learning rates appropriate for large-scale geometry.')
    parser.add_argument('--opacity_manipulation_reset', type=float, default=0.5)
    parser.add_argument('--comb_opacity_lr', type=float, default=None,
                        help='Overwrite the opacity learning rate for the combined refinement stage. Defaults to the base learning rate.')
    parser.add_argument('--comb_opacity_act_lr', type=float, default=None,
                        help='Overwrite the opacity activation learning rate for the combined refinement stage. Defaults to the base learning rate.')
    parser.add_argument('--prune', '-p', default=1, type=int)
    parser.add_argument('--out_name', default='', type=str, help='Prefix for the output folder name in output/point_cloud/. Result folder: <out_name>refined_<iterations>')

    args = parser.parse_args(sys.argv[1:])
    model_path = args.model if args.model is not None else args.source
    iterations = args.iterations
    time_start = time.time()

    stats_logs = vars(args) | {
        'model_path': model_path,
        'time_start': time_start,
    }

    # Reading data
    src_point_cloud_folder = get_heighest_point_cloud_folder(args.source, only_prefix='initial')
    ply = PlyData.read(os.path.join(src_point_cloud_folder, 'point_cloud.ply'))
    activation = ActivationData(len(ply['vertex']['opacity']), os.path.join(src_point_cloud_folder, 'activation.ply'))

    src_image_path = os.path.join(args.source, 'data', 'images')
    camera_info_path = os.path.join(args.source, 'data', 'camera_info.json')
    camera_path = os.path.join(src_point_cloud_folder, 'cameras.json')
    if not os.path.exists(camera_path):
        camera_path = os.path.join(args.source, 'output', 'cameras.json')

    with open(camera_path, 'r') as file:
        json_cameras_data = json.load(file)
    with open(camera_info_path, 'r') as file:
        json_cameras_info = json.load(file)
    train_cameras = get_cameras(json_cameras_data, info=json_cameras_info, image_type="train")
    test_cameras = get_cameras(json_cameras_data, info=json_cameras_info, image_type="test")

    lr = LARGE_SCALE_LR if args.large_scale else DEFAULT_LR

    gaussian_set = Gaussians(ply, activation, lr=lr)
    stats_logs['color_activation_mult'] = gaussian_set.color_activation_mult
    stats_logs['color_activation_shift'] = gaussian_set.color_activation_shift

    with open(os.path.join(src_point_cloud_folder, 'src_gaussian_info.json'), 'r') as file:
        src_gaussian_info = json.load(file)
    num_gaussians_per_t = src_gaussian_info['num_gaussians_per_t']

    for c in train_cameras: c.load_gt_image(src_image_path)

    time_start_training = time.time()

    if not args.ignore_cross_timestep_init:
        time_start_cross_init = time.time()
        num_times = gaussian_set.num_times
        if args.new_t is not None:
            # scale iterations to only new relationships: each new-t vs all others + each old-t vs new-t
            # invariant: total iterations == iter_init * num_times*(num_times-1) across sequential merges
            n_new = len(args.new_t)
            n_old = num_times - n_new
            cross_init_iterations = args.iter_init * (n_new * (num_times - 1) + n_old * n_new)
        else:
            cross_init_iterations = args.iter_init * num_times * (num_times - 1)
        stats_logs['cross_init_iterations'] = cross_init_iterations
        init_cross_timestep(gaussian_set, train_cameras, num_gaussians_per_t, cross_init_iterations, CROSS_TIMESTEP_INIT_LR,
                   cross_timestep_different_padding=args.cross_timestep_different_padding,
                   init_op_act_mult=0.5,
                   debug_folder=args.debug_folder,
                   new_t=args.new_t
                   )
        stats_logs['time_elapsed_cross_init'] = time.time() - time_start_cross_init
        if args.save_steps:
            folder_name = args.out_name if args.out_name is not None else ""
            out_dir = write_results(gaussian_set, model_path, iterations, pc_folder_name=folder_name + "cross_init_" + str(iterations), gaussian_info=src_gaussian_info)
            copy_meta_files(src_point_cloud_folder, out_dir)
            with open(os.path.join(out_dir, 'stats.json'), "w") as file:
                file.write(json.dumps(stats_logs, indent=4))

    lr = LARGE_SCALE_LR if args.large_scale else DEFAULT_LR
    if args.comb_opacity_lr is not None:
        lr = lr._replace(opacities=args.comb_opacity_lr)
    if args.comb_opacity_act_lr is not None:
        lr = lr._replace(opacity_activation=args.comb_opacity_act_lr)

    gaussian_set.create_new_optimizer(lr)
    time_start_combined_refinement = time.time()
    combined_refinement(
        gaussian_set, train_cameras, iterations,
        validate_it=args.validation_it,
        change_diff_weight=args.change_diff_weight,
        opacity_manipulation_reset=args.opacity_manipulation_reset
    )
    time_end_training = time.time()

    folder_name = args.out_name + 'refined_' + str(iterations)
    out_dir = write_results(gaussian_set, model_path, iterations, pc_folder_name= folder_name, prune=args.prune == 1, gaussian_info=src_gaussian_info)
    copy_meta_files(src_point_cloud_folder,out_dir)

    stats_logs['time_elapsed_combined_refinement'] = time_end_training - time_start_combined_refinement
    stats_logs['time_elapsed_training_total'] = time_end_training - time_start_training # includes saving itermediates
    stats_logs['time_elapsed_complete'] = time.time() - time_start # includes saving of final model
    stats_logs['time_elapsed_complete_minutes'] = (time.time() - time_start)/60
    stats_logs['avg_loss_after'] = gaussian_set.evaluate(train_cameras)
    stats_logs['time_end_training'] = time_end_training
    stats_logs = stats_logs | gaussian_set.get_stats()

    with open(os.path.join(out_dir, 'stats.json'), "w") as file:
        file.write(json.dumps(stats_logs, indent=4))