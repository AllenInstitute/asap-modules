from rendermodules.fine_align.schemas import (
        MakeFineInputStackSchema,
        MakeFineOutputStackSchema)
from rendermodules.module.render_module import (
        StackInputModule,
        StackOutputModule,
        RenderModuleException)
from rendermodules.dataimport.create_mipmaps import create_mipmaps
import renderapi
import glob
from six.moves import urllib
import os
import numpy as np
import json
import cv2
import pathlib
import shutil


example_input = {
        "render":{
            "host": "em-131fs",
            "port": 8988,
            "owner": "TEM",
            "project": "17797_1R",
            "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
            },
        "input_stack": "em_rough_align_zs11357_ze11838_sub",
        "output_stack": "em_rough_align_zs11357_ze11838_sub_fine_input",
        "minZ": 11593,
        "maxZ": 11602,
        "label_input_dirs": [
            "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/crack_detection/unet_predictions/em_rough_align_zs11357_ze11838_sub/post_processing/cracks",
            "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/crack_detection/unet_predictions/em_rough_align_zs11357_ze11838_sub/post_processing/folds"],
        "mask_output_dir": "/allen/programs/celltypes/workgroups/em-connectomics/danielk/fine_stack/masks",
        "baseline_vertices": [3, 3],
        "mask_epsilon": 10.0,
        "recalculate_masks": True,
        "split_divided_tiles": True,
        "pool_size": 7,
        "close_stack": True
}


def from_uri(uri):
    return urllib.parse.unquote(
               urllib.parse.urlparse(uri).path)


def to_uri(path):
   return pathlib.Path(path).as_uri()


def get_mask_lists(tilespecs, labeldirs, exts=['png', 'tif']):
    results = {}
    maskfiles = []
    for labeldir in labeldirs:
        for ext in exts:
            maskfiles += glob.glob(os.path.join(labeldir, '*.' + ext))
    maskbasenames = np.array([os.path.basename(os.path.splitext(p)[0])
                              for p in maskfiles])
    for t in tilespecs:
        results[t.tileId] = {
                'levels': [int(l) for l in t.ip.levels],
                'masks': []}
        if t.ip['0']['maskUrl'] is not None:
            results[t.tileId]['masks'].append({
                'path': from_uri(t.ip['0']['maskUrl']),
                'invert': False})
        ind = np.argwhere(maskbasenames == t.tileId.split('.')[0]).flatten()
        for i in ind:
            results[t.tileId]['masks'].append({
                'path': maskfiles[i],
                'invert': True})
    return results


def combine_masks(masks, mask_dir, recalculate):
    results = {}
    for tid, v in masks.items():
        if len(v['masks']) == 0:
            continue

        mpath = os.path.join(mask_dir, tid + '.png')
        root, ext = os.path.splitext(mpath)

        if recalculate:
            combined = None
            for m in v['masks']:
                im = cv2.imread(m['path'], 0)
                if m['invert']:
                    im = 255 - im
                if combined is None:
                    combined = im
                else:
                    combined[im == 0] = 0
            if not cv2.imwrite(mpath, combined):
                raise IOError('cv2.imwrite() could not write to %s' % mask_dir)

        results[tid] = create_mipmaps(
            mpath,
            outputDirectory=mask_dir,
            mipmaplevels=v['levels'],
            outputformat=ext.split('.')[-1],
            convertTo8bit=False,
            force_redo=True,
            block_func="min",
            paths_only=not recalculate)  

        if recalculate:
            os.remove(mpath)

    return results


def approx_snap_contour(contour, width, height, epsilon, snap_dist=5):
    approx = cv2.approxPolyDP(contour, epsilon, True)
    for i in range(approx.shape[0]):
        for j in [0, width]:
            if np.abs(approx[i, 0, 0] - j) <= snap_dist:
                approx[i, 0, 0] = j
        for j in [0, height]:
            if np.abs(approx[i, 0, 1] - j) <= snap_dist:
                approx[i, 0, 1] = j
    return approx


