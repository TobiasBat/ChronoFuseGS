"""
Trains the individual timesteps that serve as the input for the multi-temporal model.
Uses PUP 3D-GS to create the models.
"""
import argparse
import os
import shutil
import sys
import time

from utils.colmap_util import convert_points3d_txt_to_ply

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Initial Training")
    parser.add_argument('--source', '-s', type=str, required=True, help='Path to the project folder containing a data/ subdirectory with the COLMAP model.')
    parser.add_argument('--skip_3dgs', action='store_true')
    parser.add_argument('--skip_pup', action='store_true')
    parser.add_argument('--no_eval_data', action='store_true', help='When set, all images are used for training. By default a subset is held out for evaluation.')
    parser.add_argument('--white_background', '-w', action='store_true')
    parser.add_argument('--random_bg', action='store_true')
    parser.add_argument('--large_scale', '-l', action='store_true', help='Intended for large outdoor scenes. Decreases the position and scaling learning rates to avoid divergence.')
    parser.add_argument('--iterations', '-i', type=int, default=30000)
    parser.add_argument('--model', '-m', type=str, required=False)
    args = parser.parse_args(sys.argv[1:])

    source = args.source
    start_time = time.time()

    if not os.path.exists(os.path.join(source, 'data', 'sparse', '0', 'points3D.ply')):
        convert_points3d_txt_to_ply(source)
    data_path = os.path.join(source, 'data')
    output_path = os.path.join(args.model, 'output') if args.model else os.path.join(source, 'output')
    os.makedirs(output_path, exist_ok=True)

    train_cmd = (
            'python train.py'
            + ' --source ' + data_path
            + ' --model ' + output_path
            + ' --sh_degree 0'
            + ' --resolution 1'
            + ' --iterations ' + str(args.iterations)
    )
    if args.large_scale:
        train_cmd += ' --position_lr_init ' + str(0.00016 / 10.0)
        train_cmd += ' --scaling_lr ' + str(0.005 / 1)
    if args.random_bg:
        train_cmd = train_cmd + ' --random_background'
    elif args.white_background:
        train_cmd += ' --white_background'

    if not args.no_eval_data:
        train_cmd += ' --eval'

    error = False
    if not args.skip_3dgs:
        exit_code = os.system("cd " + os.path.join('..', '..' , 'gaussian-splatting-pup') + " && " + train_cmd)
        if exit_code != 0:
            error = True
            print('An error occurred during initial training.')
        print('Done with initial training with exit code  ', exit_code)


    if not args.skip_pup and not error:
        print('Starting pup ...')
        round1 = 80
        round2 = 50
        prune_type = 'fisher'
        finetune_iterations = args.iterations + 5000
        directory1 = os.path.join(args.model, 'pup', str(round1)) if args.model else os.path.join(source, 'pup', str(round1))
        os.makedirs(directory1, exist_ok=True)
        shutil.copy(os.path.join(output_path, 'cameras.json'), os.path.join(directory1, 'cameras.json'))
        shutil.copy(os.path.join(output_path, 'cfg_args'), os.path.join(directory1, 'cfg_args'))

        print('output path', output_path)
        prune_finetune_cmd = (
            'python prune_finetune.py'
            + ' -s ' + data_path
            + ' -m ' + directory1
            + ' --start_pointcloud ' + os.path.join(output_path, 'point_cloud', 'iteration_' + str(args.iterations) + '/point_cloud.ply')
            + ' --prune_percent ' + str(round1 / 100.0)
            + ' --iterations ' + str(finetune_iterations)
            + ' --save_iterations ' + str(finetune_iterations)
            + ' --checkpoint_iterations 0'
            + ' --test_iterations 0'
            + ' --prune_type ' + prune_type
            + ' --fisher_resolution 4'
            + ' --sh_degree 0'
            + ' --resolution 1'
            + ' --first_iter ' + str(args.iterations)
        )
        if args.white_background:
            prune_finetune_cmd += ' --white_background'
        if not args.no_eval_data:
            prune_finetune_cmd += ' --eval'

        exit_code_pup1  = os.system("cd " + os.path.join('..', '..', 'gaussian-splatting-pup') + " && " + prune_finetune_cmd)

        directory2 = os.path.join(args.model, 'pup', str(round2)) if args.model else os.path.join(source, 'pup' , str(round2))
        os.makedirs(directory2, exist_ok=True)
        shutil.copy(os.path.join(output_path, 'cameras.json'), os.path.join(directory2, 'cameras.json'))
        shutil.copy(os.path.join(output_path, 'cfg_args'), os.path.join(directory2, 'cfg_args'))

        finetune_2_cmd = (
            'python prune_finetune.py'
            + ' -s ' + data_path
            + ' -m ' + directory2
            + ' --start_pointcloud ' + os.path.join(directory1, 'point_cloud', 'iteration_' + str(finetune_iterations) + '/point_cloud.ply')
            + ' --prune_percent ' + str(round2 / 100.0)
            + ' --iterations ' + str(finetune_iterations)
            + ' --save_iterations ' + str(finetune_iterations)
            + ' --checkpoint_iterations 0'
            + ' --test_iterations 0'
            + ' --prune_type ' + prune_type
            + ' --fisher_resolution 4'
            + ' --first_iter ' + str(args.iterations)
            + ' --sh_degree 0'
            + ' --resolution 1'
        )
        if args.white_background:
            finetune_2_cmd += ' --white_background'
        if not args.no_eval_data:
            finetune_2_cmd += ' --eval'

        exit_code_pup2 = os.system("cd " + os.path.join('..', '..', 'gaussian-splatting-pup') + " && " + finetune_2_cmd)

        print('Done with pup with exit code  ', exit_code_pup1, exit_code_pup2)

    # moving camera files to all output folders
    cameras_output = os.path.join(output_path, 'cameras.json')
    cameras_info = os.path.join(source, 'data', 'camera_info.json')
    for src_json in [cameras_output, cameras_info]:
        if os.path.exists(os.path.join(output_path, 'point_cloud', 'iteration_7000')):
            shutil.copy(src_json, os.path.join(output_path, 'point_cloud', 'iteration_7000'))
        if os.path.exists(os.path.join(output_path, 'point_cloud', 'iteration_30000')):
            shutil.copy(src_json, os.path.join(output_path, 'point_cloud', 'iteration_30000'))
        if (args.iterations != 30000 and
                os.path.exists(os.path.join(output_path, 'point_cloud', 'iteration_'+ str(args.iterations)))):
            shutil.copy(src_json, os.path.join(output_path, 'point_cloud', 'iteration_'+ str(args.iterations)))
        pup_out_path = os.path.join(args.model, 'pup') if args.model else os.path.join(source, 'pup')
        if os.path.exists(pup_out_path):
            shutil.copy(src_json, os.path.join(pup_out_path, '50', 'point_cloud', 'iteration_' + str(finetune_iterations)))
            shutil.copy(src_json, os.path.join(pup_out_path, '80', 'point_cloud', 'iteration_' + str(finetune_iterations)))

    print('Elapsed time:', time.time() - start_time)