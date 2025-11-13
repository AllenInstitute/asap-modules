"""
run mesh lens correction from acquisition/metadata file.

This uses template matches and attempts to emulate the on-scope lens correction module (for better or worse)

TODO:
make this generic to include w/ run_mesh_lens_correction
"""

import concurrent.futures
import math
import pathlib
import json
from typing import Iterable, Tuple, Dict, Any, List


import renderapi
import uri_handler.uri_functions
import shapely
import numpy
import argschema

import cv2

import em_stitch.utils.generate_EM_tilespecs_from_metafile
import asap.em_montage_qc.detect_montage_defects
import em_stitch.montage.meta_to_collection
import asap.em_montage_qc.plots
import em_stitch.lens_correction.mesh_and_solve_transform
import asap.pointmatch.generate_point_matches_opencv
import bigfeta.jsongz
import em_stitch.lens_correction.lens_correction_solver
import em_stitch.utils.utils as common_utils

from asap.pointmatch.generate_point_matches_opencv import (
    read_downsample_equalize_mask_uri,
    make_pm
)

np = numpy


# FIXME this should be in em-stitch
class GenerateEMTilespecsModule_URIPrefix(
        em_stitch.utils.generate_EM_tilespecs_from_metafile.GenerateEMTileSpecsModule):
    @staticmethod
    def ts_from_imgdata_tileId(imgdata, img_prefix, x, y, tileId, 
                               minint=0, maxint=255, maskUrl=None,
                               width=3840, height=3840, z=None, sectionId=None,
                               scopeId=None, cameraId=None, pixelsize=None):
        raw_tforms = [renderapi.transform.AffineModel(B0=x, B1=y)]
        imageUrl = uri_handler.uri_functions.uri_join(
            img_prefix, imgdata["img_path"])
        
        if maskUrl is not None:
            maskUrl = pathlib.Path(maskUrl).as_uri()

        ip = renderapi.image_pyramid.ImagePyramid()
        ip[0] = renderapi.image_pyramid.MipMap(imageUrl=imageUrl,
                                               maskUrl=maskUrl)
        return renderapi.tilespec.TileSpec(
            tileId=tileId, z=z,
            width=width, height=height,
            minint=minint, maxint=maxint,
            tforms=raw_tforms,
            imagePyramid=ip,
            sectionId=sectionId, scopeId=scopeId, cameraId=cameraId,
            imageCol=imgdata['img_meta']['raster_pos'][0],
            imageRow=imgdata['img_meta']['raster_pos'][1],
            stageX=imgdata['img_meta']['stage_pos'][0],
            stageY=imgdata['img_meta']['stage_pos'][1],
            rotation=imgdata['img_meta']['angle'], pixelsize=pixelsize)


def resolvedtiles_from_temca_md(
        md, image_prefix, z,
        sectionId=None,
        minimum_intensity=0, maximum_intensity=255,
        initial_transform=None):
    tspecs = GenerateEMTilespecsModule_URIPrefix.ts_from_metadata(
        md, image_prefix, z, sectionId, minimum_intensity, maximum_intensity)
    tformlist = []
    if initial_transform is not None:
        initial_transform_ref = renderapi.transform.ReferenceTransform(
            refId=initial_transform.transformId)
        for ts in tspecs:
            ts.tforms.insert(0, initial_transform_ref)
        tformlist = [initial_transform]
    return renderapi.resolvedtiles.ResolvedTiles(
        tilespecs=tspecs,
        transformList=tformlist
    )


def bbox_from_ts(ts, ref_tforms, **kwargs):
    tsarr = asap.em_montage_qc.detect_montage_defects.generate_border_mesh_pts(
        ts.width, ts.height, **kwargs)
    pts = renderapi.transform.estimate_dstpts(
        ts.tforms, src=tsarr,
        reference_tforms=ref_tforms)
    minX, minY = numpy.min(pts, axis=0)
    maxX, maxY = numpy.max(pts, axis=0)
    return minX, minY, maxX, maxY


