from typing import NamedTuple


class GaussiansLearningRate(NamedTuple):
    opacity_activation: float = 0.0025 / 1000
    opacities: float = 0.005
    mean: float = 0.00016
    others: float = 0.00005
    dc: float = 0.00002
    color_activation: float = 0.0


DEFAULT_LR = GaussiansLearningRate()

LARGE_SCALE_LR = GaussiansLearningRate(
    opacity_activation=DEFAULT_LR.opacity_activation,
    opacities=DEFAULT_LR.opacities,
    mean=DEFAULT_LR.mean / 10,
    others=DEFAULT_LR.others,
    dc=DEFAULT_LR.dc,
    color_activation=DEFAULT_LR.color_activation,
)

CROSS_TIMESTEP_INIT_LR = GaussiansLearningRate(
    opacity_activation=0.0075,
    opacities=0.0,
    mean=0.0,
    others=0.0,
    dc=0.0,
    color_activation=0.00375,
)
