<img src="camera_positions_overview/nwm_preview.jpg" width="100%"/>

# No Wolf in the Meadow (NWM)

**No Wolf in the Meadow (NWM)** is a real-world outdoor image dataset of a flood control system in Vienna, Austria. The site covers approximately 100 × 200 meters and includes weir and flood control structures built from stone, wood, steel, and concrete, multiple river branches, and surrounding vegetation.

The dataset spans **8 recording days over 6.5 months** (August 2025 – March 2026), capturing the site through seasonal vegetation changes, snow cover, flooding events, and active reinforcement and renovation work. All recordings were made with a consumer drone following pre-recorded flight plans, with 4K video exported as frames at regular intervals and downscaled to 1600 × 900 pixels. The dataset also includes detailed close-up recordings of specific scene areas.



[![Download](https://img.shields.io/badge/Download-Images_%26_Pretrained_Models-blue?style=for-the-badge)](https://researchdata.tuwien.ac.at/records/bphp1-hbb20?preview=1&token=eyJhbGciOiJIUzUxMiJ9.eyJpZCI6IjNlZDQ1MjU0LTVkNTgtNDhiMC1iZWNiLTUwZWI3YTBlOGEwZSIsImRhdGEiOnt9LCJyYW5kb20iOiIxMDc1MjkwMjllZDZkYTI3MTk4MWEzM2NmZTUyNjEyMSJ9.pdNR3yUrDWgqszzUXQz2TRMaw3jeviigoN0QLYMOLySXrHPnM4ABcjcu4anHbH4d6LHOx3rdGeN7yxaiKi1lPg)



## Provided Files

The dataset is distributed as individual zip archives. Three types of archives are provided:

- **`nwm_<YYYY-MM-DD>.zip`** — Images and camera info (`camera_info.json`) for a single timestep.
- **`nwm_pre_trained_timestep_<YYYY-MM-DD>.zip`** — COLMAP model and pretrained 3DGS and PuP-3DGS models for a single timestep, used as input for ChronoFuseGS.
- **`nwm_<subset>.zip`** — Multi-temporal model trained and fused with ChronoFuseGS for a given subset (`complete`, `autumn`, `flooding`, `snow`, `car`).



## Individual Timesteps

We split the data into 11 timesteps in total. The two detail timesteps recorded at 2026-01-10 (`2026-01-10_detail_1`, `2026-01-10_detail_2`) are only included in the Snow subset. The list of timesteps is shown below:

| Timestep            | Number of Input Images | Environmental Conditions        |
| ------------------- | ---------------------: | ------------------------------- |
| 2025-08-25          |                    226 | Green vegetation                |
| 2025-11-11          |                    271 | Autumn foliage                  |
| 2025-11-22          |                    255 | Bare trees                      |
| 2025-11-23          |                    283 | Bare trees, light snow, sunset  |
| 2025-12-04_1        |                    284 | Bare trees                      |
| 2025-12-04_2        |                    198 | Bare trees                      |
| 2025-12-08          |                    223 | Bare trees                      |
| 2026-01-10          |                    273 | Snow cover                      |
| 2026-01-10_detail_1 |                    180 | Snow cover                      |
| 2026-01-10_detail_2 |                    155 | Snow cover                      |
| 2026-03-28          |                    208 | Early spring, bare trees, flooding |

Each timestep's image set is split into training and test images. Every 8th image is held out as a test image; the remaining images are used for training. The `type` field in `camera_info.json` indicates the split for each image (`"train"` or `"test"`).

## Multi-Temporal Models

We grouped these individual timesteps into the multi-timestep datasets of NWM, including the _Complete_ dataset which covers all recording days, and smaller focused subsets. The table includes the number of registered images in the combined multi-timestep models.

| Subset   | Num T. | Days | Timesteps                                                    | Registered Images |
| -------- | -----: | ---: | ------------------------------------------------------------ | ----------------: |
| Complete |      9 |    8 | `2025-08-25`, `2025-11-11`, `2025-11-22`,<br />`2025-11-23`, `2025-12-04_1`, `2025-12-04_2`,<br />`2025-12-08`, `2026-01-10`, `2026-03-28` |             2,221 |
| Autumn   |      4 |    4 | `2025-08-25`, `2025-11-11`,<br />`2025-11-22`, `2025-12-08`  |               975 |
| Flooding |      3 |    3 | `2025-12-04_2`, `2025-12-08`, `2026-03-28`                   |               629 |
| Snow     |      3 |    1 | `2026-01-10`, `2026-01-10_detail_1`,<br /> `2026-01-10_detail_2` |               608 |
| Car      |      3 |    1 | `2025-12-04_1`, `2025-12-04_2`, `2025-12-08`                 |               705 |

## Camera Positions

We extracted GPS coordinates from the camera logs and provide per-image coordinate information in the corresponding `camera_info.json` file.

```json
[
    {
        "image": "006_DJI_20250829153742_0593_D_1.png",
        "video_frame": 60,
        "src_video": "006_DJI_20250829153742_0593_D.MP4",
        "latitude": 48.206373,
        "longitude": 16.230399,
        "rel_alt": 20.0,
        "abs_alt": 317.406,
        "ecef": [4089114.54278001, 1190350.6104078596, 4732436.830631929],
        "registered": true,
        "type": "test",
        "t": 0
    },
    {
        "image": "006_DJI_20250829153742_0593_D_2.png",
        "video_frame": 180,
        "src_video": "006_DJI_20250829153742_0593_D.MP4",
        "latitude": 48.206436,
        "longitude": 16.2306,
        "rel_alt": 20.0,
        "abs_alt": 317.406,
        "ecef": [4089105.352015008, 1190363.495616108, 4732441.499502797],
        "registered": true,
        "type": "train",
        "t": 0
    },
    ...
]
```

An overview of the camera positions for each subset is shown below.

### Complete

<img src="camera_positions_overview/cameras_NWM_Complete_t0_t1_t2.jpg" width="600"/>
<img src="camera_positions_overview/cameras_NWM_Complete_t3_t4_t5.jpg" width="600"/>
<img src="camera_positions_overview/cameras_NWM_Complete_t6_t7_t8.jpg" width="600"/>

### Autumn

<img src="camera_positions_overview/cameras_NWM_Autumn_t0_t1_t2_t3.jpg" width="600"/>

### Flooding

<img src="camera_positions_overview/cameras_NWM_Flood_t0_t1_t2.jpg" width="600"/>

### Snow

<img src="camera_positions_overview/cameras_NWM_Snow_Large_t0_t1_t2.jpg" width="600"/>

### Car

<img src="camera_positions_overview/cameras_NWM_Car_t0_t1_t2.jpg" width="600"/>



## Computing Multi-Temporal Models

The following commands compute the combined multi-temporal models using ChronoFuseGS. Run from the repository root. All commands use 6,000 refinement iterations. For more detailed instructions on how to run the code, have a look at the root README.md of the repository.

**Complete**

```bash
python merge.py --pup -s ..\..\timesteps\2025-08-25 ..\..\timesteps\2025-11-11 ..\..\timesteps\2025-11-22 ..\..\timesteps\2025-11-23 ..\..\timesteps\2025-12-04_1 ..\..\timesteps\2025-12-04_2 ..\..\timesteps\2025-12-08 ..\..\timesteps\2026-01-10 ..\..\timesteps\2026-03-28 -m ..\..\models\complete
python train.py -i 6000 --validation_it 2000 --save_steps --large_scale -s ..\..\models\complete
```

**Autumn**

```bash
python merge.py --pup -s ..\..\timesteps\2025-08-25 ..\..\timesteps\2025-11-11 ..\..\timesteps\2025-11-22 ..\..\timesteps\2025-12-08 -m ..\..\models\autumn
python train.py -i 6000 --validation_it 2000 --save_steps --large_scale -s ..\..\models\autumn
```

**Flooding**

```bash
python merge.py --pup -s ..\..\timesteps\2025-12-04_2 ..\..\timesteps\2025-12-08 ..\..\timesteps\2026-03-28 -m ..\..\models\flooding
python train.py -i 6000 --validation_it 2000 --save_steps --large_scale -s ..\..\models\flooding
```

**Snow**

```bash
python merge.py --pup -s ..\..\timesteps\2026-01-10 ..\..\timesteps\2026-01-10_detail_1 ..\..\timesteps\2026-01-10_detail_2 -m ..\..\models\snow
python train.py -i 6000 --validation_it 2000 --save_steps --large_scale -s ..\..\models\snow
```

**Car**

```bash
python merge.py --pup -s ..\..\timesteps\2025-12-04_1 ..\..\timesteps\2025-12-04_2 ..\..\timesteps\2025-12-08 -m ..\..\models\car
python train.py -i 6000 --validation_it 2000 --save_steps --large_scale -s ..\..\models\car
```
