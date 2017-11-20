from rh_logger.api import logger
import rh_logger
import logging

import sys
import os.path
import os
import argparse
import random

from collections import defaultdict
import json

import glob
#import progressbar
import numpy as np
import scipy.sparse as spp
from scipy.sparse.linalg import lsqr
from rh_renderer import models
import time

class OptimizerRigid2D(object):
    def __init__(self, **kwargs):
        self._params = {}
        self._params["max_iterations"] = kwargs.get("max_iterations", 1000)
        self._params["max_epsilon"] = kwargs.get("max_epsilon", 5)
        self._params["step_size"] = kwargs.get("step_size", 0.1)
        self._params["damping"] = kwargs.get("damping", 0.01)  # in units of matches per pair
        self._params["avoid_empty_matches"] = True if "avoid_empty_matches" in kwargs else False

        

    @staticmethod
    def _find_rotation(p1, p2, stepsize):
        U, S, VT = np.linalg.svd(np.dot(p1, p2.T))
        R = np.dot(VT.T, U.T)
        angle = stepsize * np.arctan2(R[1, 0], R[0, 0])
        return np.array([[np.cos(angle), -np.sin(angle)],
                         [np.sin(angle),  np.cos(angle)]])


#     ### TO REMOVE?
#     @staticmethod
#     def create_new_tilespec(old_ts_fname, rotations, translations, centers, out_fname):
#         logger.report_event("Optimization done, saving tilespec at: {}".format(out_fname), log_level=logging.INFO)
#         with open(old_ts_fname, 'r') as f:
#             tilespecs = json.load(f)
# 
#         # Iterate over the tiles in the original tilespec
#         for ts in tilespecs:
#             img_url = ts["mipmapLevels"]["0"]["imageUrl"]
#             # print("Transforming {}".format(img_url))
#             if img_url not in rotations.keys():
#                 logger.report_event("Flagging out tile {}, as no rotation was found".format(img_url), log_level=logging.WARN)
#                 continue
#             # Get 4 points of the old bounding box [top_left, top_right, bottom_left, bottom_right]
#             old_bbox = [float(d) for d in ts["bbox"]]
#             old_bbox_points = [
#                 np.array([ np.array([old_bbox[0]]), np.array([old_bbox[2]]) ]),
#                 np.array([ np.array([old_bbox[1]]), np.array([old_bbox[2]]) ]),
#                 np.array([ np.array([old_bbox[0]]), np.array([old_bbox[3]]) ]),
#                 np.array([ np.array([old_bbox[1]]), np.array([old_bbox[3]]) ]) ]
#             # print("old_bbox:", old_bbox_points)
#             # convert the transformation according to the rotations data
#             # compute new bbox with rotations (Rot * (pt - center) + center + trans)
#             trans = np.array(translations[img_url])  # an array of 2 elements
#             rot_matrix = np.matrix(rotations[img_url]).T  # a 2x2 matrix
#             center = np.array(centers[img_url])  # an array of 2 elements
#             transformed_points = [np.dot(rot_matrix, old_point - center) + center + trans for old_point in old_bbox_points]
#             # print("transformed_bbox:", transformed_points)
#             min_xy = np.min(transformed_points, axis=0).flatten()
#             max_xy = np.max(transformed_points, axis=0).flatten()
#             new_bbox = [min_xy[0], max_xy[0], min_xy[1], max_xy[1]]
#             # print("new_bbox", new_bbox)
#             # compute the global transformation of the tile
#             # the translation part is just taking (0, 0) and moving it to the first transformed_point
#             delta = np.asarray(transformed_points[0].T)[0]
# 
#             x, y = np.asarray((old_bbox_points[1] - old_bbox_points[0]).T)[0]
#             new_x, new_y = np.asarray(transformed_points[1].T)[0]
#             k = (y * (new_x - delta[0]) - x * (new_y - delta[1])) / (x**2 + y**2)
#             h1 = (new_x - delta[0] - k*y)/x
#             # To overcome a bug in arccos (when h1 is wrongly above 1)
#             if h1 > 1.0:
#                 h1 = 1.0
#             new_transformation = "{} {} {}".format(np.arccos(h1), delta[0], delta[1])
#             # print("new_transformation:", new_transformation)
# 
#             # Verify the result - for debugging (needs to be the same as the new bounding box)
#             # new_matrix = np.array([ [h1, k, delta[0]],
#             #                         [-k, h1, delta[1]],
#             #                         [0.0, 0.0, 1.0]])
#             # tile_points = [np.asarray((old_bbox_points[i] - old_bbox_points[0]).T)[0] for i in range(4)]
#             # tile_points = [np.append(tile_point, [1.0], 0) for tile_point in tile_points]
#             # after_trans = [np.dot(new_matrix, tile_point) for tile_point in tile_points]
#             # print("tile 4 coordinates after_trans", after_trans)
# 
#             # Set the transformation in the tilespec
#             # TODO - use the models module from rh_renderer instead
#             ts["transforms"] = [{
#                     "className": "mpicbg.trakem2.transform.RigidModel2D",
#                     "dataString": new_transformation
#                 }]
# 
#             ts["bbox"] = new_bbox
# 
#         # Save the new tilespecs
#         with open(out_fname, 'w') as outjson:
#             json.dump(tilespecs, outjson, sort_keys=True, indent=4)
#             logger.report_event('Wrote tilespec to {0}'.format(out_fname), log_level=logging.INFO)

    @staticmethod
    def create_transforms(rotations, translations, centers, all_start_pts):
        out_models = {}
        for k in rotations.keys():
            rot = rotations[k]
            trans = translations[k]
            center = centers[k]
            start_pt = all_start_pts[k]

            # TODO - fix rotation and translation (compared to the the tile's (0,0))
            # The matrix is going to be as follows: move the tile so its "center point" will be in (0,0), rotate it, and then move it to the start point
            t1 = start_pt - center
            new_delta = np.dot(rot.T, t1) + center + trans
            new_model = models.Transforms.create(1) # Creating a rigid model
            new_model.set(np.arccos(rot[0][0]), new_delta)
            out_models[k] = new_model

        return out_models