def apply_resolvedtiles_bboxes(rts, **kwargs):
    for ts in rts.tilespecs:
        minX, minY, maxX, maxY = bbox_from_ts(ts, rts.transforms, **kwargs)
        ts.minX = minX
        ts.minY = minY
        ts.maxX = maxX
        ts.maxY = maxY


# TODO many issues in em-stitch implementation of this.   here, just add the ability to skip matches that fail kmeans
def filter_match_collection(
        matches, threshold, model="Similarity",
        n_clusters=None, n_cluster_pts=20, ransacReprojThreshold=40.,
        ignore_match_indices=(),
        input_n_key="n_from_gpu", output_n_key="n_after_filter"):
    """
    Filter a collection of matches based on specified criteria.

    Parameters
    ----------
    matches : List[Dict[str, Any]]
        The collection of matches to filter.
    threshold : float
        Threshold value.
    model : str, optional
        Model type, by default "Similarity".
    n_clusters : int, optional
        Number of clusters, by default None.
    n_cluster_pts : int, optional
        Number of cluster points, by default 20.
    ransacReprojThreshold : float, optional
        RANSAC reprojection threshold, by default 40.0.
    ignore_match_indices : Optional[Iterable[int]], optional
        Indices of matches to ignore, by default None.
    input_n_key : str, optional
        Key to store input count in counts dictionary, by default "n_from_gpu".
    output_n_key : str, optional
        Key to store output count in counts dictionary, by default "n_after_filter".

    Returns
    -------
    Tuple[List[Dict[str, Any]], List[Dict[str, int]]]
        A tuple containing the filtered matches and their corresponding counts.
    """
    ignore_match_indices = (set() if ignore_match_indices is None else ignore_match_indices)
    ignore_match_indices = set(ignore_match_indices)

    counts = []
    new_matches = []

    for i, m in enumerate(matches):
        input_n = len(m["matches"]["p"][0])

        try:
            _, _, w, _ = common_utils.pointmatch_filter(
                m,
                n_clusters=n_clusters,
                n_cluster_pts=n_cluster_pts,
            )
        except:
            continue

        m["matches"]["w"] = w.tolist()

        output_n = np.count_nonzero(w)

        counts.append({
            input_n_key: input_n,
            output_n_key: output_n})

        # original version ran pointmatch filtering for these and then filtered
        #   them out of the matches.  Do this by continuing here, I guess.
        if i in ignore_match_indices:
            continue

        new_matches.append(m)

    return new_matches, counts


# TODO: allow different inputs, or substitute with an equivalent helper function from em-stitch
def solve_lc(rts, matches, transformId=None):
    solve_matches = renderapi.pointmatch.copy_matches_explicit(matches)
    # define input parameters for solving
    nvertex = 1000
    
    # regularization parameters for components
    regularization_dict = {
        "translation_factor": 0.001,
        "default_lambda": 1.0,
        "lens_lambda": 1.0
    }
    
    # thresholds defining an acceptable solution.
    #   solves exceeding these will raise an exception in em_stitch.lens_correction.mesh_and_solve_transform._solve_resolvedtiles
    good_solve_dict = {
        "error_mean": 2.0,
        "error_std": 5.5,
        "scale_dev": 0.1
    }
    
    solve_resolvedtiles_args = (
        rts, solve_matches,
        nvertex, regularization_dict["default_lambda"],
        regularization_dict["translation_factor"],
        regularization_dict["lens_lambda"],
        good_solve_dict
    )
    solved_rts, lc_tform, jresult = em_stitch.lens_correction.mesh_and_solve_transform._solve_resolvedtiles(*solve_resolvedtiles_args)
    if transformId:
        lc_tform.transformId = transformId
    return lc_tform


