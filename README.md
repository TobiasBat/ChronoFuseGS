![Teaser](https://raw.githubusercontent.com/TobiasBat/ChronoFuseGS/main/docs/static/images/teaser.png)

# ChronoFuseGS: Multi-Temporal Gaussian Fusion with Per-Splat Persistence and Change Visualization

**Tobias Batik, Diana Marin, Peter Kán, Hannes Kaufmann — [TU Wien, Austria](https://www.vr.tuwien.ac.at/)**

[[Project Page]](https://tobiasbat.github.io/ChronoFuseGS/)


ChronoFuseGS fuses individually trained Gaussian Splatting models across multiple timesteps into a single combined model. It encodes per-Gaussian persistence — whether each Gaussian contributes to the reconstruction at other timesteps — and uses this to highlight scene changes at sub-object granularity while preserving the appearance of persistent parts.

This repository contains the code accompanying the ChronoFuseGS paper, primarily intended to reproduce the results reported in the paper.

## Dataset

The paper is evaluated on the **No Wolf in the Meadow (NWM)** dataset, a real-world outdoor image dataset captured over 8 recording days across 6.5 months. See [`NWM_dataset/`](https://github.com/TobiasBat/ChronoFuseGS/tree/main/NWM_dataset) for documentation.

## Training

The `chronoFuseGS_train` folder contains the code to create multi-temporal models. The pipeline covers three stages: preparing and training the individual timesteps, fusing and refining the multi-temporal model, and evaluating the results.

### Preparing Individual Timesteps

`convert.py` converts videos or source images into a COLMAP reconstruction. It reads input from `<model-folder>/data/src-data` and writes the COLMAP model and undistorted images into the `data` folder.

```
conda activate chronofuse
python convert.py --parse_video -s <model-folder>
```

The resulting COLMAP model is then used to train a single-timestep Gaussian Splatting model. `initial_train.py` uses Pup 3D-GS for this step.

```
conda activate pup
python initial_train.py --random_bg --large_scale -s <model-folder>
```

<br>

### Multi-Temporal Gaussian Fusion

`merge.py` takes the individually pre-trained Gaussian models and creates an initial multi-temporal model. It produces a combined `point_cloud.ply` containing all Gaussians from all timesteps, as well as an `activation.ply` file. This per-Gaussian data encodes each Gaussian's contribution across timesteps — referred to as the opacity manipulation vector `o` in the paper.

```
conda activate chronofuse
python merge.py --pup -s <timestep-model-1> <timestep-model-2> <timestep-model-3> -m <output-model>
```

`-s` accepts paths to individual timestep models from `initial_train.py`, or already-refined multi-temporal models from a previous `train.py` or `merge.py` run. With `--pup`, models from the `<src-model>/pup` directory are used instead of the default output.

To refine the resulting multi-temporal model:

```
python train.py -i 5000 --validation_it 2000 --save_steps --large_scale --iter_init 1000 -s <output-model>
```

<br>

### Evaluation

To render the test views and compute metrics:

```
python render.py -i 0 6000 -s <model>
python metrics.py -m <model>/output
```

Results are written to `output/results.json`.

To reproduce the per-timestep comparison scores from Table 2 of the paper, run `metrics_compare.py` with the individually trained single-timestep models that have been refined with additional training iterations:

```
python metrics_compare.py -m <timestep-model-1>/comp_36000/pup/50 <timestep-model-2>/comp_36000/pup/50 ... -o <output>.json
```

