"""
run mesh lens correction from an acquisition directory/metadata file.
This avoids calls to java clients or other modules and does not require reading or writing from a render collection

Does not provide the same mask support as do_mesh_lens_correction.
"""


import concurrent.futures
import pathlib
import json

import renderapi
import uri_handler.uri_functions
import shapely
import numpy
import argschema

import em_stitch.utils.generate_EM_tilespecs_from_metafile
import asap.em_montage_qc.detect_montage_defects
import em_stitch.montage.meta_to_collection
import asap.em_montage_qc.plots
import em_stitch.lens_correction.mesh_and_solve_transform
import asap.pointmatch.generate_point_matches_opencv


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


# TODO: match tilepair options and make part of tilepair generation
def pair_tiles_rts(rts, query_fraction=0.1):
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
    return neighborpairs_rp


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
        "error_mean": 0.8,
        "error_std": 3.0,
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


def match_tiles_rts(rts, tpairs, concurrency=10):
    sectionId_tId_to_ts = {(ts.layout.sectionId, ts.tileId): ts for ts in rts.tilespecs}
    matches_rp = []
        
    with concurrent.futures.ProcessPoolExecutor(max_workers=concurrency) as e:
        futs = [
            e.submit(
                asap.pointmatch.generate_point_matches_opencv.process_matches,
                tpair["p"]["id"], tpair["p"]["groupId"],
                (
                    sectionId_tId_to_ts[
                        (tpair["p"]["groupId"], tpair["p"]["id"])
                    ].ip[0].imageUrl,
                    None
                ),
                tpair["q"]["id"], tpair["q"]["groupId"],
                (
                    sectionId_tId_to_ts[
                        (tpair["q"]["groupId"], tpair["q"]["id"])
                    ].ip[0].imageUrl,
                    None
                ),
                downsample_scale=0.3,
                ndiv=8,
                matchMax=1000,
                sift_kwargs={
                    "nfeatures": 20000,
                    "nOctaveLayers": 3,
                    "sigma": 1.5,
                },
                # SIFT_nfeature=20000,
                # SIFT_noctave=3,
                # SIFT_sigma=1.5,
                RANSAC_outlier=5.0,
                FLANN_ncheck=50,
                FLANN_ntree=5,
                ratio_of_dist=0.7,
                CLAHE_grid=None,
                CLAHE_clip=None)
            for tpair in tpairs
        ]
        for fut in concurrent.futures.as_completed(futs):
            match_d, num_matches, num_features_p, num_features_q = fut.result()
            matches_rp.append(match_d)
    return matches_rp


class CalculateLensCorrectionParams(argschema.ArgSchema):
    metafile_uri = argschema.fields.Str(required=True)
    image_prefix = argschema.fields.Str(required=True)
    transformId = argschema.fields.Str(required=True)
    concurrency = argschema.fields.Int(required=False, default=10)


class CalculateLensCorrectionOutputSchema(argschema.schemas.DefaultSchema):
    lc_transform = argschema.fields.Dict(required=True)


class CalculateLensCorrectionModule(argschema.ArgSchemaParser):
    default_schema = CalculateLensCorrectionParams
    default_output_schema = CalculateLensCorrectionOutputSchema

    @staticmethod
    def compute_lc_from_metadata_uri(
            md_uri, image_prefix, sectionId=None,
            transformId=None, match_concurrency=10):
        md = json.loads(uri_handler.uri_functions.uri_readbytes(md_uri))
        rts = resolvedtiles_from_temca_md(
            md, image_prefix, 0, sectionId=sectionId)
        apply_resolvedtiles_bboxes(rts)
        tpairs = pair_tiles_rts(rts)

        matches = match_tiles_rts(rts, tpairs)
        lc_tform = solve_lc(rts, matches, transformId=transformId)
        return lc_tform

    def run(self):
        lc_tform = self.compute_lc_from_metadata_uri(
            self.args["metafile_uri"],
            self.args["image_prefix"],
            sectionId=self.args["transformId"],
            transformId=self.args["transformId"],
            match_concurrency=self.args["concurrency"]
        )
        self.output({
            "lc_transform": json.loads(renderapi.utils.renderdumps(lc_tform))
        })


if __name__ == "__main__":
    mod = CalculateLensCorrectionModule()
    mod.run()
