import marshmallow as mm
from argschema.fields import InputDir, InputFile, Str, Int, Boolean, InputDir
from ..module.schemas import RenderParameters
from marshmallow import ValidationError, post_load
from argschema.schemas import DefaultSchema


class GenerateMipMapsOutput(DefaultSchema):
    levels = Int(required=True)
    output_dir = Str(required=True)


class GenerateMipMapsParameters(RenderParameters):
    input_stack = mm.fields.Str(
        required=True,
        description='stack for which the mipmaps are to be generated')
    output_dir = mm.fields.Str(
        required=True,
        description='directory to which the mipmaps will be stored')
    method = mm.fields.Str(
        required=True, default="block_reduce",
        validator=mm.validate.OneOf(["PIL"]),
        description=(
            "method to downsample mipmapLevels, "
            "'PIL' for PIL Image (currently NEAREST) filtered resize, "
            "Currently only PIL is implemented"))
        #"'render' for render-ws based rendering.  "
        #"can be 'block_reduce' for skimage based area downsampling, "
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

    @post_load
    def validate_zvalues(self, data):
        if ('zstart' not in data.keys()) or ('zend' not in data.keys()):
            if 'z' not in data.keys():
                raise ValidationError('Need a z value')

    @classmethod
    def validationOptions(cls, options):
        excluded_fields = {
            'PIL': [''],
            'block_reduce': [''],
            'render': ['']
        }
        exc_fields = excluded_fields[options['method']]
        return cls(exclude=exc_fields).dump(options)


class AddMipMapsToStackOutput(DefaultSchema):
    output_stack = Str(required=True)


class AddMipMapsToStackParameters(RenderParameters):
    input_stack = mm.fields.Str(
        required=True,
        description='stack for which the mipmaps are to be generated')
    output_stack = mm.fields.Str(
        required=True, 
        description='the output stack name. Leave to overwrite input stack')
    mipmap_dir = InputDir(
        required=True,
        description='directory to which the mipmaps will be stored')
    levels = mm.fields.Int(
        required=False, default=6,
        description='number of levels of mipmaps, default is 6')
    zstart = mm.fields.Int(
        required=False,
        description='start z-index in the stack')
    zend = mm.fields.Int(
        required=False,
        description='end z-index in the stack')
    z = mm.fields.Int(
        required=False,
        description='z-index of section in the stack')
    imgformat = mm.fields.Str(
        required=False, default="tiff",
        description='mipmap image format, default is tiff')
    pool_size = mm.fields.Int(
        required=False, default=20,
        description='number of cores to be used')
    close_stack = mm.fields.Boolean(
        required=False, default=False,
        description=("whether to set output stack state to "
                     "'COMPLETE' upon completion"))

    @post_load
    def validate_zvalues(self, data):
        if ('zstart' not in data.keys()) or ('zend' not in data.keys()):
            if 'z' not in data.keys():
                raise ValidationError('Need a z value or a z range')



class GenerateEMTileSpecsParameters(RenderParameters):
    metafile = InputFile(
        required=True,
        description="metadata file containing TEMCA acquisition data")
    stack = Str(required=True,
                description="stack to which tiles should be added")
    image_directory = InputDir(
        required=False,
        description=("directory used in determining absolute paths to images. "
                     "Defaults to parent directory containing metafile "
                     "if omitted."))
    pool_size = Int(
        required=False, default=1,
        description="processes to spawn for parallelization")
    close_stack = Boolean(
        required=False, default=False,
        description=("whether to set stack to 'COMPLETE' after "
                     "performing operation"))
    overwrite_zlayer = Boolean(
        required=False, default=False,
        description=("whether to remove the existing layer from the "
                     "target stack before uploading."))
    maximum_intensity = Int(
        required=False, default=255,
        description=("intensity value to interpret as white"))
    minimum_intensity = Int(
        required=False, default=0,
        description=("intensity value to interpret as black"))
    z_index = Int(
        required=True,
        description="z value to which tilespecs from ROI will be added")
    sectionId = Str(
        required=False,
        description=("sectionId to apply to tiles during ingest.  "
                     "If unspecified will default to a string "
                     "representation of the float value of z_index."))


class GenerateEMTileSpecsOutput(DefaultSchema):
    stack = Str(required=True,
                description="stack to which generated tiles were added")