# TODO pair tiles rts
def pair_tiles_rts(rts, query_fraction=0.1, inverse_pair=True):
    boxes = [shapely.box(*ts.bbox) for ts in rts.tilespecs]
    tree = shapely.strtree.STRtree(boxes)

    qresults = {}
    
    for qidx, qbox in enumerate(boxes):
        qbox = boxes[qidx]
        qfraction = query_fraction
        qdiag = numpy.sqrt(qbox.length ** 2 - 8 * qbox.area) / 2
        qminX, qminY, qmaxX, qmaxY = qbox.bounds
    
        qresult_idxs = tree.query_nearest(
            qbox, max_distance=qdiag * qfraction, exclusive=True)
        for ridx in qresult_idxs:
            if frozenset((qidx, ridx)) not in qresults:
                rbox = boxes[ridx]
                is_not_corner = ((qminX < rbox.centroid.x < qmaxX) &
                                 (qminY < rbox.centroid.y < qmaxY))
                if is_not_corner:
                    rminX, rminY, rmaxX, rmaxY = rbox.bounds

                    # copied from java
                    deltaX = qminX - rminX
                    deltaY = qminY - rminY
                    if abs(deltaX) > abs(deltaY):
                        orientation = ("RIGHT" if deltaX > 0 else "LEFT") 
                    else:
                        orientation = ("BOTTOM" if deltaY > 0 else "TOP")
    
                    opposite_orientation = {
                        "LEFT": "RIGHT",
                        "TOP": "BOTTOM",
                        "RIGHT": "LEFT",
                        "BOTTOM": "TOP"
                    }[orientation]
    
                    p_ts = rts.tilespecs[qidx]
                    q_ts = rts.tilespecs[ridx]
                    qresults[frozenset((qidx, ridx))] = {
                        "p": {
                            "groupId": p_ts.layout.sectionId,
                            "id": p_ts.tileId,
                            "relativePosition": orientation
                        },
                        "q": {
                            "groupId": q_ts.layout.sectionId,
                            "id": q_ts.tileId,
                            "relativePosition": opposite_orientation
                        }
                    }
    
    neighborpairs_rp = [*qresults.values()]
    if inverse_pair:
        neighborpairs_rp += [{"p": d["q"], "q": d["p"]} for d in neighborpairs_rp]
    return neighborpairs_rp


# TODO update asap-modules for unlimited matches
def locs_to_dict(
        pGroupId, pId, loc_p,
        qGroupId, qId, loc_q,
        scale_factor=None, match_max=None):

    match_max = (
        loc_p.shape[0] if match_max is None
        else match_max
    )

    if loc_p.shape[0] < 0:
        return
    if scale_factor is not None:
        loc_p *= scale_factor
        loc_q *= scale_factor

    if loc_p.shape[0] > match_max:
        ind = numpy.arange(loc_p.shape[0])
        numpy.random.shuffle(ind)
        ind = ind[0:match_max]
        loc_p = loc_p[ind, ...]
        loc_q = loc_q[ind, ...]

    return make_pm(
        (pId, qId),
        (pGroupId, qGroupId),
        loc_p, loc_q)