#         logger.report_event("Optimization done, saving tilespec at: {}".format(out_fname), log_level=logging.INFO)
#         with open(old_ts_fname, 'r') as f:
#             tilespecs = json.load(f)
# 
#         # Iterate over the tiles in the original tilespec
#         for ts in tilespecs:
#             img_url = ts["mipmapLevels"]["0"]["imageUrl"]
#             # print("Transforming {}".format(img_url))
#             if img_url not in rotations.keys():
#                 logger.report_event("Flagging out tile {}, as no rotation was found".format(img_url), log_level=logging.WARN)
#                 continue
#             # Get 4 points of the old bounding box [top_left, top_right, bottom_left, bottom_right]
#             old_bbox = [float(d) for d in ts["bbox"]]
#             old_bbox_points = [
#                 np.array([ np.array([old_bbox[0]]), np.array([old_bbox[2]]) ]),
#                 np.array([ np.array([old_bbox[1]]), np.array([old_bbox[2]]) ]),
#                 np.array([ np.array([old_bbox[0]]), np.array([old_bbox[3]]) ]),
#                 np.array([ np.array([old_bbox[1]]), np.array([old_bbox[3]]) ]) ]
#             # print("old_bbox:", old_bbox_points)
#             # convert the transformation according to the rotations data
#             # compute new bbox with rotations (Rot * (pt - center) + center + trans)
#             trans = np.array(translations[img_url])  # an array of 2 elements
#             rot_matrix = np.matrix(rotations[img_url]).T  # a 2x2 matrix
#             center = np.array(centers[img_url])  # an array of 2 elements
#             transformed_points = [np.dot(rot_matrix, old_point - center) + center + trans for old_point in old_bbox_points]
#             # print("transformed_bbox:", transformed_points)
#             min_xy = np.min(transformed_points, axis=0).flatten()
#             max_xy = np.max(transformed_points, axis=0).flatten()
#             new_bbox = [min_xy[0], max_xy[0], min_xy[1], max_xy[1]]
#             # print("new_bbox", new_bbox)
#             # compute the global transformation of the tile
#             # the translation part is just taking (0, 0) and moving it to the first transformed_point
#             delta = np.asarray(transformed_points[0].T)[0]
# 
#             x, y = np.asarray((old_bbox_points[1] - old_bbox_points[0]).T)[0]
#             new_x, new_y = np.asarray(transformed_points[1].T)[0]
#             k = (y * (new_x - delta[0]) - x * (new_y - delta[1])) / (x**2 + y**2)
#             h1 = (new_x - delta[0] - k*y)/x
#             # To overcome a bug in arccos (when h1 is wrongly above 1)
#             if h1 > 1.0:
#                 h1 = 1.0
#             new_transformation = "{} {} {}".format(np.arccos(h1), delta[0], delta[1])
#             # print("new_transformation:", new_transformation)
# 
#             # Verify the result - for debugging (needs to be the same as the new bounding box)
#             # new_matrix = np.array([ [h1, k, delta[0]],
#             #                         [-k, h1, delta[1]],
#             #                         [0.0, 0.0, 1.0]])
#             # tile_points = [np.asarray((old_bbox_points[i] - old_bbox_points[0]).T)[0] for i in range(4)]
#             # tile_points = [np.append(tile_point, [1.0], 0) for tile_point in tile_points]
#             # after_trans = [np.dot(new_matrix, tile_point) for tile_point in tile_points]
#             # print("tile 4 coordinates after_trans", after_trans)
# 
#             # Set the transformation in the tilespec
#             # TODO - use the models module from rh_renderer instead
#             ts["transforms"] = [{
#                     "className": "mpicbg.trakem2.transform.RigidModel2D",
#                     "dataString": new_transformation
#                 }]
# 
#             ts["bbox"] = new_bbox
# 
#         # Save the new tilespecs
#         with open(out_fname, 'w') as outjson:
#             json.dump(tilespecs, outjson, sort_keys=True, indent=4)
#             logger.report_event('Wrote tilespec to {0}'.format(out_fname), log_level=logging.INFO)



    def optimize_2d_tiles(self, all_matches, all_pts, all_start_pts, optimized_section_id=""):
        # Find centers of each group of points
        centers = {k: np.mean(np.vstack(pts).T, axis=1, keepdims=True) for k, pts in all_pts.items()}
        # a unique index for each url
        url_idx = {url: idx for idx, url in enumerate(all_pts)}

        prev_meanmed = np.inf

        T = defaultdict(lambda: np.zeros((2, 1)))
        R = defaultdict(lambda: np.eye(2))
        stepsize = self._params["step_size"]
        for iter in range(self._params["max_iterations"]):
            # transform points by the current trans/rot
            trans_matches = {(k1, k2): (np.dot(R[k1], p1.T - centers[k1]) + T[k1] + centers[k1],
                                        np.dot(R[k2], p2.T - centers[k2]) + T[k2] + centers[k2])
                             for (k1, k2), (p1, p2) in all_matches.items()}

            # mask off all points more than epsilon past the median
            diffs = {k: p2 - p1 for k, (p1, p2) in trans_matches.items()}
            distances = {k: np.sqrt((d ** 2).sum(axis=0)) for k, d in diffs.items()}
            masks = {k: d < (np.median(d) + self._params["max_epsilon"]) for k, d in distances.items()}
            masked_matches = {k: (p1[:, masks[k]], p2[:, masks[k]]) for k, (p1, p2) in trans_matches.items()}

            median_dists = [np.median(d) for d in distances.values()]
            medmed = np.median(median_dists)
            meanmed = np.mean(median_dists)
            maxmed = np.max(median_dists)
            logger.report_event("med-med distance: {}, mean-med distance: {}  max-med: {}  SZ: {}".format(medmed, meanmed, maxmed, stepsize), log_level=logging.INFO)
            logger.report_metric("Optimize2d_med_med_distance", medmed, context=[optimized_section_id, iter])
            logger.report_metric("Optimize2d_mean_med_distance", meanmed, context=[optimized_section_id, iter])
            logger.report_metric("Optimize2d_max_med_distance", maxmed, context=[optimized_section_id, iter])
            if meanmed < prev_meanmed:
                stepsize *= 1.1
                if stepsize > 1:
                    stepsize = 1
            else:
                stepsize *= 0.5

            # Find optimal translations
            #
            # Build a sparse matrix M of c/0/-c for differences between match sets,
            # where c is the size of each match set, and a vector D of sums of
            # differences, and then solve for T:
            #    M * T = D
            # to get the translations (independently in x and y).
            #
            # M is IxJ, I = number of match pairs, J = number of tiles
            # T is Jx2, D is Ix2  (2 for x, y)

            # two nonzero entries per match set
            rows = np.hstack((np.arange(len(diffs)), np.arange(len(diffs))))
            cols = np.hstack(([url_idx[url1] for (url1, url2) in diffs],
                              [url_idx[url2] for (url1, url2) in diffs]))
            # diffs are p2 - p1, so we want a positive value on the translation for p1,
            # e.g., a solution could be Tp1 == p2 - p1.
            Mvals = np.hstack(([pts.shape[1] for pts in diffs.values()],
                              [-pts.shape[1] for pts in diffs.values()]))
            logger.report_event("solving", log_level=logging.DEBUG)
            M = spp.csr_matrix((Mvals, (rows, cols)))

            # We use the sum of match differences
            D = np.vstack([d.sum(axis=1) for d in diffs.values()])
            oTx = lsqr(M, D[:, :1], damp=self._params["damping"])[0]
            oTy = lsqr(M, D[:, 1:], damp=self._params["damping"])[0]
            for k, idx in url_idx.items():
                T[k][0] += oTx[idx]
                T[k][1] += oTy[idx]

            # first iteration is translation only
            if iter == 0:
                continue

            # don't update Rotations on last iteration
            if stepsize < 1e-30:
                logger.report_event("Step size is small enough, finishing optimization", log_level=logging.INFO)
                break

            # if the changes to the tiles are too small, stop optimization
            #med_diff_threshold = 0.001
            #if abs(prev_meanmed - meanmed) < med_diff_threshold and abs(prev_medmed - medmed) < med_diff_threshold and abs(prev_maxmed - maxmed) < med_diff_threshold:
            #    logger.report_event("Absolute med difference is small enough, finishing optimization", log_level=logging.INFO)
            #    break

            prev_meanmed = meanmed
            prev_medmed = medmed
            prev_maxmed = maxmed

            # don't update Rotations on last iteration
            if (iter < self._params["max_iterations"] - 1):
                # find points and their matches from other groups for each tile
                self_points = defaultdict(list)
                other_points = defaultdict(list)
                for (k1, k2), (p1, p2) in masked_matches.items():
                    self_points[k1].append(p1)
                    self_points[k2].append(p2)
                    other_points[k1].append(p2)
                    other_points[k2].append(p1)
                self_points = {k: np.hstack(p) for k, p in self_points.items()}
                other_points = {k: np.hstack(p) for k, p in other_points.items()}

                self_centers = {k: np.mean(p, axis=1).reshape((2, 1)) for k, p in self_points.items()}
                other_centers = {k: np.mean(p, axis=1).reshape((2, 1)) for k, p in other_points.items()}

                # find best rotation, multiply the angle of rotation by a stepsize, and update the rotations
                new_R = {k: OptimizerRigid2D._find_rotation(self_points[k] - self_centers[k],
                                          other_points[k] - other_centers[k],
                                          stepsize)
                         for k in self_centers}
                R = {k: np.dot(R[k], new_R[k]) for k in R}

        #R = {k: v.tolist() for k, v in R.items()}
        #T = {k: v.tolist() for k, v in T.items()}
        #centers = {k: v.tolist() for k, v in centers.items()}
        R = {k: v for k, v in R.items()}
        T = {k: v.T[0] for k, v in T.items()}
        centers = {k: v.T[0] for k, v in centers.items()}
        # json.dump({"Rotations": R,
        #            "Translations": T,
        #            "centers": centers},
        #           open(sys.argv[2], "wb"),
        #           indent=4)
        #create_new_tilespec(tiles_fname, R, T, centers, out_fname)
        # Generate the per-tile results
        return OptimizerRigid2D.create_transforms(R, T, centers, all_start_pts)




