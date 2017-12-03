import renderapi
import urllib
import urlparse
from rendermodules.dataimport.create_mipmaps import create_mipmaps
from functools import partial
from ..module.render_module import RenderModule, RenderModuleException
from rendermodules.dataimport.schemas import GenerateMipMapsParameters

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
                             force_redo=True):
    (filepath, downdir) = mipmap_tuple
    return create_mipmaps(filepath, outputDirectory=downdir,
                          mipmaplevels=levels, convertTo8bit=convertTo8bit,
                          outputformat=imgformat, force_redo=force_redo)


def get_filepath_from_tilespec(ts):
    mml = ts.ip.get(0)

    old_url = mml['imageUrl']
    filepath_in = urllib.unquote(urlparse.urlparse(
        str(old_url)).path)
    return filepath_in


def make_tilespecs_and_cmds(render, inputStack, output_dir, zvalues, levels,
                            imgformat, convert_to_8bit, force_redo, pool_size):
    mipmap_args = []

    for z in zvalues:
        tilespecs = render.run(renderapi.tilespec.get_tile_specs_from_z,
                               inputStack, z)

        for ts in tilespecs:
            filepath_in = get_filepath_from_tilespec(ts)
            mipmap_args.append((filepath_in, output_dir))

    mypartial = partial(
        create_mipmap_from_tuple, levels=range(1, levels + 1),
        convertTo8bit=convert_to_8bit, force_redo=force_redo, imgformat=imgformat)

    with renderapi.client.WithPool(pool_size) as pool:
        results = pool.map(mypartial, mipmap_args)

    return mipmap_args


'''
def verify_mipmap_generation(mipmap_args):
    missing_files = []
    for (m1,m2) in mipmap_args:
        if not os.path.exists(m2):
            missing_files.append((m1,m2))

    return missing_files
'''


class GenerateMipMaps(RenderModule):
    default_schema = GenerateMipMapsParameters
    default_output_schema = GenerateMipMapsOutput

    def run(self):
        self.logger.debug('Mipmap generation module')

        # get the list of z indices
        zvalues = self.render.run(renderapi.stack.get_z_values_for_stack,
                                  self.args['input_stack'])

        try:
            zvalues1 = range(self.args['zstart'], self.args['zend'] + 1)
            # extract only those z's that exist in the input stack
            zvalues = list(set(zvalues1).intersection(set(zvalues)))
        except NameError:
            try:
                if self.args['z'] in zvalues:
                    zvalues = [self.args['z']]
            except NameError:
                self.logger.error('No z value given for mipmap generation')

        if len(zvalues) == 0:
            self.logger.error('No sections found for stack {}'.format(
                self.args['input_stack']))

        self.logger.debug("Creating mipmaps...")

        if self.args['method'] in ['PIL']:
            mipmap_args = make_tilespecs_and_cmds(self.render,
                                                  self.args['input_stack'],
                                                  self.args['output_dir'],
                                                  zvalues,
                                                  self.args['levels'],
                                                  self.args['imgformat'],
                                                  self.args['convert_to_8bit'],
                                                  self.args['force_redo'],
                                                  self.args['pool_size'])

        else:
            raise RenderModuleException(
                "method {} not supported".format(self.args['method']))
            # self.logger.debug("mipmaps generation checks...")
            # missing_files = verify_mipmap_generation(mipmap_args)
            # if not missing_files:
            #     self.logger.error("not all mipmaps have been generated")
        self.output({"levels": self.args["levels"],
                     "output_dir": self.args["output_dir"]})


if __name__ == "__main__":
    # mod = GenerateMipMaps(input_data=example)
    mod = GenerateMipMaps(schema_type=GenerateMipMapsParameters)
    mod.run()
