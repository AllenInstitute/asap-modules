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
        "split_divided_tiles": True,
        "pool_size": 7,
        "close_stack": True
}


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
            mpath = urllib.parse.unquote(
                        urllib.parse.urlparse(
                            t.ip['0']['maskUrl']).path)
            results[t.tileId]['masks'].append({
                'path': mpath,
                'invert': False})
        ind = np.argwhere(maskbasenames == t.tileId.split('.')[0]).flatten()
        for i in ind:
            results[t.tileId]['masks'].append({
                'path': maskfiles[i],
                'invert': True})
    return results


def combine_masks(masks, mask_dir):
    results = {}
    for tid, v in masks.items():
        combined = None
        if len(v['masks']) == 0:
            continue
        for m in v['masks']:
            im = cv2.imread(m['path'], 0)
            if m['invert']:
                im = 255 - im
            if combined is None:
                combined = im
            else:
                combined[im == 0] = 0
        mpath = os.path.join(
                    mask_dir,
                    tid + '.png')
        if not cv2.imwrite(mpath, combined):
            raise IOError('cv2.imwrite() could not write to %s' % mask_dir)

        root, ext = os.path.splitext(mpath)

        results[tid] = create_mipmaps(
            mpath,
            outputDirectory=mask_dir,
            mipmaplevels=v['levels'],
            outputformat=ext.split('.')[-1],
            convertTo8bit=False,
            force_redo=True,
            block_func="min")  

        os.remove(mpath)

    return results


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

    combined = combine_masks(masks, args['mask_output_dir'])

    for t in resolved.tilespecs:
        if t.tileId in combined:
            for lvl, maskUrl in combined[t.tileId].items():
                t.ip[lvl].maskUrl = pathlib.Path(maskUrl).as_uri()

    renderapi.client.import_tilespecs(
            args['output_stack'],
            resolved.tilespecs,
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

        try:
            if self.args['close_stack']:
                renderapi.stack.set_stack_state(
                        self.args['output_stack'],
                        state='COMPLETE',
                        render=render)
        except render.errors.RenderError:
            pass


if __name__ == "__main__":
    rmod = MakeFineInputStack(input_data=example_input)
    rmod.run()
