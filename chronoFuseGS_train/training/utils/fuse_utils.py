import math
import os
import shutil

import numpy as np


def regit_transformation(a_src, b_src):
    """
    a -> b
    """
    print('finding regit transformation...')
    # a -> b
    a = a_src.copy()
    b = b_src.copy()

    R = np.eye(4, dtype=np.float64)
    scale = np.ones(4, dtype=np.float64)
    translate = np.zeros(4, dtype=np.float64)
    T = np.eye(4)
    T[:, 3] = 1
    if len(a) == 0 or len(b) == 0:
        print('Error could not find regit transformation\n  because no points provided')
        return scale, R, translate, T

    # https://roboticsknowledgebase.com/wiki/math/registration-techniques/#:~:text=Horn's%20method%20is%20a%20useful,to%20the%20absolute%20orientation%20problem.s
    centroid_a = np.mean(a, axis=0, dtype=np.float64)
    centroid_b = np.mean(b, axis=0, dtype=np.float64)

    a = a - centroid_a
    b = b - centroid_b

    # check what should be squared, the sum or the norm
    a_mag = np.linalg.norm(a, axis=1)
    b_mag = np.linalg.norm(b, axis=1)
    a_mag_sum = np.sum(a_mag)**2
    b_mag_sum = np.sum(b_mag)**2
    s = math.sqrt(b_mag_sum / a_mag_sum)
    scale[:3] *= s

    #https://usmanqayyum.blogspot.com/2016/09/finding-optimal-rotation-and.html#:~:text=Where%20R%2Ct%20are%20the,Find%20the%20translation%20t
    a = a * s
    a = a.transpose()
    b = b.transpose()

    H = a @ b.transpose()

    U_mat, S_vec, V_mat = np.linalg.svd(H)

    rot_mat = V_mat.transpose() @ U_mat.transpose()
    if np.linalg.det(rot_mat) < 0:
        print('Reflected case: rotation matrix is not positive definite')
        V_mat[-1, :] *= -1
        rot_mat = V_mat.transpose() @ U_mat.transpose()

    R[:3, :3] = rot_mat.transpose()

    translate[:3] = centroid_b - scale[0] *  rot_mat @ centroid_a

    S = np.diag(np.array([scale[0], scale[1], scale[2], 1]))
    T = S @ R.transpose()
    T[:3, 3] = translate[:3]

    return scale, R, translate, T


def copy_meta_files(src_folder, to_folder):
    shutil.copy(os.path.join(src_folder, 'cameras.json'), to_folder)
    # shutil.copy(os.path.join(src_folder, 'cameras_test.json'), to_folder)
    if os.path.exists(os.path.join(os.path.join(src_folder, 'bounding_area.json'))):
        shutil.copy(os.path.join(src_folder, 'bounding_area.json'), to_folder)