def add_vertices_from_mask(mpath, vertices, epsilon):
    im = cv2.imread(mpath, 0)
    if im is None:
        raise RenderModuleException("could not read %s\n"
                                    "if recalculate_masks = False, are you "
                                    "sure the masks are there?" % mpath) 
    im = cv2.threshold(im, 127, 255, cv2.THRESH_BINARY)[1]
    im2, contours, h = cv2.findContours(
        im, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    cf_vertices = []
    for c in contours:
        approx = approx_snap_contour(c, im.shape[1], im.shape[0], epsilon)
        cf_vertices.append(np.array(approx).squeeze(axis=1))

    for v in np.concatenate(cf_vertices):
        if v not in vertices:
            vertices = np.vstack((vertices, v))

    return vertices


def baseline_vertices(width, height, nxy):
    xt, yt = np.meshgrid(
            np.linspace(0, width, nxy[0]),
            np.linspace(0, height, nxy[1]))
    return np.vstack((xt.flatten(), yt.flatten())).transpose()


def tps_from_vertices(vertices):
    tf = renderapi.transform.ThinPlateSplineTransform()
    tf.ndims = 2
    tf.nLm = vertices.shape[0]
    tf.aMtx = np.array([[0.0, 0.0], [0.0, 0.0]])
    tf.bVec = np.array([0.0, 0.0])
    tf.srcPts = vertices.transpose()
    tf.dMtxDat = np.zeros_like(tf.srcPts)
    return tf


def add_new_tforms(resolved, nxy_baseline, epsilon):
    refids = np.array([r.transformId for r in resolved.transforms])

    for t in resolved.tilespecs:
        vertices = baseline_vertices(t.width, t.height, nxy_baseline)

        if t.ip['0']['maskUrl'] is not None:
            impath = from_uri(t.ip['0']['maskUrl'])
            vertices = add_vertices_from_mask(impath, vertices, epsilon)


        # need to transform vertices through tforms
        for tf in t.tforms:
            if isinstance(tf, renderapi.transform.ReferenceTransform):
                rind = np.argwhere(refids == tf.refId)[0][0]
                vertices = resolved.transforms[rind].tform(vertices)
            else:
                vertices = tf.tform(vertices)

        tf = tps_from_vertices(vertices)
        t.tforms.append(tf)

    return resolved.tilespecs


def zjob(fargs):
    [z, args] = fargs

    render = renderapi.connect(**args['render'])
    resolved = renderapi.resolvedtiles.get_resolved_tiles_from_z(
            args['input_stack'],
            float(z),
            render=render)

    masks = get_mask_lists(
            resolved.tilespecs,
            args['label_input_dirs'],
            exts=args['mask_exts'])

    combined = combine_masks(masks, args['mask_output_dir'], args['recalculate_masks'])

    for t in resolved.tilespecs:
        if t.tileId in combined:
            for lvl, maskUrl in combined[t.tileId].items():
                t.ip[lvl].maskUrl = to_uri(maskUrl)

    new_tilespecs = add_new_tforms(
            resolved, args['baseline_vertices'], args['mask_epsilon'])

    renderapi.client.import_tilespecs(
            args['output_stack'],
            new_tilespecs,
            sharedTransforms=resolved.transforms,
            render=render)

    return


class MakeFineInputStack(StackInputModule, StackOutputModule):
    default_schema = MakeFineInputStackSchema
    default_output_schema = MakeFineOutputStackSchema

    def run(self):
        render = renderapi.connect(** self.args['render'])
        renderapi.stack.create_stack(self.args['output_stack'], render=render)
        renderapi.stack.set_stack_state(
                self.args['output_stack'], state='LOADING', render=render)

        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            fargs = []
            for z in self.args['zValues']:
                fargs.append([z, self.args])
            pool.imap_unordered(zjob, fargs)

            #zjob(fargs[0])

        try:
            if self.args['close_stack']:
                renderapi.stack.set_stack_state(
                        self.args['output_stack'],
                        state='COMPLETE',
                        render=render)
        except renderapi.errors.RenderError:
            pass


if __name__ == "__main__":
    rmod = MakeFineInputStack(input_data=example_input)
    rmod.run()
