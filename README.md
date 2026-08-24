![Teaser](https://raw.githubusercontent.com/TobiasBat/ChronoFuseGS/main/docs/static/images/teaser.png)

# ChronoFuseGS: Multi-Temporal Gaussian Fusion with Per-Splat Persistence and Change Visualization

**Tobias Batik, Diana Marin, Peter Kán, Hannes Kaufmann — [TU Wien, Austria](https://www.vr.tuwien.ac.at/)**

[[Project Page]](https://tobiasbat.github.io/ChronoFuseGS/)


ChronoFuseGS fuses individually trained Gaussian Splatting models across multiple timesteps into a single combined model. It encodes per-Gaussian persistence — whether each Gaussian contributes to the reconstruction at other timesteps — and uses this to highlight scene changes at sub-object granularity while preserving the appearance of persistent parts.

This repository contains the code accompanying the ChronoFuseGS paper, primarily intended to reproduce the results reported in the paper.

<br>
<br>

## Dataset

The paper is evaluated on the **No Wolf in the Meadow (NWM)** dataset, a real-world outdoor image dataset captured over 8 recording days across 6.5 months. See [`NWM_dataset/`](https://github.com/TobiasBat/ChronoFuseGS/tree/main/NWM_dataset) for documentation.


<br>
<br>

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

<br>
<br>

## Change Visualization

The ChronoFuseGS change visualization is implemented in Unreal Engine 5.6. The code has only been tested in that Unreal version on Windows. The [`chronoFuseGS_change_visualization`](chronoFuseGS_change_visualization) directory contains the Unreal project.

To display a multi-temporal scene, open a Level and set the `Model Folder Path` on the `BP_SplattingActor` to the point cloud directory of the trained multi-temporal model (e.g. `<output-model>/output/point_cloud/refined_30000`). Note: currently only spherical harmonics degree 0 is supported.

On the `SplattingActor`, the `Activation Selection` array lets timesteps be turned on and off individually (`1` turned on, `0` turned off). The render mode can also be selected directly: `2` for change highlighting and `0` for true color.

The scene can be navigated with `W`, `A`, `S`, `D` and the mouse to look around. The following keyboard shortcuts are supported:

| Key | Action |
|---|---|
| `0` | True color render mode |
| `2` | Change highlighting render mode |
| `J` / `K` | Previous / next test camera |
| `Page Up` / `Page Down` | Select next / previous timestep (only one timestep is selected at a time, all others are deselected) |
| `T` | Activate all timesteps |
| `H` | FPV camera |
| `F` | Start FPS test |
| `O` | Orbit around the scene |
| `+` | Toggle orbit distance (only while orbiting) |
| `R` | Take a screenshot (only works when a `ScreenCapturer` actor is present in the scene) |


