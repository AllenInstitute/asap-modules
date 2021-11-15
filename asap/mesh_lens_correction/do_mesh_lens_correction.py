#!/usr/bin/env python
import datetime
import json
import os
from shutil import copyfile
import tempfile

from bigfeta import jsongz
import cv2
import numpy as np
import renderapi

from em_stitch.lens_correction.mesh_and_solve_transform \
    import MeshAndSolveTransform

from asap.module.render_module import (
    RenderModule, RenderModuleException)
from asap.mesh_lens_correction.schemas \
        import MeshLensCorrectionSchema, DoMeshLensCorrectionOutputSchema
from asap.dataimport.generate_EM_tilespecs_from_metafile \
        import GenerateEMTileSpecsModule
from asap.pointmatch.create_tilepairs \
        import TilePairClientModule
from asap.pointmatch.generate_point_matches_opencv \
        import GeneratePointMatchesOpenCV
from asap.utilities import uri_utils

example = {
    "render": {
        "host": "em-131db.corp.alleninstitute.org",
        "port": 8080,
        "owner": "danielk",
        "project": "lens_corr",
        "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
        "memGB": "2G"
    },
    "regularization": {
        "default_lambda": 1e5,
        "translation_factor": 1e-5,
        "lens_lambda": 1e-5
    },
    "input_stack": "raw_lens_stack",
    "output_stack": "lens_corrected_stack",
    "overwrite_zlayer": True,
    "close_stack": True,
    "z_index": 100,
    "metafile": "/allen/programs/celltypes/workgroups/em-connectomics/danielk/em_lens_correction/test_data/_metadata_20180220175645_247488_8R_tape070A_05_20180220175645_reference_0_.json",
    "match_collection": "raw_lens_matches",
    "nfeature_limit": 20000,
    "output_dir": "/allen/programs/celltypes/workgroups/em-connectomics/danielk/tmp",
    "outfile": "lens_out.json",
    "output_json": "./mesh_lens_output.json",
    "mask_coords": [[0, 100], [100, 0], [3840, 0], [3840, 3840], [0, 3840]],
    "mask_dir": "/allen/programs/celltypes/workgroups/em-connectomics/danielk/masks_for_stacks"
}


class DoMeshException(RenderModuleException):
    # placeholder
    pass


def delete_matches_if_exist(render, owner, collection, sectionId):
    collections = renderapi.pointmatch.get_matchcollections(
            render=render,
            owner=owner)
    collection_names = [c['collectionId']['name'] for c in collections]
    if collection in collection_names:
        groupids = renderapi.pointmatch.get_match_groupIds(
                collection,
                render=render)
        if sectionId in groupids:
            renderapi.pointmatch.delete_point_matches_between_groups(
                    collection,
                    sectionId,
                    sectionId,
                    render=render)


def make_mask_from_coords(w, h, coords):
    cont = np.array(coords).astype('int32')
    cont = np.reshape(cont, (cont.shape[0], 1, cont.shape[1]))
    mask = np.zeros((h, w)).astype('uint8')
    mask = cv2.fillConvexPoly(mask, cont, color=255)
    return mask


def make_mask(mask_dir, w, h, coords, mask_file=None, basename=None):

    def get_new_filename(fname):
        noext, fext0 = os.path.splitext(fname)
        fext = str(fext0)
        while os.path.exists(noext + fext):
            fext = '%s' % datetime.datetime.now().strftime("_%Y%m%d%H%M%S%f")
            fext += fext0
        return noext + fext

    maskUrl = None
    if mask_file is not None:
        # copy the provided file directly over
        maskUrl = get_new_filename(
                      os.path.join(
                          mask_dir,
                          os.path.basename(mask_file)))
        copyfile(mask_file, maskUrl)

    if (maskUrl is None) & (coords is not None):
        mask = make_mask_from_coords(w, h, coords)
        if basename is None:
            basename = 'lens_corr_mask.png'
        maskUrl = get_new_filename(os.path.join(mask_dir, basename))
        if not cv2.imwrite(maskUrl, mask):
            raise IOError('cv2.imwrite() could not write to %s' % mask_dir)

    return maskUrl