# TODO make this better
def pytemca_query_points(n_points=33, n_corner_points=2, corner_fraction=0.005, corner_offset=8, w=5376, h=5376):
    # get the pixel coordinates of the sampling grid, (0,0) in the TL corner
    corner_size = w * corner_fraction
    border = 0
    xPix = np.linspace(border, w - 1 - border, num=n_points, endpoint=True, dtype=int)
    yPix = np.linspace(border, h - 1 - border, num=n_points, endpoint=True, dtype=int)
    xxPix, yyPix = np.meshgrid(xPix, yPix)
    xyPix = np.vstack([xxPix.ravel(), yyPix.ravel()])  # back to a 2D list

    # add in the corner high density sampling areas

    # generate a corner grid
    jxPix = np.linspace(0, corner_size, num=n_corner_points, endpoint=True, dtype=int)
    jyPix = np.linspace(0, corner_size, num=n_corner_points, endpoint=True, dtype=int)
    jxxPix, jyyPix = np.meshgrid(jxPix, jyPix)
    jxyPix = np.vstack([jxxPix.ravel(), jyyPix.ravel()]) # back to a 2D list

    # top left
    txxPix = jxxPix + corner_offset
    tyyPix = jyyPix + corner_offset
    xyPix = np.concatenate((xyPix, np.vstack([txxPix.ravel(), tyyPix.ravel()])), 1)

    # top right
    txxPix = jxxPix + (w - corner_size - corner_offset)
    tyyPix = jyyPix + corner_offset
    xyPix = np.concatenate((xyPix, np.vstack([txxPix.ravel(), tyyPix.ravel()])), 1)

    # bottom left
    txxPix = jxxPix + corner_offset
    tyyPix = jyyPix + (h - corner_size - corner_offset)
    xyPix = np.concatenate((xyPix, np.vstack([txxPix.ravel(), tyyPix.ravel()])), 1)
        
    # bottom right
    txxPix = jxxPix + (w - corner_size - corner_offset)
    tyyPix = jyyPix + (h - corner_size - corner_offset)
    xyPix = np.concatenate((xyPix, np.vstack([txxPix.ravel(), tyyPix.ravel()])), 1)

    # more samples on the center of each edge

    # center left
    txxPix = jxxPix + corner_offset
    tyyPix = jyyPix + (h/2 - corner_size/2 + corner_offset)
    xyPix = np.concatenate((xyPix, np.vstack([txxPix.ravel(), tyyPix.ravel()])), 1)

    # center top
    txxPix = jxxPix + (w/2 - corner_size/2 + corner_offset)
    tyyPix = jyyPix + corner_offset
    xyPix = np.concatenate((xyPix, np.vstack([txxPix.ravel(), tyyPix.ravel()])), 1)

    # center right
    txxPix = jxxPix + (w - corner_size - corner_offset)
    tyyPix = jyyPix + (h/2 - corner_size/2 + corner_offset)
    xyPix = np.concatenate((xyPix, np.vstack([txxPix.ravel(), tyyPix.ravel()])), 1)
        
    # center bottom
    txxPix = jxxPix + (w/2 - corner_size/2 - corner_offset)
    tyyPix = jyyPix + (h - corner_size - corner_offset)
    xyPix = np.concatenate((xyPix, np.vstack([txxPix.ravel(), tyyPix.ravel()])), 1)

    return xyPix.T.astype(int)


