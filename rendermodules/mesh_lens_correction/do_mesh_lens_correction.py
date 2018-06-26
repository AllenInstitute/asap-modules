import os
import json
import renderapi
import tempfile

from ..module.render_module import RenderModule

from rendermodules.mesh_lens_correction.schemas import LensCorrectionSchema, LensCorrectionOutputSchema
from rendermodules.dataimport.generate_EM_tilespecs_from_metafile import GenerateEMTileSpecsModule
from rendermodules.pointmatch.create_tilepairs import TilePairClientModule
from rendermodules.mesh_lens_correction.LensPointMatches import LensPointMatches
from rendermodules.mesh_lens_correction.MeshAndSolveTransform import MeshAndSolveTransform
from rendermodules.em_montage_qc.detect_montage_defects import DetectMontageDefectsModule


example = {
  "render":{
     "host":"em-131snb1",
     "port":8080,
     "owner":"gayathrim",
     "project":"lens_corr",
     "client_scripts":"/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
     "memGB":"2G"
  },
  "z_index": 100,
  "overwrite_zlayer":True,
  "input_stack":"raw_lens_stack",
  "close_stack":"True",
  "metafile":"/allen/programs/celltypes/workgroups/em-connectomics/danielk/em_lens_correction/test_data/_metadata_20180220175645_247488_8R_tape070A_05_20180220175645_reference_0_.json",
  "match_collection":"raw_lens_matches",
  "nfeature_limit": 20000,
  "regularization":{
        "default_lambda":1e5,
        "translation_factor":1e-5,
        "lens_lambda":1e-5
  },
  "output_stack": "lens_corrected_stack",
  "output_dir":"/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch",
  "out_html_dir":"/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch"
}

class MeshLensCorrection(RenderModule):
    default_schema = LensCorrectionSchema
    default_output_schema = LensCorrectionOutputSchema

    def get_section_id_from_metafile(self):
        j = json.load(open(self.args['metafile'], 'r'))
        self.sectionId = j[0]['metadata']['grid']
        return self.sectionId
    
    @staticmethod
    def get_sectionId_from_z(z):
        return str(float(z))

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
        if self.args['output_dir'] is None:
            ex['output_dir'] = tempfile.mkdtemp()
            self.args['output_dir'] = ex['output_dir']
        else:
            ex['output_dir'] = self.args['output_dir']
        return ex

    def generate_ptmatch_example(self):
        ex = {}
        ex['render'] = {}
        ex['render']['host'] = self.render.DEFAULT_HOST
        ex['render']['port'] = self.render.DEFAULT_PORT
        ex['render']['owner'] = self.render.DEFAULT_OWNER
        ex['render']['project'] = self.render.DEFAULT_PROJECT
        ex['render']['client_scripts'] = self.render.DEFAULT_CLIENT_SCRIPTS
        ex['match_collection'] = self.args['match_collection']
        ex['pairJson'] = self.args['pairJson']
        ex['metafile'] = self.args['metafile']
        ex['z_index'] = self.args['z_index']
        ex['input_stack'] = self.args['input_stack']
        return ex

    def get_lens_correction_example(self):
        ex = {}
        ex['render'] = {}
        ex['render']['host'] = self.render.DEFAULT_HOST
        ex['render']['port'] = self.render.DEFAULT_PORT
        ex['render']['owner'] = self.render.DEFAULT_OWNER
        ex['render']['project'] = self.render.DEFAULT_PROJECT
        ex['render']['client_scripts'] = self.render.DEFAULT_CLIENT_SCRIPTS
        ex['match_collection'] = self.args['match_collection']
        ex['close_stack'] = self.args['close_stack']
        ex['regularization'] = self.args['regularization']
        ex['output_dir'] = self.args['output_dir']
        ex['sectionId'] = self.sectionId
        ex['output_stack'] = self.args['output_stack']
        ex['input_stack'] = self.args['input_stack']

        ex['metafile'] = self.args['metafile']
        ex['z_index'] = self.args['z_index']
        ex['out_html_dir'] = self.args['out_html_dir']
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
        ex['out_html_dir'] = self.args['out_html_dir']
        ex['minZ'] = self.args['z_index']
        ex['maxZ'] = self.args['z_index']
        return ex

    def run(self):
        self.sectionId = self.get_sectionId_from_z(self.args['z_index'])

        out_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        out_file.close()
        
        # create a stack with the lens correction tiles
        ts_example = self.generate_ts_example()
        mod = GenerateEMTileSpecsModule(input_data=ts_example, args=['--output_json', out_file.name])
        mod.run()

        # generate tile pairs for this section in the input stack
        tp_example = self.generate_tilepair_example()
        tp_mod = TilePairClientModule(input_data=tp_example, args=['--output_json', out_file.name])
        tp_mod.run()
        with open(tp_mod.args['output_json'], 'r') as f:
            js = json.load(f)
        self.args['pairJson'] = js['tile_pair_file']

        # generate mesh point matches
        pt_example = self.generate_ptmatch_example()
        pt_mod = LensPointMatches(input_data=pt_example, args=['--output_json', out_file.name])
        pt_mod.run()

        # find the lens correction, write out to new stack
        ls_example = self.get_lens_correction_example()
        lens_output = tempfile.NamedTemporaryFile(suffix=".json", dir=self.args['output_dir'], delete=False)
        lens_output.close()
        ls_example['outfile'] = lens_output.name
        mesh_mod = MeshAndSolveTransform(input_data=ls_example, args=['--output_json', lens_output.name])
        mesh_mod.run()

        # run montage qc on the new stack
        qc_example = self.get_qc_example()
        qc_mod = DetectMontageDefectsModule(input_data=qc_example, args=['--output_json', out_file.name])
        qc_mod.run()

        try:
            self.output({'output_json': lens_output.name})
        except AttributeError as e:
            self.logger.error(e)

if __name__=="__main__":
    mod = MeshLensCorrection(input_data=example, args=['--output_json', 'out.json'])
    mod.run()
    