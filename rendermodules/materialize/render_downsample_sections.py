from functools import partial
import time
from multiprocessing.pool import ThreadPool
import numpy as np
import renderapi
from rendermodules.materialize.schemas import (RenderSectionAtScaleParameters,
                                               RenderSectionAtScaleOutput)
from ..module.render_module import RenderModule, RenderModuleException


example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "russelt",
        "project": "Reflections",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_latest/render-ws-java-client/src/main/scripts"
    },
    "input_stack": "Secs_1015_1099_5_reflections_mml6_montage",
    "image_directory": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch",
    "imgformat":"png",
    "scale": 0.01,
    "minZ": 1015,
    "maxZ": 1016
}

example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "gayathri",
        "project": "Tests",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_latest/render-ws-java-client/src/main/scripts"
    },
    "input_stack": "rough_test_montage_stack",
    "image_directory": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch",
    "imgformat":"png",
    "scale": 0.1,
    "minZ": 1020,
    "maxZ": 1022
}


def check_stack_for_mipmaps(render, input_stack, zvalues):
    # this function checks for the mipmaplevels for the first section in the stack
    # Assumes that all the sections in the stack has mipmaps stored if the first section has mipmaps

    # z = random.choice(zvalues)
    z = zvalues[0]
    tilespecs = render.run(renderapi.tilespec.get_tile_specs_from_z,
                           input_stack, z)
    for ts in tilespecs:
        if len(ts.ip) > 1:
            return True
    return False


def create_tilespecs_without_mipmaps(render, montage_stack, level, z):
    """return tilespecs missing mipmaplevels above the specified level"""
    ts = render.run(renderapi.tilespec.get_tile_specs_from_z, montage_stack, z)
    for t in ts:
        t.ip = renderapi.tilespec.ImagePyramid({
            lvl: mipmap for lvl, mipmap in t.ip.items()
            if int(lvl) <= int(level)})
    return ts


# FIXME this should be provided in render-python external
class WithThreadPool(ThreadPool):
    def __init__(self, *args, **kwargs):
        super(WithThreadPool, self).__init__(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()
        self.join()


class RenderSectionAtScale(RenderModule):
    default_schema = RenderSectionAtScaleParameters
    default_output_schema = RenderSectionAtScaleOutput

    @classmethod
    def downsample_specific_mipmapLevel(
            cls, zvalues, input_stack=None, level=1, pool_size=1,
            image_directory=None, scale=None, imgformat=None, doFilter=None,
            fillWithNoise=None, filterListName=None,
            render=None, do_mp=True, **kwargs):
        # temporary hack for nested pooling woes
        poolclass = (renderapi.client.WithPool if do_mp else WithThreadPool)

        stack_has_mipmaps = check_stack_for_mipmaps(
            render, input_stack, zvalues)

        ds_source = input_stack
        # check if there are mipmaps in this stack
        if stack_has_mipmaps:
            print("stack has mipmaps")
            # clone the input stack to a temporary one with level 1 mipmap alone
            temp_no_mipmap_stack = "{}_no_mml_zs{}_ze{}_t{}".format(
                input_stack, min(zvalues), max(zvalues),
                time.strftime("%m%d%y_%H%M%S"))

            mypartial = partial(create_tilespecs_without_mipmaps,
                                render, input_stack, level)

            with poolclass(pool_size) as pool:
                # jsonfiles = pool.map(mypartial, zvalues)
                all_tilespecs = [i for l in pool.map(mypartial, zvalues)
                                 for i in l]

            # create stack - overwrites existing one
            render.run(renderapi.stack.create_stack, temp_no_mipmap_stack)

            # set stack state to LOADING
            render.run(renderapi.stack.set_stack_state,
                       temp_no_mipmap_stack, state='LOADING')

            render.run(renderapi.client.import_tilespecs_parallel,
                       temp_no_mipmap_stack,
                       all_tilespecs,
                       poolsize=pool_size,
                       close_stack=True,
                       mpPool=poolclass)
            ds_source = temp_no_mipmap_stack

        render.run(renderapi.client.renderSectionClient,
                   ds_source,
                   image_directory,
                   zvalues,
                   scale=scale,
                   format=imgformat,
                   doFilter=doFilter,
                   fillWithNoise=fillWithNoise,
                   filterListName=filterListName)

        if stack_has_mipmaps:
            # delete the temp stack
            render.run(renderapi.stack.delete_stack,
                       temp_no_mipmap_stack)
        return ds_source

    def run(self):

        zvalues1 = self.render.run(
            renderapi.stack.get_z_values_for_stack,
            self.args['input_stack'])

        if self.args['minZ'] == -1 or self.args['maxZ'] == -1:
            self.args['minZ'] = min(zvalues1)
            self.args['maxZ'] = max(zvalues1)
        elif self.args['minZ'] > self.args['maxZ']:
            raise RenderModuleException('Invalid Z range: {} > {}'.format(
                self.args['minZ'], self.args['maxZ']))

        zvalues1 = np.array(zvalues1)
        zrange = range(int(self.args['minZ']), int(self.args['maxZ'])+1)
        zvalues = list(set(zvalues1).intersection(set(zrange)))

        if not zvalues:
            raise RenderModuleException(
                'No valid zvalues found in stack for '
                'given range {} - {}'.format(
                    self.args['minZ'], self.args['maxZ']))

        self.args['temp_stack'] = self.downsample_specific_mipmapLevel(
            zvalues, **dict(self.args, **{'render': self.render}))

        self.output({"image_directory": self.args['image_directory'],
                     "temp_stack": self.args['temp_stack']})


if __name__ == "__main__":
    mod = RenderSectionAtScale(input_data=example)
    mod.run()
