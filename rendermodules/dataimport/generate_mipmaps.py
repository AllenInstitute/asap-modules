from functools import partial

import renderapi
from six.moves import urllib

from rendermodules.dataimport.create_mipmaps import (
    create_mipmaps, create_mipmaps_uri)
from rendermodules.module.render_module import (
    StackInputModule, RenderModuleException)
from rendermodules.dataimport.schemas import (
    GenerateMipMapsParameters, GenerateMipMapsOutput)

if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.dataimport.generate_mipmaps"

example = {
    "render": {
        "host": "10.128.124.14",
        "port": 8998,
        "owner": "gayathri",
        "project": "MM2",
        "client_scripts": "/data/nc-em2/gayathrim/Janelia_Pipeline/render_20170613/render-ws-java-client/src/main/scripts"
    },
    "method": "PIL",
    "input_stack": "mm2_acquire_8bit",
    "output_dir": "/net/aidc-isi1-prd/scratch/aibs/scratch",
    "convert_to_8bit": "False",
    "method": "PIL",
    "imgformat": "tif",
    "levels": 6,
    "force_redo": "True",
    "zstart": 1015,
    "zend": 1015
}


def create_mipmap_from_tuple(mipmap_tuple, levels=[1, 2, 3],
                             imgformat='tif', convertTo8bit=True,
                             force_redo=True, **kwargs):
    (filepath, downdir) = mipmap_tuple
    return create_mipmaps(filepath, outputDirectory=downdir,
                          mipmaplevels=levels, convertTo8bit=convertTo8bit,
                          outputformat=imgformat,
                          force_redo=force_redo, **kwargs)


def create_mipmap_from_tuple_uri(mipmap_tuple, levels=[1, 2, 3],
                                 imgformat='tif', convertTo8bit=True,
                                 force_redo=True, **kwargs):
    (filepath, downdir) = mipmap_tuple
    return create_mipmaps_uri(filepath, outputDirectory=downdir,
                              mipmaplevels=levels, convertTo8bit=convertTo8bit,
                              outputformat=imgformat,
                              force_redo=force_redo, **kwargs)


def get_filepath_from_tilespec(ts):
    mml = ts.ip[0]

    old_url = mml.imageUrl
    filepath_in = urllib.parse.unquote(urllib.parse.urlparse(
        str(old_url)).path)
    return filepath_in


def make_tilespecs_and_cmds(render, inputStack, output_prefix, zvalues, levels,
                            imgformat, convert_to_8bit, force_redo, pool_size,
                            method):
    mipmap_args = []

    for z in zvalues:
        tilespecs = render.run(renderapi.tilespec.get_tile_specs_from_z,
                               inputStack, z)

        for ts in tilespecs:
            mipmap_args.append((ts.ip[0].imageUrl, output_prefix))

    mypartial = partial(
        create_mipmap_from_tuple_uri, method=method,
        levels=list(range(1, levels + 1)),
        convertTo8bit=convert_to_8bit, force_redo=force_redo,
        imgformat=imgformat)

    with renderapi.client.WithPool(pool_size) as pool:
        results = pool.map(mypartial, mipmap_args)

    return mipmap_args


class GenerateMipMaps(StackInputModule):
    default_schema = GenerateMipMapsParameters
    default_output_schema = GenerateMipMapsOutput

    def run(self):
        self.logger.debug('Mipmap generation module')

        """
        # get the list of z indices
        zvalues = self.render.run(renderapi.stack.get_z_values_for_stack,
                                  self.args['input_stack'])
        zvalues = list(set(self.zValues).intersection(set(zvalues)))
        """
        zvalues = self.get_overlapping_inputstack_zvalues()
        if not zvalues:
            raise RenderModuleException(
                "No sections found for stack {} for specified zs".format(
                    self.args['input_stack']))

        self.logger.debug("Creating mipmaps...")

        mipmap_args = make_tilespecs_and_cmds(self.render,
                                              self.args['input_stack'],
                                              self.args['output_prefix'],
                                              zvalues,
                                              self.args['levels'],
                                              self.args['imgformat'],
                                              self.args['convert_to_8bit'],
                                              self.args['force_redo'],
                                              self.args['pool_size'],
                                              self.args['method'])

        self.output({"levels": self.args["levels"],
                     "output_prefix": self.args["output_prefix"]})


if __name__ == "__main__":
    mod = GenerateMipMaps()
    mod.run()
