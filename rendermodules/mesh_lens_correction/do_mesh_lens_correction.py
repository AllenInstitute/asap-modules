import os
import json
import renderapi
import tempfile

from ..module.render_module import RenderModule

from rendermodules.mesh_lens_correction.schemas import MeshLensCorrectionSchema, MeshLensCorrectionOutputSchema
from rendermodules.dataimport.generate_EM_tilespecs_from_metafile import GenerateEMTileSpecsModule
from rendermodules.pointmatch.create_tilepairs import TilePairClientModule
from rendermodules.mesh_lens_correction.LensPointMatches import generate_point_matches
from rendermodules.mesh_lens_correction.MeshAndSolveTransform import MeshAndSolveTransform
from rendermodules.em_montage_qc.detect_montage_defects import DetectMontageDefectsModule

example = {
    "render": {
        "host": "em-131snb1",
        "port": 8080,
        "owner": "gayathrim",
        "project": "lens_corr",
        "client_scripts":"/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
        "memGB":"2G"
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
    "match_collection":"raw_lens_matches",
    "nfeature_limit": 20000,
    "output_dir": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch",
    "outfile": "lens_out.json"
}

class MeshLensCorrection(RenderModule):
    default_schema = MeshLensCorrectionSchema
    default_output_schema = MeshLensCorrectionOutputSchema

    @staticmethod
    def get_sectionId_from_z(z):
        return str(float(z))

    @staticmethod
    def get_sectionId_from_metafile(metafile):
        j = json.load(open(metafile, 'r'))
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
        ex['metafile'] = self.args['metafile']
        ex['stack'] = self.args['input_stack']
        ex['overwrite_zlayer'] = self.args['overwrite_zlayer']
        ex['close_stack'] = self.args['close_stack']
        ex['output_stack'] = self.args['input_stack']
        ex['z'] = self.args['z_index']
        ex['sectionId'] = self.args['sectionId']
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

    def get_qc_example(self):
        ex = {}
        ex['render'] = {}
        ex['render']['host'] = self.render.DEFAULT_HOST
        ex['render']['port'] = self.render.DEFAULT_PORT
        ex['render']['owner'] = self.render.DEFAULT_OWNER
        ex['render']['project'] = self.render.DEFAULT_PROJECT
        ex['render']['client_scripts'] = self.render.DEFAULT_CLIENT_SCRIPTS
        ex['match_collection'] = self.args['match_collection']
        ex['prestitched_stack'] = self.args['input_stack']
        ex['poststitched_stack'] = self.args['output_stack']
        ex['out_html_dir'] = self.args['output_dir']
        ex['minZ'] = self.args['z_index']
        ex['maxZ'] = self.args['z_index']
        return ex

    def run(self):
        self.args['sectionId'] = self.get_sectionId_from_metafile(self.args['metafile'])

        if self.args['output_dir'] is None:
            self.args['output_dir'] = tempfile.mkdtemp()

        if self.args['outfile'] is None:
            outfile = tempfile.NamedTemporaryFile(suffix=".json",
                                                  delete=False,
                                                  dir=self.args['output_dir'])
            outfile.close()
            self.args['outfile'] = outfile.name

        # check if match_collection exists
        collections = renderapi.pointmatch.get_matchcollections(render=self.render)
        if self.args['match_collection'] in collections:
            # check if the point match exists
            groupids = renderapi.pointmatch.get_match_groupIds(self.args['match_collection'], render=self.render)
            if str(float(self.args['z_index'])) in groupids:
                renderapi.pointmatch.delete_point_matches_between_groups(self.args['match_collection'],
                                                                        str(float(self.args['z_index'])),
                                                                        str(float(self.args['z_index'])),
                                                                        render=self.render)

        out_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        out_file.close()

        # create a stack with the lens correction tiles
        ts_example = self.generate_ts_example()
        mod = GenerateEMTileSpecsModule(input_data=ts_example,
                                        args=['--output_json', out_file.name])
        mod.run()

        # generate tile pairs for this section in the input stack
        tp_example = self.generate_tilepair_example()
        tp_mod = TilePairClientModule(input_data=tp_example,
                                        args=['--output_json', out_file.name])
        tp_mod.run()

        with open(tp_mod.args['output_json'], 'r') as f:
            js = json.load(f)
        self.args['pairJson'] = js['tile_pair_file']

        # generate point matches
        generate_point_matches(self.render,
                               self.args['pairJson'],
                               self.args['input_stack'],
                               self.args['match_collection'],
                               self.args['matchMax'],
                               nfeature_limit=self.args['nfeature_limit'])

        meshclass = MeshAndSolveTransform()
        # find the lens correction, write out to new stack
        lens_correction_json = meshclass.MeshAndSolve(self.render,
                                            self.args['input_stack'],
                                            self.args['output_stack'],
                                            self.args['match_collection'],
                                            self.args['sectionId'],
                                            self.args['nvertex'],
                                            self.args['output_dir'],
                                            self.args['outfile'],
                                            self.args['regularization']['default_lambda'],
                                            self.args['regularization']['translation_factor'],
                                            self.args['regularization']['lens_lambda'],
                                            self.args['close_stack'])

        # run montage qc on the new stack
        qc_example = self.get_qc_example()
        qc_mod = DetectMontageDefectsModule(input_data=qc_example, args=['--output_json', out_file.name])
        qc_mod.run()

        try:
            self.output({'output_json': lens_correction_json, 'qc_json': out_file.name})
        except AttributeError as e:
            self.logger.error(e)

if __name__=="__main__":
    mod = MeshLensCorrection(input_data=example)
    mod.run()
