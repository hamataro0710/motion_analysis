import pandas as pd
import numpy as np
from scipy.spatial import distance

# from tf-pose-estimation.tf_pose.common import CocoPart


def calc_cog(segments, rates):
    """
    :param segments:
    :param rates:
    :return: center of gravity; this reflects segments' score > 0 or not to reflect occlusion.
    """
    # seg_cog = (np.dot(np.multiply(rates, segments[:, 2]), segments[:, :2])) / np.dot(segments[:, 2], np.array(rates))
    rates = np.array(rates)
    if type(segments) is list:
        segments = np.array(segments)
    segments[np.isnan(segments)] = 0
    rates = [rates[num] if segments[num, 2] > 0 else 0 for num in range(len(rates))]
    # rates = rates[~np.isnan(segments[:, 2])]
    if sum(rates):
        seg_cog = (np.dot(rates, segments[:, :2])) / sum(rates)
        # print('cog_vals: ',seg_cog, '\nmean: ',np.mean(segments[:, 2]))
        seg_cog = np.append(seg_cog, np.mean(segments[:, 2]))
    else:
        seg_cog = [0,0,0]
    return seg_cog


def calc_torso_length(humans):
    torso = []
    for a_human in humans:
        if a_human[1, 2] != 0:
            neck_cog = a_human[1]
        else:
            neck_cog = calc_cog(np.vstack((a_human[2], a_human[5])), [1, 1])
        if a_human[8, 2] != 0:
            hip_cog = a_human[8]
        else:
            hip_cog = calc_cog(np.vstack((a_human[8], a_human[12])), [1, 1])
        torso.append(np.vstack((neck_cog, hip_cog)))
        torso = np.array(torso)
    length = distance.cdist(torso[:, 0, :2], torso[:, 1, :2])
    return length


def segment_cog(a_human):
    head_cog = calc_cog(a_human[15:19], [1, 1, 1, 1])
    if a_human[1, 2] != 0:
        neck_cog = a_human[1]
    else:
        neck_cog = calc_cog(np.vstack((a_human[2], a_human[5])), [1, 1])
    if a_human[8, 2] != 0:
        hip_cog = a_human[8]
    else:
        hip_cog = calc_cog(np.vstack((a_human[8], a_human[12])), [1, 1])
    torso_cog = calc_cog(np.vstack((neck_cog, hip_cog)), [1, 1])
    r_thigh_cog = calc_cog(np.vstack((a_human[9], a_human[10])), [52.5, 47.5])
    l_thigh_cog = calc_cog(np.vstack((a_human[12], a_human[13])), [52.5, 47.5])
    r_leg_cog = calc_cog(np.vstack((a_human[10], a_human[11])), [59.4, 40.6])
    l_leg_cog = calc_cog(np.vstack((a_human[13], a_human[14])), [59.4, 40.6])
    r_arm_cog = calc_cog(np.vstack((a_human[2], a_human[3])), [1, 1])
    l_arm_cog = calc_cog(np.vstack((a_human[5], a_human[6])), [1, 1])
    r_forearm_cog = calc_cog(np.vstack((a_human[3], a_human[4])), [1, 1])
    l_forearm_cog = calc_cog(np.vstack((a_human[6], a_human[7])), [1, 1])
    r_foot_cog = calc_cog(np.vstack((a_human[24], a_human[22])), [1, 1])
    l_foot_cog = calc_cog(np.vstack((a_human[21], a_human[19])), [1, 1])
    ret_cog = [head_cog, torso_cog,
               r_thigh_cog, l_thigh_cog,
               r_leg_cog, l_leg_cog,
               r_foot_cog, l_foot_cog,
               r_arm_cog, l_arm_cog,
               r_forearm_cog, l_forearm_cog,
               a_human[4], a_human[7]]
    return ret_cog


# tilt degree, base axis is Y
def calc_degree(seg1, seg2):
    vec = np.array(seg1) - np.array(seg2)
    degree = np.angle(vec[1] + vec[0] * 1j, deg=True)
    return degree


def segments_degree(a_human):
    degrees = []
    neck = a_human[1] if a_human[1, 2] != 0 else calc_cog(np.vstack((a_human[2], a_human[5])),[1.0, 1.0])  #torso
    pelvis = calc_cog(np.vstack((a_human[8], a_human[11])), [1.0, 1.0])
    degrees = [calc_degree(neck, pelvis),
               calc_cog(a_human[2], a_human[3]),
               calc_cog(a_human[3], a_human[4]),
               calc_cog(a_human[5], a_human[6]),]
    return degrees
