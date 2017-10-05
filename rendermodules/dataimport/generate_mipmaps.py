import renderapi
import urllib
import urlparse
import os
from create_mipmaps import create_mipmaps
from functools import partial
from ..module.render_module import RenderModule, RenderParameters
import marshmallow as mm
from marshmallow import ValidationError, validates_schema


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
    "imgformat": "tiff",
    "levels": 6,
    "force_redo": "True",
    "zstart": 1015,
    "zend": 1015
}


def create_mipmap_from_tuple(mipmap_tuple, levels=[1, 2, 3],
                             convertTo8bit=True, force_redo=True):
    (filepath, downdir) = mipmap_tuple
    print mipmap_tuple
    return create_mipmaps(filepath, outputDirectory=downdir,
                          mipmaplevels=levels, convertTo8bit=convertTo8bit,
                          force_redo=force_redo)


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
        convertTo8bit=convert_to_8bit, force_redo=force_redo)

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


class GenerateMipMapsParameters(RenderParameters):
    input_stack = mm.fields.Str(
        required=True,
        description='stack for which the mipmaps are to be generated')
    output_dir = mm.fields.Str(
        required=True,
        description='directory to which the mipmaps will be stored')
    method = mm.fields.Str(
        required=True, default="block_reduce",
        validator=mm.validate.OneOf(["PIL", "block_reduce", "render"]),
        description=(
            "method to downsample mipmapLevels, "
            "can be 'block_reduce' for skimage based area downsampling, "
            "'PIL' for PIL Image (currently NEAREST) filtered resize, "
            "'render' for render-ws based rendering.  "
            "Currently only PIL is implemented, while others may fall "
            "back to this."))
    convert_to_8bit = mm.fields.Boolean(
        required=False, default=True,
        description='convert the data from 16 to 8 bit (default True)')
    pool_size = mm.fields.Int(
        required=False, default=20,
        description='number of cores to be used')
    imgformat = mm.fields.Str(
        required=False, default='tiff',
        description='image format for mipmaps (default tiff)')
    levels = mm.fields.Int(
        required=False, default=6,
        description='number of levels of mipmaps, default is 6')
    force_redo = mm.fields.Boolean(
        required=False, default=True,
        description='force re-generation of existing mipmaps')
    zstart = mm.fields.Int(
        required=False,
        description='start z-index in the stack')
    zend = mm.fields.Int(
        required=False,
        description='end z-index in the stack')
    z = mm.fields.Int(
        required=False,
        description='z-index in the stack')

    @validates_schema
    def validate_zvalues(self, data):
        if 'zstart' not in data.keys() or 'zend' not in data.keys():
            if 'zvalue' not in data.keys():
                raise ValidationError('Need a z value')
        if 'zvalue' not in data.keys():
            if 'zstart' not in data.keys() or 'zend' not in data.keys():
                raise ValidationError('Need a z range')

    @classmethod
    def validationOptions(cls, options):
        excluded_fields = {
            'PIL': [''],
            'block_reduce': [''],
            'render': ['']
        }
        exc_fields = excluded_fields[options['method']]
        return cls(exclude=exc_fields).dump(options)


class GenerateMipMaps(RenderModule):
    def __init__(self, schema_type=None, *args, **kwargs):
        if schema_type is None:
            schema_type = GenerateMipMapsParameters
        super(GenerateMipMaps, self).__init__(
            schema_type=schema_type, *args, **kwargs)

    def run(self):
        self.logger.debug('Mipmap generation module')

        # get the list of z indices
        zvalues = self.render.run(renderapi.stack.get_z_values_for_stack,
                                  self.args['input_stack'])

        try:
            self.args['zstart'] and self.args['zend']
            zvalues1 = range(self.args['zstart'], self.args['zend'] + 1)
            # extract only those z's that exist in the input stack
            zvalues = list(set(zvalues1).intersection(set(zvalues)))
        except NameError:
            try:
                self.args['z']
                if self.args['z'] in zvalues:
                    zvalues = [self.args['z']]
            except NameError:
                self.logger.error('No z value given for mipmap generation')

        if len(zvalues) == 0:
            self.logger.error('No sections found for stack {}'.format(
                self.args['input_stack']))

        self.logger.debug("Creating mipmaps...")

        if self.args['method'] in ['PIL', 'block_reduce']:
            mipmap_args = make_tilespecs_and_cmds(self.render,
                                                  self.args['input_stack'],
                                                  self.args['output_dir'],
                                                  zvalues,
                                                  self.args['levels'],
                                                  self.args['imgformat'],
                                                  self.args['convert_to_8bit'],
                                                  self.args['force_redo'],
                                                  self.args['pool_size'])

            # self.logger.debug("mipmaps generation checks...")
            # missing_files = verify_mipmap_generation(mipmap_args)
            # if not missing_files:
            #     self.logger.error("not all mipmaps have been generated")


if __name__ == "__main__":
    # mod = GenerateMipMaps(input_data=example)
    mod = GenerateMipMaps(schema_type=GenerateMipMapsParameters)
    mod.run()
