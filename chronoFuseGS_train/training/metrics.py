import argparse
import json
import os
import piq
from torchvision import transforms
from PIL import Image

def compute_metrics(model_path, iteration_name):
    psnr_vals = []
    ssim_vals = []
    lpips_vals = []

    gt_folder = os.path.join(model_path, 'test', iteration_name, 'gt')
    rendered_folder = os.path.join(model_path, 'test', iteration_name, 'renders')
    lpips_metric = piq.LPIPS().to('cuda')
    to_tensor = transforms.ToTensor()

    for filename in os.listdir(gt_folder):
        render_path = os.path.join(rendered_folder, filename)
        gt_path = os.path.join(gt_folder, filename)

        gt_image = to_tensor(Image.open(gt_path)).unsqueeze(0).to('cuda')
        render_image = to_tensor(Image.open(render_path)).unsqueeze(0).to('cuda')

        psnr_val = piq.psnr(render_image, gt_image, data_range=1.0)
        ssim_val = piq.ssim(render_image, gt_image, data_range=1.0)
        lpips_val = lpips_metric(render_image, gt_image)
        psnr_vals.append(psnr_val.item())
        ssim_vals.append(ssim_val.item())
        lpips_vals.append(lpips_val.item())

    return {
        "PSNR": sum(psnr_vals) / len(psnr_vals),
        "SSIM": sum(ssim_vals) / len(ssim_vals),
        "LPIPS": sum(lpips_vals) / len(lpips_vals),
        "n": len(psnr_vals),
    }

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Disaster Metrics")
    parser.add_argument('--model', '-m', type=str, required=True, default=None)
    args = parser.parse_args()
    iterations = [f.name for f in os.scandir(os.path.join(args.model, 'test')) if f.is_dir()]

    print('computing metrics for')
    results = {}

    for iteration in iterations:
        print('iteration {}'.format(iteration))
        results[iteration] = compute_metrics(args.model, iteration)

    print('saving results')
    with open(os.path.join(args.model, 'results.json'), 'w') as f:
        f.write(json.dumps(results, indent=4))
