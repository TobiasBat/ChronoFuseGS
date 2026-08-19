import argparse
import os
import sys

from plyfile import PlyData

def format_num_gauss(num):
    return round(num/1e6, 2)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Disaster Renderer")
    parser.add_argument('--models', '-m', type=str, required=True, nargs="+")
    args = parser.parse_args(sys.argv[1:])

    sum_gauss = 0
    for model in args.models:
        if not os.path.exists(model):
            print(f"Model {model} does not exist")
        elif os.path.exists(os.path.join(model, 'point_cloud.ply')):
                model = os.path.join(model, 'point_cloud.ply')
        elif os.path.exists(os.path.join(model, 'point_cloud', 'iteration_35000', 'point_cloud.ply')):
                model = os.path.join(model, 'point_cloud', 'iteration_35000', 'point_cloud.ply')
        ply = PlyData.read(os.path.join(model))
        num_gauss = len(ply['vertex']['x'])
        sum_gauss += num_gauss

        print('Num Gaussians '+model+':', format_num_gauss(num_gauss))

    if len(args.models) > 0:
        print('Sum of models: ', format_num_gauss(sum_gauss))