#     def optimize_2d_mfovs_old(tiles_fname, match_list_file, out_fname, conf_fname=None):
#         logger.start_process('optimize_2d_mfovs', 'optimize_2d_mfovs.py', [tiles_fname, match_list_file, out_fname])
#         logger.report_event("Optimizing tilespec: {}".format(tiles_fname), log_level=logging.INFO)
#         st_time = time.time()
#         # all matched pairs between point sets
#         all_matches = {}
#         # all points from a given tile
#         all_pts = defaultdict(list)
# 
#         # load the list of files
#         with open(match_list_file, 'r') as list_file:
#             match_files = list_file.readlines()
#         match_files = [fname.replace('\n', '').replace('file://', '') for fname in match_files]
#         # print(match_files)
# 
#         # Load config parameters
#         params = utils.conf_from_file(conf_fname, 'Optimize2Dmfovs')
#         if params is None:
#             params = {}
#         maxiter = params.get("maxIterations", 1000)
#         epsilon = params.get("maxEpsilon", 5)
#         stepsize = params.get("stepSize", 0.1)
#         damping = params.get("damping", 0.01)  # in units of matches per pair
#         avoidemptymatches = True if "avoidEmptyMatches" in params else False
#         tilespec = json.load(open(tiles_fname, 'r'))
# 
#         # load the matches
#         pbar = progressbar.ProgressBar()
#         for f in pbar(match_files):
#             try:
#                 data = json.load(open(f))
#             except:
#                 logger.report_event("Error when parsing: {}".format(f), log_level=logging.ERROR)
#                 raise
#             # point arrays are 2xN
#             pts1 = np.array([c["p1"]["w"] for c in data[0]["correspondencePointPairs"]]).T
#             pts2 = np.array([c["p2"]["w"] for c in data[0]["correspondencePointPairs"]]).T
#             url1 = data[0]["url1"]
#             url2 = data[0]["url2"]
#             if pts1.size > 0:
#                 all_matches[url1, url2] = (pts1, pts2)
#                 all_pts[url1].append(pts1)
#                 all_pts[url2].append(pts2)
#             # If we want to add fake points when no matches are found
#             elif not avoidemptymatches:
#                 # Find the images in the tilespec
#                 mfov1, mfov2 = -1, -1
#                 for t in tilespec:
#                     if t['mipmapLevels']['0']['imageUrl'] == url1:
#                         tile1 = t
#                         mfov1 = t["mfov"]
#                     if t['mipmapLevels']['0']['imageUrl'] == url2:
#                         tile2 = t
#                         mfov2 = t["mfov"]
#                 if mfov1 == -1 or mfov2 == -1 or mfov1 != mfov2:
#                     continue
# 
#                 # Determine the region of overlap between the two images
#                 overlapx_min = max(tile1['bbox'][0], tile2['bbox'][0])
#                 overlapx_max = min(tile1['bbox'][1], tile2['bbox'][1])
#                 overlapy_min = max(tile1['bbox'][2], tile2['bbox'][2])
#                 overlapy_max = min(tile1['bbox'][3], tile2['bbox'][3])
#                 obbox = [overlapx_min, overlapx_max, overlapy_min, overlapy_max]
#                 xrang, yrang = obbox[1] - obbox[0], obbox[3] - obbox[2]
#                 if xrang < 0 or yrang < 0:
#                     # The two areas do not overlap
#                     continue
# 
#                 # Choose four random points in the overlap region - one from each quadrant
#                 xvals, yvals = [], []
#                 xvals.append(random.random() * xrang / 2 + obbox[0])
#                 xvals.append(random.random() * xrang / 2 + obbox[0] + xrang / 2)
#                 xvals.append(random.random() * xrang / 2 + obbox[0])
#                 xvals.append(random.random() * xrang / 2 + obbox[0] + xrang / 2)
# 
#                 yvals.append(random.random() * yrang / 2 + obbox[2])
#                 yvals.append(random.random() * yrang / 2 + obbox[2])
#                 yvals.append(random.random() * yrang / 2 + obbox[2] + yrang / 2)
#                 yvals.append(random.random() * yrang / 2 + obbox[2] + yrang / 2)
# 
#                 # Add these 4 points to a list of point pairs
#                 corpairs = []
#                 for i in range(0, len(xvals)):
#                     newpair = {}
#                     newpair['dist_after_ransac'] = 1.0
#                     newp1 = {'l': [xvals[i] - tile1['bbox'][0], yvals[i] - tile1['bbox'][2]], 'w': [xvals[i], yvals[i]]}
#                     newp2 = {'l': [xvals[i] - tile2['bbox'][0], yvals[i] - tile2['bbox'][2]], 'w': [xvals[i], yvals[i]]}
#                     newpair['p1'] = newp1
#                     newpair['p2'] = newp2
#                     corpairs.append(newpair)
# 
#                 logger.report_event("Added {} \"Fake\" matches between tiles: {} and {}".format(len(corpairs), url1, url2), log_level=logging.INFO)
#                 pts1 = np.array([c["p1"]["w"] for c in corpairs]).T
#                 pts2 = np.array([c["p2"]["w"] for c in corpairs]).T
#                 all_matches[url1, url2] = (pts1, pts2)
#                 all_pts[url1].append(pts1)
#                 all_pts[url2].append(pts2)
# 
#         # Find centers of each group of points
#         centers = {k: np.mean(np.hstack(pts), axis=1, keepdims=True) for k, pts in all_pts.items()}
#         # a unique index for each url
#         url_idx = {url: idx for idx, url in enumerate(all_pts)}
# 
#         prev_meanmed = np.inf
# 
#         T = defaultdict(lambda: np.zeros((2, 1)))
#         R = defaultdict(lambda: np.eye(2))
#         for iter in range(maxiter):
#             # transform points by the current trans/rot
#             trans_matches = {(k1, k2): (np.dot(R[k1], p1 - centers[k1]) + T[k1] + centers[k1],
#                                         np.dot(R[k2], p2 - centers[k2]) + T[k2] + centers[k2])
#                              for (k1, k2), (p1, p2) in all_matches.items()}
# 
#             # mask off all points more than epsilon past the median
#             diffs = {k: p2 - p1 for k, (p1, p2) in trans_matches.items()}
#             distances = {k: np.sqrt((d ** 2).sum(axis=0)) for k, d in diffs.items()}
#             masks = {k: d < (np.median(d) + epsilon) for k, d in distances.items()}
#             masked_matches = {k: (p1[:, masks[k]], p2[:, masks[k]]) for k, (p1, p2) in trans_matches.items()}
# 
#             median_dists = [np.median(d) for d in distances.values()]
#             medmed = np.median(median_dists)
#             meanmed = np.mean(median_dists)
#             maxmed = np.max(median_dists)
#             logger.report_event("med-med distance: {}, mean-med distance: {}  max-med: {}  SZ: {}".format(medmed, meanmed, maxmed, stepsize), log_level=logging.INFO)
#             logger.report_metric("Optimize2d_med_med_distance", medmed, context=[tiles_fname, match_list_file, iter])
#             logger.report_metric("Optimize2d_mean_med_distance", meanmed, context=[tiles_fname, match_list_file, iter])
#             logger.report_metric("Optimize2d_max_med_distance", maxmed, context=[tiles_fname, match_list_file, iter])
#             if meanmed < prev_meanmed:
#                 stepsize *= 1.1
#                 if stepsize > 1:
#                     stepsize = 1
#             else:
#                 stepsize *= 0.5
# 
#             # Find optimal translations
#             #
#             # Build a sparse matrix M of c/0/-c for differences between match sets,
#             # where c is the size of each match set, and a vector D of sums of
#             # differences, and then solve for T:
#             #    M * T = D
#             # to get the translations (independently in x and y).
#             #
#             # M is IxJ, I = number of match pairs, J = number of tiles
#             # T is Jx2, D is Ix2  (2 for x, y)
# 
#             # two nonzero entries per match set
#             rows = np.hstack((np.arange(len(diffs)), np.arange(len(diffs))))
#             cols = np.hstack(([url_idx[url1] for (url1, url2) in diffs],
#                               [url_idx[url2] for (url1, url2) in diffs]))
#             # diffs are p2 - p1, so we want a positive value on the translation for p1,
#             # e.g., a solution could be Tp1 == p2 - p1.
#             Mvals = np.hstack(([pts.shape[1] for pts in diffs.values()],
#                               [-pts.shape[1] for pts in diffs.values()]))
#             logger.report_event("solving", log_level=logging.DEBUG)
#             M = spp.csr_matrix((Mvals, (rows, cols)))
# 
#             # We use the sum of match differences
#             D = np.vstack([d.sum(axis=1) for d in diffs.values()])
#             oTx = lsqr(M, D[:, :1], damp=damping)[0]
#             oTy = lsqr(M, D[:, 1:], damp=damping)[0]
#             for k, idx in url_idx.items():
#                 T[k][0] += oTx[idx]
#                 T[k][1] += oTy[idx]
# 
#             # first iteration is translation only
#             if iter == 0:
#                 continue
# 
#             # don't update Rotations on last iteration
#             if stepsize < 1e-30:
#                 logger.report_event("Step size is small enough, finishing optimization", log_level=logging.INFO)
#                 break
# 
#             # if the changes to the tiles are too small, stop optimization
#             #med_diff_threshold = 0.001
#             #if abs(prev_meanmed - meanmed) < med_diff_threshold and abs(prev_medmed - medmed) < med_diff_threshold and abs(prev_maxmed - maxmed) < med_diff_threshold:
#             #    logger.report_event("Absolute med difference is small enough, finishing optimization", log_level=logging.INFO)
#             #    break
# 
#             prev_meanmed = meanmed
#             prev_medmed = medmed
#             prev_maxmed = maxmed
# 
#             # don't update Rotations on last iteration
#             if (iter < maxiter - 1):
#                 # find points and their matches from other groups for each tile
#                 self_points = defaultdict(list)
#                 other_points = defaultdict(list)
#                 for (k1, k2), (p1, p2) in masked_matches.items():
#                     self_points[k1].append(p1)
#                     self_points[k2].append(p2)
#                     other_points[k1].append(p2)
#                     other_points[k2].append(p1)
#                 self_points = {k: np.hstack(p) for k, p in self_points.items()}
#                 other_points = {k: np.hstack(p) for k, p in other_points.items()}
# 
#                 self_centers = {k: np.mean(p, axis=1).reshape((2, 1)) for k, p in self_points.items()}
#                 other_centers = {k: np.mean(p, axis=1).reshape((2, 1)) for k, p in other_points.items()}
# 
#                 # find best rotation, multiply the angle of rotation by a stepsize, and update the rotations
#                 new_R = {k: find_rotation(self_points[k] - self_centers[k],
#                                           other_points[k] - other_centers[k],
#                                           stepsize)
#                          for k in self_centers}
#                 R = {k: np.dot(R[k], new_R[k]) for k in R}
# 
#         R = {k: v.tolist() for k, v in R.items()}
#         T = {k: v.tolist() for k, v in T.items()}
#         centers = {k: v.tolist() for k, v in centers.items()}
#         # json.dump({"Rotations": R,
#         #            "Translations": T,
#         #            "centers": centers},
#         #           open(sys.argv[2], "wb"),
#         #           indent=4)
#         create_new_tilespec(tiles_fname, R, T, centers, out_fname)
# 
#         logger.report_event("** 2D mfovs optimization took: {} seconds".format(time.time() - st_time), log_level=logging.INFO)
#         logger.report_metric("Optimize2d_time", time.time() - st_time, context=[tiles_fname, match_list_file])
#         logger.end_process('optimize_2d_mfovs ending', rh_logger.ExitCode(0))