def match_templates_at_points(
    img1: np.ndarray,
    img2: np.ndarray,
    template_centers: Iterable[Tuple[int, int]],
    search_centers: Iterable[Tuple[int, int]],
    patch_size: Tuple[int, int] = (32, 32),
    search_radius: int = 20,
    # quality thresholds (set any to None to disable)
    min_ncc: float = 0.5,
    min_psr: float = 6.0,
    min_peak_ratio: float = 1.2,
    min_var: float = 1e-3,
) -> Dict[str, Any]:
    """
    Returns match metrics + quality gating:
      - 'good': (N,) bool mask for accepted matches
      - 'reject_reason': list of strings ('' if good)
      - 'matched_center_img2': absolute template center positions in img2
    """
    def _clip_rect(x, y, w, h, W, H):
        nx = max(0, x)
        ny = max(0, y)
        nw = max(0, min(x + w, W) - nx)
        nh = max(0, min(y + h, H) - ny)
        return (nx, ny, nw, nh)

    def _rect_slices(r):
        x, y, w, h = r
        return slice(y, y + h), slice(x, x + w)

    def _f32(a):
        return a.astype(np.float32, copy=False) if a.dtype != np.float32 else a

    def _psr(R: np.ndarray, peak_xy: Tuple[int, int], guard: int) -> float:
        # PSR = (peak - mean(sidelobes)) / std(sidelobes), excluding a guard window around the peak
        h, w = R.shape
        mask = np.ones_like(R, dtype=bool)
        x0 = max(0, peak_xy[0] - guard)
        x1 = min(w, peak_xy[0] + guard + 1)
        y0 = max(0, peak_xy[1] - guard)
        y1 = min(h, peak_xy[1] + guard + 1)
        mask[y0:y1, x0:x1] = False
        sidelobes = R[mask]
        if sidelobes.size == 0:
            return 0.0
        mu = float(sidelobes.mean())
        sd = float(sidelobes.std(ddof=0))
        if sd <= 1e-12:
            return 0.0
        return float((R[peak_xy[1], peak_xy[0]] - mu) / sd)

    def _second_peak(R: np.ndarray, peak_xy: Tuple[int, int], suppress: int) -> float:
        # Suppress a neighborhood around the max, return next max
        R2 = R.copy()
        x0 = max(0, peak_xy[0] - suppress)
        x1 = min(R.shape[1], peak_xy[0] + suppress + 1)
        y0 = max(0, peak_xy[1] - suppress)
        y1 = min(R.shape[0], peak_xy[1] + suppress + 1)
        R2[y0:y1, x0:x1] = -np.inf
        return float(np.max(R2))

    H1, W1 = img1.shape[:2]
    H2, W2 = img2.shape[:2]
    wT, hT = patch_size
    sw = wT + 2 * search_radius
    sh = hT + 2 * search_radius

    t_centers = list(template_centers)
    s_centers = list(search_centers)
    if len(t_centers) != len(s_centers):
        raise ValueError("template_centers and search_centers must have the same length.")

    img1f, img2f = _f32(img1), _f32(img2)

    N = len(t_centers)
    offsets = np.zeros((N, 2), dtype=np.float32)
    distance = np.zeros((N,), dtype=np.float32)
    rotation = np.zeros((N,), dtype=np.float32)
    maxVal = np.full((N,), np.nan, dtype=np.float32)
    minVal = np.full((N,), np.nan, dtype=np.float32)
    # rect_template: List[Tuple[int,int,int,int]] = []
    # rect_search:   List[Tuple[int,int,int,int]] = []
    expected_offset_in_crop: List[Tuple[int,int]] = []
    maxLoc: List[Tuple[int,int]] = []
    matched_pos_img2: List[Tuple[int,int]] = []
    matched_center_img2: List[Tuple[int,int]] = []
    # result8u: List[np.ndarray] = []
    good = np.zeros((N,), dtype=bool)
    reject_reason: List[str] = [""] * N

    # guard/suppress windows scale with template size
    guard = max(3, min(wT, hT) // 6)
    suppress = guard

    for i, ((tx, ty), (sx, sy)) in enumerate(zip(t_centers, s_centers)):
        tmpl_req = (tx - wT // 2, ty - hT // 2, wT, hT)
        srch_req = (sx - sw // 2, sy - sh // 2, sw, sh)

        tmpl = _clip_rect(*tmpl_req, W1, H1)
        srch = _clip_rect(*srch_req, W2, H2)
        # rect_template.append(tmpl)
        # rect_search.append(srch)

        # Invalid windows?
        if tmpl[2] <= 0 or tmpl[3] <= 0 or srch[2] <= 0 or srch[3] <= 0:
            reject_reason[i] = "empty_window"
            expected_offset_in_crop.append((0, 0))
            maxLoc.append((0, 0))
            matched_pos_img2.append((0, 0))
            matched_center_img2.append((0, 0))
            # result8u.append(np.zeros((1, 1), dtype=np.uint8))
            continue

        # Offsets for expected-in-crop + center offset in template
        ptTemplateOffset = (tx - tmpl[0], ty - tmpl[1])
        ptSearchOffset   = (sx - srch[0], sy - srch[1])
        ex = ptSearchOffset[0] - ptTemplateOffset[0]
        ey = ptSearchOffset[1] - ptTemplateOffset[1]
        expected_offset_in_crop.append((ex, ey))

        ys_t, xs_t = _rect_slices(tmpl)
        ys_s, xs_s = _rect_slices(srch)
        T = img1f[ys_t, xs_t]
        S = img2f[ys_s, xs_s]

        # Texture check (flat templates are uninformative)
        if min_var is not None and float(np.var(T)) < min_var:
            reject_reason[i] = "low_texture"
            maxLoc.append((0, 0))
            matched_pos_img2.append((0, 0))
            matched_center_img2.append((0, 0))
            # result8u.append(np.zeros((1, 1), dtype=np.uint8))
            continue

        if T.shape[0] > S.shape[0] or T.shape[1] > S.shape[1]:
            reject_reason[i] = "template_larger_than_search"
            maxLoc.append((0, 0))
            matched_pos_img2.append((0, 0))
            matched_center_img2.append((0, 0))
            # result8u.append(np.zeros((1, 1), dtype=np.uint8))
            continue

        # Correlate
        R = cv2.matchTemplate(S, T, cv2.TM_CCOEFF_NORMED)
        mn, mx, mnLoc, mxLoc = cv2.minMaxLoc(R)
        # r8 = np.clip(R * 255.0, 0, 255).astype(np.uint8, copy=False)

        # Absolute positions in img2
        matched_tl = (srch[0] + mxLoc[0], srch[1] + mxLoc[1])
        matched_center = (matched_tl[0] + ptTemplateOffset[0],
                          matched_tl[1] + ptTemplateOffset[1])

        # Offsets vs expected within cropped windows
        dx = float(mxLoc[0] - ex)
        dy = float(mxLoc[1] - ey)

        # Store metrics
        offsets[i, :] = (dx, dy)
        distance[i] = math.hypot(dx, dy)
        rotation[i] = math.atan2(dy, dx)
        maxVal[i] = float(mx)
        minVal[i] = float(mn)
        maxLoc.append((int(mxLoc[0]), int(mxLoc[1])))
        matched_pos_img2.append(matched_tl)
        matched_center_img2.append(matched_center)
        # result8u.append(r8)

        # --- Quality gating ---
        # 1) NCC
        if min_ncc is not None and mx < min_ncc:
            reject_reason[i] = "low_ncc"
            continue

        # 2) PSR
        psr = _psr(R, (mxLoc[0], mxLoc[1]), guard)
        if min_psr is not None and psr < min_psr:
            reject_reason[i] = f"low_psr({psr:.2f})"
            continue

        # 3) Peak ratio
        sp = _second_peak(R, (mxLoc[0], mxLoc[1]), suppress)
        if min_peak_ratio is not None and (sp == -np.inf or mx / max(sp, 1e-12) < min_peak_ratio):
            reject_reason[i] = f"low_peak_ratio({mx/max(sp,1e-12):.2f})"
            continue

        # Passed all checks
        good[i] = True
        reject_reason[i] = ""

    return {
        "offsets": offsets,
        "distance": distance,
        "rotation": rotation,
        "maxVal": maxVal,
        "minVal": minVal,
        # "rect_template": rect_template,
        # "rect_search": rect_search,
        "expected_offset_in_crop": expected_offset_in_crop,
        "maxLoc": maxLoc,
        "matched_pos_img2": matched_pos_img2,        # template top-left (abs)
        "matched_center_img2": matched_center_img2,  # template center (abs) — what you asked for
        # "result8u": result8u,
        "good": good,
        "reject_reason": reject_reason,
    }


def sample_pts_from_p_local_seeds(p_local_seed_pts,
                                  p_img_shape, p_origin,
                                  q_img_shape, q_origin):
    p_world_pts = p_local_seed_pts + numpy.array(p_origin)
    q_local_seed_pts = p_world_pts - numpy.array(q_origin)
    return p_local_seed_pts, q_local_seed_pts


def filter_template_pts_by_ts_overlap(
        template_pts, template_ts, search_ts, buffer=64):
    # overlap bounds
    minX = max(template_ts.minX - buffer, search_ts.minX - buffer)
    minY = max(template_ts.minY - buffer, search_ts.minY - buffer)
    maxX = min(template_ts.maxX + buffer, search_ts.maxX + buffer)
    maxY = min(template_ts.maxY + buffer, search_ts.maxY + buffer)

    template_minX = minX - template_ts.minX
    template_minY = minY - template_ts.minY
    template_maxX = maxX - template_ts.minX
    template_maxY = maxY - template_ts.minY

    bounds_mask = (
        ((template_pts[:, 0] >= template_minX) & (template_pts[:, 0] <= template_maxX)) &
        ((template_pts[:, 1] >= template_minY) & (template_pts[:, 1] <= template_maxY))
    )

    return template_pts[bounds_mask]


def template_match_images(
        pim, qim, p_seed_pts, q_seed_pts, return_num_features=False,
        patch_size=(80, 80),
        search_radius=600,
        min_ncc=0.6,
        min_psr=1.2,
        min_peak_ratio=1.1,
        min_var=1e-3):
    res = match_templates_at_points(
        pim,
        qim,
        p_seed_pts,
        q_seed_pts,
        patch_size=patch_size,
        search_radius=search_radius,
        min_ncc=min_ncc,
        min_psr=min_psr,
        min_peak_ratio=min_peak_ratio,
        min_var=min_var)

    res_p_pts = p_seed_pts[res["good"]]
    res_q_pts = numpy.array(res["matched_center_img2"])[res["good"]]

    if return_num_features:
        return (res_p_pts, res_q_pts), (res_p_pts.shape[0], res_q_pts.shape[0])
    else:
        return (res_p_pts, res_q_pts)


def process_lc_template_matches_ts(
        pId, pGroupId, p_ts,
        qId, qGroupId, q_ts,
        CLAHE_grid=None,
        CLAHE_clip=None,
        min_val=None,
        max_val=None,
        template_match_kwargs=None,
        **kwargs):

    template_match_kwargs = template_match_kwargs or {}

    # image and mask uris based on full-res
    p_image_uri = (p_ts.ip[0].imageUrl, None)
    q_image_uri = (q_ts.ip[0].imageUrl, None)

    downsample_scale = 1

    pim = read_downsample_equalize_mask_uri(
        p_image_uri,
        downsample_scale,
        CLAHE_grid=CLAHE_grid,
        CLAHE_clip=CLAHE_clip,
        min_val=min_val,
        max_val=max_val)
    qim = read_downsample_equalize_mask_uri(
        q_image_uri,
        downsample_scale,
        CLAHE_grid=CLAHE_grid,
        CLAHE_clip=CLAHE_clip,
        min_val=min_val,
        max_val=max_val)

    # generate template centers (p seeds) and search centers (q seeds)
    p_query_pts = pytemca_query_points(w=p_ts.width, h=p_ts.height)

    overlapping_query_pts = filter_template_pts_by_ts_overlap(
        p_query_pts, p_ts, q_ts)

    p_seed_pts, q_seed_pts = sample_pts_from_p_local_seeds(
        overlapping_query_pts,
        pim.shape, (int(p_ts.minX), int(p_ts.minY)),
        qim.shape, (int(q_ts.minX), int(q_ts.minY))
    )

    (loc_p, loc_q), (num_features_p, num_features_q) = template_match_images(
        pim, qim, p_seed_pts, q_seed_pts,
        return_num_features=True, **template_match_kwargs)

    pm_dict = locs_to_dict(
        pGroupId, pId, loc_p,
        qGroupId, qId, loc_q
    )

    return pm_dict, len(loc_p), len(loc_p), len(loc_p)


# TODO match tiles rts
def match_tiles_rts(rts, tpairs, concurrency=10, **kwargs):
    sectionId_tId_to_ts = {
        (ts.layout.sectionId, ts.tileId): ts for ts in rts.tilespecs
    }
    matches_rp = []

    default_kwargs = {
        "min_ncc": None,
        "min_psr": None,
        "min_peak_ratio": None,
        "min_var": None
    }

    kwargs = {**default_kwargs, **kwargs}

    with concurrent.futures.ProcessPoolExecutor(max_workers=concurrency) as e:
        futs = [
            e.submit(
                process_lc_template_matches_ts,
                tpair["p"]["id"], tpair["p"]["groupId"],
                sectionId_tId_to_ts[
                    (tpair["p"]["groupId"], tpair["p"]["id"])
                ],
                tpair["q"]["id"], tpair["q"]["groupId"],
                sectionId_tId_to_ts[
                    (tpair["q"]["groupId"], tpair["q"]["id"])
                ],
                **kwargs
            )
            for tpair in tpairs
        ]
        for fut in futs:
            match_d, num_matches, num_features_p, num_features_q = fut.result()
            matches_rp.append(match_d)

    filtered_matches_rp, counts = filter_match_collection(matches_rp, None)
    return filtered_matches_rp
    # return matches_rp


class TemplateMatchOptions(argschema.schemas.DefaultSchema):
    min_ncc = argschema.fields.Float(required=False, default=None)
    min_psr = argschema.fields.Float(required=False, default=None)
    min_peak_ratio = argschema.fields.Float(required=False, default=None)
    min_var = argschema.fields.Float(required=False, default=None)


class CalculateLensCorrectionParams(argschema.ArgSchema):
    metafile_uri = argschema.fields.Str(required=True)
    image_prefix = argschema.fields.Str(required=True)
    transformId = argschema.fields.Str(required=True)
    concurrency = argschema.fields.Int(required=False, default=10)
    matches_output = argschema.fields.Str(
        required=False, allow_none=True, default=None)
    template_match_options = argschema.fields.Nested(
        TemplateMatchOptions, required=False)


class CalculateLensCorrectionOutputSchema(argschema.schemas.DefaultSchema):
    lc_transform = argschema.fields.Dict(required=True)


class CalculateLensCorrectionModule(argschema.ArgSchemaParser):
    default_schema = CalculateLensCorrectionParams
    default_output_schema = CalculateLensCorrectionOutputSchema

    @staticmethod
    def compute_lc_from_metadata_uri(
            md_uri, image_prefix, sectionId=None,
            transformId=None, match_concurrency=10,
            match_options=None,
            allow_failed_solve=False):
        match_options = match_options or {}

        md = json.loads(uri_handler.uri_functions.uri_readbytes(md_uri))
        rts = resolvedtiles_from_temca_md(
            md, image_prefix, 0, sectionId=sectionId)
        apply_resolvedtiles_bboxes(rts)
        tpairs = pair_tiles_rts(rts)

        matches = match_tiles_rts(
            rts, tpairs, concurrency=match_concurrency,
            **match_options)
        try:
            lc_tform = solve_lc(rts, matches, transformId=transformId)
        except:
            if allow_failed_solve:
                lc_tform = None
            else:
                raise
        return lc_tform, matches

    def run(self):
        lc_tform, matches = self.compute_lc_from_metadata_uri(
            self.args["metafile_uri"],
            self.args["image_prefix"],
            sectionId=self.args["transformId"],
            transformId=self.args["transformId"],
            match_concurrency=self.args["concurrency"],
            allow_failed_solve=True,
            match_options=self.args.get("template_match_options")
        )

        # output matches
        if self.args.get("matches_output"):
            bigfeta.jsongz.dump(matches, self.args["matches_output"])

        if lc_tform is None:
            raise Exception("lc solve failed")

        self.output({
            "lc_transform": json.loads(renderapi.utils.renderdumps(lc_tform))
        })


if __name__ == "__main__":
    mod = CalculateLensCorrectionModule()
    mod.run()
