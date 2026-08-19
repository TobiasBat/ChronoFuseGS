"""
Utility to handle Activation Data. Notice that in the ChronoFuseGS we
refer to this data as the opacity manipulation vector. Altering alpha
per timestep.
"""

from __future__ import annotations

import json
import math
import os

import numpy as np
from numpy.typing import NDArray
from plyfile import PlyElement, PlyData


class ActivationData:
    num_gaussians: int
    num_t: int
    _opacity: NDArray = None
    _color: NDArray = None

    def __init__(self, num_gaussians: int, src_path: str = None, num_timesteps: int = 1, turned_off: bool = False):
        self.num_gaussians = num_gaussians
        self.num_t = num_timesteps

        if src_path is not None and os.path.isfile(src_path):
            if src_path.endswith('.ply'):
                self._read_ply(src_path)
            else:
                self._read(src_path)
            self.num_t = self._opacity.shape[1]

            if self.num_gaussians != self._opacity.shape[0]:
                raise ValueError('Num Gaussians in activation file does not match')

        else:
            self._opacity = self._default_parm(
                num_gaussians,
                num_timesteps=num_timesteps,
                value= -math.e * 2 if turned_off else math.e * 2,
                values_per_time=1
            )
            self._color = self._default_parm(
                num_gaussians,
                num_timesteps=num_timesteps,
                value=0,
                values_per_time=3
            )

    def write(self, point_cloud_folder: str, nice=False):
        self.write_activation_data(
            None,
            filepath_ply=os.path.join(point_cloud_folder, "activation.ply"),
            opacity=self._opacity,
            color=self._color,
            nice=nice
        )


    @property
    def get_color_mat(self):
        return self._color

    def _read(self, filepath):  # legacy JSON reader
        with open(filepath, 'r') as file:
            json_data = json.load(file)

        if len(json_data['opacity']) * 3 != len(json_data['color']):
            raise ValueError(
                'Num Values in activation file does not match',
                len(json_data['opacity']) * 3,
                len(json_data['color'])
            )

        num_gaussians = int(len(json_data['opacity']) / json_data['number_of_steps'])
        num_t = json_data['number_of_steps']

        opt = np.array(json_data['opacity'])
        col = np.array(json_data['color'])

        self._opacity = opt.reshape(num_gaussians, num_t)
        self._color = col.reshape(num_gaussians, num_t * 3)

        print('number of steps: ', num_t)
        print('Shape of opacity: ', self._opacity.shape)
        print('Shape of color: ', self._color.shape)
        print()

    def _read_ply(self, filepath):
        plydata = PlyData.read(filepath)
        vertex = plydata['vertex']
        names = vertex.data.dtype.names
        num_t = sum(1 for n in names if n.startswith('opacity_'))

        self._opacity = np.stack([vertex[f'opacity_{t}'] for t in range(num_t)], axis=1).astype(np.float32)
        color_cols = []
        for t in range(num_t):
            color_cols += [vertex[f'color_r_{t}'], vertex[f'color_g_{t}'], vertex[f'color_b_{t}']]
        self._color = np.stack(color_cols, axis=1).astype(np.float32)

        print('number of steps: ', num_t)
        print('Shape of opacity: ', self._opacity.shape)
        print('Shape of color: ', self._color.shape)
        print()

    @staticmethod
    def _default_parm(num_gaussians, value=math.e * 2, num_timesteps=1, values_per_time=1):
        data = np.full((num_gaussians, num_timesteps * values_per_time), value)
        return data

    @staticmethod
    def combine(act1: ActivationData, act2: ActivationData) -> ActivationData:
        """
        Function to create a combined activation data from two srcs
        Times that are not defined are set to -math.e * 2
        """
        combined = ActivationData(
            act1.num_gaussians + act2.num_gaussians,
            num_timesteps=act1.num_t + act2.num_t,
            turned_off=True
        )

        combined._opacity[:act1.num_gaussians, :act1.num_t] = act1._opacity
        combined._opacity[act1.num_gaussians:, act1.num_t:] = act2._opacity

        combined._color[:act1.num_gaussians, :act1.num_t * 3] = act1._color
        combined._color[act1.num_gaussians:, act1.num_t * 3:] = act2._color

        return combined

    @staticmethod
    def combine_multiple(activation_datas: list[ActivationData]) -> ActivationData:
        combined_activation = None
        for index, activationData in enumerate(activation_datas):
            print(index)
            if index == 0:
                pass
            elif index == 1:
                combined_activation = ActivationData.combine(activation_datas[index - 1], activation_datas[index])
            else:
                combined_activation = ActivationData.combine(combined_activation, activation_datas[index])
        return combined_activation

    @staticmethod
    def write_activation_data(
            filepath: str,
            filepath_ply: str = None,
            opacity: NDArray = None,
            color: NDArray = None,
            nice=False
    ):
        print('Writing activations data...')
        time_data = {}

        if opacity is not None:
            time_data['number_of_steps'] = opacity.shape[1]
            time_data['opacity'] = opacity.flatten().tolist()

        if color is not None:
            time_data['color'] = color.flatten().tolist()
        else:
            print('No color_r specified')

        if filepath is not None:
            with open(filepath, "w") as file:
                if nice:
                    file.write(json.dumps(time_data, indent=4))
                else:
                    file.write(json.dumps(time_data))


        if filepath_ply is not None and opacity is not None and color is not None:
            print('Writing to Ply File')
            attributes = []
            for t in range(0, opacity.shape[1]):
                attributes.append('opacity_' + str(t))
            for t in range(0, opacity.shape[1]):
                attributes.append('color_r_' + str(t))
                attributes.append('color_g_' + str(t))
                attributes.append('color_b_' + str(t))

            dtype_full = [(attribute, 'f4') for attribute in attributes]
            print('Writing to Ply File with Attributes', attributes)
            elements = np.empty(opacity.shape[0], dtype=dtype_full)
            attribute_values = np.concatenate((opacity, color), axis=1)
            for i, attr in enumerate(attributes):
                elements[attr] = attribute_values[:, i]

            el = PlyElement.describe(elements, 'vertex')
            PlyData([el]).write(filepath_ply)