class MeshLensCorrection(RenderModule):
    default_schema = MeshLensCorrectionSchema
    default_output_schema = DoMeshLensCorrectionOutputSchema

    @staticmethod
    def get_sectionId_from_metafile_uri(metafile_uri):
        j = json.loads(uri_utils.uri_readbytes(
            metafile_uri))
        sectionId = j[0]['metadata']['grid']
        return sectionId

    def generate_ts_example(self):
        ex = {}
        ex['render'] = {}
        ex['render']['host'] = self.render.DEFAULT_HOST
        ex['render']['port'] = self.render.DEFAULT_PORT
        ex['render']['owner'] = self.render.DEFAULT_OWNER
        ex['render']['project'] = self.render.DEFAULT_PROJECT
        ex['render']['client_scripts'] = self.render.DEFAULT_CLIENT_SCRIPTS
        ex['metafile_uri'] = self.args['metafile_uri']
        ex['stack'] = self.args['input_stack']
        ex['overwrite_zlayer'] = self.args['overwrite_zlayer']
        ex['close_stack'] = self.args['close_stack']
        ex['output_stack'] = self.args['input_stack']
        ex['z'] = self.args['z_index']
        ex['sectionId'] = self.args['sectionId']
        ex['maskUrl'] = self.maskUrl
        return ex

    def generate_tilepair_example(self):
        ex = {}
        ex['render'] = {}
        ex['render']['host'] = self.render.DEFAULT_HOST
        ex['render']['port'] = self.render.DEFAULT_PORT
        ex['render']['owner'] = self.render.DEFAULT_OWNER
        ex['render']['project'] = self.render.DEFAULT_PROJECT
        ex['render']['client_scripts'] = self.render.DEFAULT_CLIENT_SCRIPTS
        ex['minZ'] = self.args['z_index']
        ex['maxZ'] = self.args['z_index']
        ex['zNeighborDistance'] = 0
        ex['stack'] = self.args['input_stack']
        ex['xyNeighborFactor'] = 0.1
        ex['excludeCornerNeighbors'] = False
        ex['excludeSameLayerNeighbors'] = False
        ex['excludeCompletelyObscuredTiles'] = True
        ex['output_dir'] = self.args['output_dir']

        ex['outfile'] = self.args['outfile']
        return ex

    def get_pm_args(self):
        args_for_pm = dict(self.args)
        args_for_pm['render'] = self.args['render']
        args_for_pm['pairJson'] = self.args['pairJson']
        args_for_pm['input_stack'] = self.args['input_stack']
        args_for_pm['match_collection'] = self.args['match_collection']
        return args_for_pm

    def run(self):
        self.args['sectionId'] = self.get_sectionId_from_metafile_uri(
                self.args['metafile_uri'])

        if self.args['output_dir'] is None:
            self.args['output_dir'] = tempfile.mkdtemp()

        if self.args['outfile'] is None:
            outfile = tempfile.NamedTemporaryFile(suffix=".json",
                                                  delete=False,
                                                  dir=self.args['output_dir'])
            outfile.close()
            self.args['outfile'] = outfile.name

        out_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        out_file.close()

        args_for_input = dict(self.args)

        metafile = json.loads(uri_utils.uri_readbytes(
            self.args['metafile_uri']))

        self.maskUrl = make_mask(
                self.args['mask_dir'],
                metafile[0]['metadata']['camera_info']['width'],
                metafile[0]['metadata']['camera_info']['height'],
                self.args['mask_coords'],
                mask_file=self.args['mask_file'],
                basename=uri_utils.uri_basename(
                    self.args['metafile_uri']) + '.png')

        # argschema doesn't like the NumpyArray after processing it once
        # we don't need it after mask creation
        self.args['mask_coords'] = None
        args_for_input['mask_coords'] = None

        # create a stack with the lens correction tiles
        ts_example = self.generate_ts_example()
        mod = GenerateEMTileSpecsModule(input_data=ts_example,
                                        args=['--output_json', out_file.name])
        mod.run()

        if self.args['rerun_pointmatch']:
            # generate tile pairs for this section in the input stack
            tp_example = self.generate_tilepair_example()
            tp_mod = TilePairClientModule(
                    input_data=tp_example,
                    args=['--output_json', out_file.name])
            tp_mod.run()

            with open(tp_mod.args['output_json'], 'r') as f:
                js = json.load(f)
            self.args['pairJson'] = js['tile_pair_file']

            self.logger.setLevel(self.args['log_level'])
            delete_matches_if_exist(
                    self.render,
                    self.args['render']['owner'],
                    self.args['match_collection'],
                    self.args['sectionId'])

            args_for_pm = self.get_pm_args()
            pmgen = GeneratePointMatchesOpenCV(
                    input_data=args_for_pm,
                    args=['--output_json', out_file.name])
            pmgen.run()

        # load these up in memory to pass to actual solver
        rawtilespecs = renderapi.tilespec.get_tile_specs_from_z(
                ts_example['output_stack'],
                ts_example['z'],
                render=renderapi.connect(**ts_example['render']))
        rawtdict = [t.to_dict() for t in rawtilespecs]
        matches = renderapi.pointmatch.get_matches_within_group(
                self.args['match_collection'],
                self.args['sectionId'],
                render=renderapi.connect(**self.args['render']))

        self.logger.setLevel(self.args['log_level'])

        solver_args = {
                'nvertex': self.args['nvertex'],
                'regularization': self.args['regularization'],
                'good_solve': self.args['good_solve'],
                'tilespecs': rawtdict,
                'matches': matches,
                'output_dir': self.args['output_dir'],
                'outfile': 'resolvedtiles.json.gz',
                'compress_output': False,
                'log_level': self.args['log_level'],
                'timestamp': True}

        meshclass = MeshAndSolveTransform(
                input_data=solver_args, args=[])
        # find the lens correction, write out to new stack
        meshclass.run()
        with open(meshclass.args['output_json'], 'r') as f:
            jout = json.load(f)
        resolved = renderapi.resolvedtiles.ResolvedTiles(
                json=jsongz.load(jout['resolved_tiles']))

        tform_out = os.path.join(
                self.args['output_dir'],
                'lens_correction_out.json')
        with open(tform_out, 'w') as f:
            json.dump(resolved.transforms[0].to_dict(), f)

        try:
            self.output(
                    {'output_json': tform_out,
                     'maskUrl': self.maskUrl})
        except AttributeError as e:
            self.logger.error(e)


if __name__ == "__main__":
    mod = MeshLensCorrection(input_data=example)
    mod.run()
