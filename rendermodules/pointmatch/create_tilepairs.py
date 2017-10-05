
import json
import os
import subprocess
from argschema.fields import Bool, Float, Int, Nested, Str, InputDir
from argschema.schemas import DefaultSchema
import marshmallow as mm
import renderapi
from ..module.render_module import RenderModule, RenderParameters

if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.pointmatch.create_tilepairs"


example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8998,
        "owner": "gayathri",
        "project": "MM2",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-java-client/src/main/scripts"
    },
    "minZ":1015,
    "maxZ":1030,
    "zNeighborDistance":0,
    "baseStack":"mm2_acquire_8bit_reimage",
    "stack":"mm2_acquire_8bit_reimage",
    "xyNeighborFactor": 0.9,
    "excludeCornerNeighbors":"true",
    "excludeSameLayerNeighbors":"false",
    "excludeCompletelyObscuredTiles":"true",
    "output_dir":"/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/scratch/montageTilepairs"
}


class TilePairClientParameters(RenderParameters):
    stack = Str(
        required=True,
        description="input stack to which tilepairs need to be generated")
    baseStack = Str(
        required=False,
        default=stack,
        description="Base stack")
    minZ = Int(
        required=False,
        default=None,
        description="z min for generating tilepairs")
    maxZ = Int(
        required=False,
        default=None,
        description="z max for generating tilepairs")
    xyNeighborFactor = Float(
        required=False,
        default=0.9,
        description="Multiply this by max(width, height) of each tile to determine radius for locating neighbor tiles")
    zNeighborDistance = Int(
        required=False,
        default=2,
        description="Look for neighbor tiles with z values less than or equal to this distance from the current tile's z value")
    excludeCornerNeighbors = Bool(
        required=False,
        default=True,
        description="Exclude neighbor tiles whose center x and y is outside the source tile's x and y range respectively")
    excludeSameLayerNeighbors = Bool(
        required=False,
        default=False,
        description="Exclude neighbor tiles in the same layer (z) as the source tile")
    excludeCompletelyObscuredTiles = Bool(
        required=False,
        default=True,
        description="Exclude tiles that are completely obscured by reacquired tiles")
    output_dir = Str(
        required=True,
        description="Output directory path to save the tilepair json file")
    memGB = Str(
        required=False,
        default='6G',
        description="Memory for the java client to run")



class TilePairClientModule(RenderModule):

    def __init__(self, schema_type=None, *args, **kwargs):
        if schema_type is None:
            schema_type = TilePairClientParameters
        super(TilePairClientModule, self).__init__(
            schema_type=schema_type, *args, **kwargs)

        self.client_class = 'org.janelia.render.client.TilePairClient'
        self.client_script_name = 'run_ws_client.sh'

    @property
    def default_client_script(self):
        basecmd = os.path.join(
                        self.args['render']['client_scripts'],
                        self.client_script_name)
        if not os.path.isfile(basecmd):
            raise TilePairClientException(
                'client script {} does not exist'.format(basecmd))
        elif not os.access(basecmd, os.X_OK):
            raise TilePairClientException(
                'client script {} is not executable'.format(basecmd))
        return basecmd

    def run(self):
        basecmd = self.default_client_script

        baseDataUrl = "%s:%d/render-ws/v1"%(self.args['render']['host'], self.args['render']['port'])

        zvalues = self.render.run(
            renderapi.stack.get_z_values_for_stack, self.args['stack'])

        if self.args['minZ'] is not None:
            self.args['minZ'] = self.args['minZ'] if self.args['minZ'] > min(zvalues) else min(zvalues)
        elif self.args['maxZ'] is not None:
            self.args['maxZ'] = self.args['maxZ'] if self.args['maxZ'] < max(zvalues) else max(zvalues)
        else:
            self.args['minZ'] = min(zvalues)
            self.args['maxZ'] = max(zvalues)

        tilepairJsonFile = "tile_pairs_%s_z_%d_to_%d_dist_%d.json"%(self.args['stack'], self.args['minZ'], self.args['maxZ'], self.args['zNeighborDistance'])
        tilepairJsonFile = os.path.join(
                                self.args['output_dir'],
                                tilepairJsonFile)

        tilepairs = self.render.run(
                        renderapi.client.tilePairClient,
                        self.args['stack'],
                        self.args['minZ'],
                        self.args['maxZ'],
                        outjson=tilepairJsonFile,
                        basestack=self.args['baseStack'],
                        xyNeighborFactor=self.args['xyNeighborFactor'],
                        zNeighborDistance=self.args['zNeighborDistance'],
                        excludeCornerNeighbors=self.args['excludeCornerNeighbors'],
                        excludeSameLayerNeighbors=self.args['excludeSameLayerNeighbors'],
                        excludeCompletelyObscuredTiles=self.args['excludeCompletelyObscuredTiles'])


        # non-render-python way of calling TilePairClient
        '''
        run_cmd = [
                    basecmd,
                    self.args['memGB'],
                    self.client_class,
                    "--baseDataUrl {}".format(baseDataUrl),
                    "--owner {}".format(self.args['render']['owner']),
                    "--project {}".format(self.args['render']['project']),
                    "--baseOwner {}".format(self.args['render']['owner']),
                    "--baseProject {}".format(self.args['render']['project']),
                    "--baseStack {}".format(self.args['baseStack']),
                    "--stack {}".format(self.args['stack']),
                    "--minZ {}".format(self.args['minZ']),
                    "--maxZ {}".format(self.args['maxZ']),
                    "--xyNeighborFactor {}".format(self.args['xyNeighborFactor']),
                    "--zNeighborDistance {}".format(self.args['zNeighborDistance']),
                    "--excludeCornerNeighbors {}".format(self.args['excludeCornerNeighbors']),
                    "--excludeSameLayerNeighbors {}".format(self.args['excludeSameLayerNeighbors']),
                    "--excludeCompletelyObscuredTiles {}".format(self.args['excludeCompletelyObscuredTiles']),
                    "--toJson {}".format(tilepairJsonFile)
                    ]

        subprocess.call(run_cmd)
        '''

if __name__ == "__main__":
    module = TilePairClientModule(input_data=example)
    #module = TilePairClientModule(schema_type=TilePairClientParameters)
    module.run()
