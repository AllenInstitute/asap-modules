import renderapi
import numpy as np 
import matplotlib.pyplot as plt

from ..module.render_module import RenderModule, RenderModuleException

ex = {
    "render":{
        "host": "http://em-131db",
        "port": 8080,
        "owner": "TEM",
        "project": "17797_1R",
        "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts"
    },
    "montage_stack": "em_2d_montage_solved_py",
    "downsampled_stack": "em_2d_montage_solved_py_0_01_mapped",
    "match_owner": "TEM",
    "match_collection": "chunk_rough_align_point_matches",
    "minZ": 21457,
    "maxZ": 21616,
    "pool_size": 10
}

from ..module.schemas import RenderParameters
from argschema.fields import Str, Int, List
from argschema.schemas import DefaultSchema

class RoughAlignPreCheckSchema(RenderParameters):
    montage_stack = Str(
        required=True,
        description="Montage stack")
    downsampled_stack = Str(
        required=True,
        description="Pre rough aligned downsampled stack")
    match_owner = Str(
        required=False,
        default=None,
        missing=None,
        description="Match collection owner")
    match_collection = Str(
        required=True,
        description="Match collection name")
    new_z = List(
        Int,
        required=False,
        default=None,
        cli_as_single_argument=True,
        description="List of new z values to be mapped to")
    old_z = List(
        Int,
        required=True,
        cli_as_single_argument=True,
        description="List of old z values") 
    pool_size = Int(
        required=False,
        default=10,
        missing=10,
        description="Pool size")

class RoughAlignPreCheckOutputSchema(DefaultSchema):
    multi_tile_sections = List(
        Int,
        required=True,
        cli_as_single_argument=True,
        description="List of Zs with multiple tiles in downsample stack")
    invalid_tileids = List(
        Str,
        required=True,
        cli_as_single_argument=True,
        description="List of invalid, multiple tilesIds in downsample stack")
    missing_groupids = List(
        Int,
        required=True,
        cli_as_single_argument=True,
        description="List of Zs with no point matches in the match collection")




class RoughAlignPreCheck(RenderModule):
    default_schema = RoughAlignPreCheckSchema
    default_output_schema = RoughAlignPreCheckOutputSchema
    def run(self):
        newzrange = self.args['new_z']
        oldzrange = self.args['old_z']
        if len(newzrange) == 0:
            raise RenderModuleException('Need a list of z values')
        
        if len(newzrange) == len(oldzrange):
            raise RenderModuleException('Length of z ranges must match')
        
        zvalues = renderapi.stack.get_z_values_for_stack(self.args['downsampled_stack'], self.render)
        filtered_zvalues = []
        
        filtoldz = []
        filtnewz = []
        for z1, z2 in (oldzrange, newzrange):
            if z2 in zvalues:
                filtoldz.append(z1)
                filtnewz.append(z2)

        # check if there are missing z values
        missing_zs = list(set(newzrange).difference(filtnewz))

        # get point match group ids and check if all sections have point matches
        # TODO: should also check if pID and qID match with tileIds
        groupids = renderapi.pointmatch.get_match_groupIds(self.args['match_collection'],
                                                           owner=self.args['match_owner'],
                                                           render=self.render)
        groupids = [int(float(g)) for g in groupids]
        missing_groupids = [f for f in filtnewz if not(f in groupids)]


        more_tspecs_ids = []
        invalid_tileids = []
        for i, z in enumerate(filtnewz):
            # get tilespecs for this z
            ts = renderapi.tilespec.get_tile_specs_from_z(self.args['downsampled_stack'], z, render=self.render)

            # check if any section has more than one tile in tilespecs
            if len(ts) > 1:
                more_tspecs_ids.append(z)
                # check which one is not valid
                # the downsampled stack's tileId is some tileId from the montage stack
                tspecs = renderapi.tilespec.get_tile_specs_from_z(self.args['montage_stack'], filtoldz[i], render=self.render)
                tileIds = [t.tileId for t in tspecs]
                for t in ts:
                    if not(t.tileId in tileIds):
                        invalid_tileids.append(t.tileId)

        self.output({'multi_tile_sections': more_tspecs_ids,
                     'invalid_tileids': invalid_tileids,
                     'missing_groupids': missing_groupids})


if __name__=="__main__":
    mod = RoughAlignPreCheck(input_data=ex)
    mod.run()     



        