import argparse
import json
import os

from metrics import compute_metrics

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Compare")
    parser.add_argument('--models', '-m',  nargs="+",  type=str, required=True, default=None)
    parser.add_argument('--output', '-o', type=str, required=True, default=None)


    args = parser.parse_args()
    all_results = []

    for model in args.models:
        iterations = [f.name for f in os.scandir(os.path.join(model, 'test')) if f.is_dir()]
        results = {}

        for iteration in iterations:
            print('iteration {}'.format(iteration))
            results[iteration] = compute_metrics(model, iteration)
        all_results.append({
            'model': model,
            'results': results,
        })

    # combuting weighted average aff all the individual
    combined_results = {
        "PSNR": 0,
        "SSIM": 0,
        "LPIPS": 0,
        "n": 0,
    }

    for single_t_result in all_results:
        print(single_t_result)
        model_key = list(single_t_result['results'].keys())[0] # only works if there is only one
        combined_results['n'] += single_t_result['results'][model_key]['n']
    for single_t_result in all_results:
        model_key = list(single_t_result['results'].keys())[0]
        combined_results['PSNR'] += single_t_result['results'][model_key]['PSNR'] * single_t_result['results'][model_key]['n'] / combined_results['n']
        combined_results['SSIM'] += single_t_result['results'][model_key]['SSIM'] * single_t_result['results'][model_key]['n'] / combined_results['n']
        combined_results['LPIPS'] += single_t_result['results'][model_key]['LPIPS'] * single_t_result['results'][model_key]['n'] / combined_results['n']

    print('saving results')
    all_results.append({
        'model': 'combined',
        'results': combined_results
    })

    with open(os.path.join(args.output), 'w') as f:
        f.write(json.dumps(all_results, indent=4))