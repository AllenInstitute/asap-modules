import warnings

import marshmallow as mm
from argschema.fields import InputDir, InputFile, Str, Int, Boolean, Float, List
from ..module.schemas import (StackTransitionParameters, InputStackParameters,
                              OutputStackParameters)
from marshmallow import ValidationError, post_load, pre_load
from argschema.schemas import DefaultSchema

import rendermodules.utilities.schema_utils


class GenerateMipMapsOutput(DefaultSchema):
    levels = Int(required=True)
    output_dir = Str(required=True)


class GenerateMipMapsParameters(InputStackParameters):
    output_dir = mm.fields.Str(
        required=False,
        description='directory to which the mipmaps will be stored')
    output_prefix = mm.fields.Str(
        required=True, description=("uri prefix for generated mipmaps"))
    method = mm.fields.Str(
        required=True, default="block_reduce",
        validator=mm.validate.OneOf(["PIL", "block_reduce"]),
        description=(
            "method to downsample mipmapLevels, "
            "'PIL' for PIL Image (currently NEAREST) filtered resize, "
            "can be 'block_reduce' for skimage based area downsampling"))
# "'render' for render-ws based rendering.  "
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
    PIL_filter = Str(required=False, default='NEAREST',
                     validator=mm.validate.OneOf([
                         'NEAREST', 'BOX', 'BILINEAR',
                         'HAMMING', 'BICUBIC', 'LANCZOS']),
                     description=('filter to be used in PIL resize'))
    block_func = Str(required=False, default='mean',
                     validator=mm.validate.OneOf(['mean', 'median']),
                     description=("function to represent blocks in "
                                  "area downsampling with block_reduce"))

    @classmethod
    def validationOptions(cls, options):
        excluded_fields = {
            'PIL': [''],
            'block_reduce': [''],
            'render': ['']
        }
        exc_fields = excluded_fields[options['method']]
        return cls(exclude=exc_fields).dump(options)

    # TODO test this
    @pre_load
    def directory_to_prefix(self, data):
        rendermodules.utilities.schema_utils.posix_to_uri(
            data, "output_dir", "output_prefix")


class AddMipMapsToStackOutput(DefaultSchema):
    output_stack = Str(required=True)
    missing_ts_zs = List(Int,
        required=False,
        default=[],
        missing=[],
        cli_as_single_argument=True,
        description="Z values for which apply mipmaps failed")


class AddMipMapsToStackParameters(StackTransitionParameters):
    mipmap_dir = InputDir(
        required=False,
        description='directory to which the mipmaps will be stored')
    mipmap_prefix = Str(
        required=True, description=(
            "uri prefix from which mipmap locations are built."))
    levels = mm.fields.Int(
        required=False, default=6,
        description='number of levels of mipmaps, default is 6')
    imgformat = mm.fields.Str(
        required=False, default="tiff",
        description='mipmap image format, default is tiff')

    # TODO test this
    @pre_load
    def mipmap_directory_to_prefix(self, data):
        rendermodules.utilities.schema_utils.posix_to_uri(
            data, "mipmap_dir", "mipmap_prefix")


class GenerateEMTileSpecsParameters(OutputStackParameters):
    metafile = InputFile(
        required=False,
        description="metadata file containing TEMCA acquisition data")
    metafile_uri = Str(
        required=True, description=(
            "uri of metadata containing TEMCA acquisition data"))
    # FIXME maskUrl and image_directory are not required -- posix_to_uri should support this
    maskUrl = InputFile(
        required=False,
        default=None,
        missing=None,
        description="absolute path to image mask to apply")
    maskUrl_uri = Str(
        required=False,
        default=None,
        missing=None,
        description=("uri of image mask to apply"))
    image_directory = InputDir(
        required=False,
        description=("directory used in determining absolute paths to images. "
                     "Defaults to parent directory containing metafile "
                     "if omitted."))
    image_prefix = Str(
        required=False, description=(
            "prefix used in determining full uris of images in metadata. "
            "Defaults to using the / delimited prefix to "
            "the metadata_uri if omitted"))
    maximum_intensity = Int(
        required=False, default=255,
        description=("intensity value to interpret as white"))
    minimum_intensity = Int(
        required=False, default=0,
        description=("intensity value to interpret as black"))
    sectionId = Str(
        required=False,
        description=("sectionId to apply to tiles during ingest.  "
                     "If unspecified will default to a string "
                     "representation of the float value of z_index."))

    @pre_load
    def metafile_to_uri(self, data):
        rendermodules.utilities.schema_utils.posix_to_uri(
            data, "metafile", "metafile_uri")

    # FIXME not required -- does this work
    @pre_load
    def maskUrl_to_uri(self, data):
        rendermodules.utilities.schema_utils.posix_to_uri(
            data, "storage_directory", "storage_prefix")

    @pre_load
    def image_directory_to_prefix(self, data):
        rendermodules.utilities.schema_utils.posix_to_uri(
            data, "image_directory", "image_prefix")


class GenerateEMTileSpecsOutput(DefaultSchema):
    stack = Str(required=True,
                description="stack to which generated tiles were added")


class MakeMontageScapeSectionStackParameters(OutputStackParameters):
    montage_stack = Str(
        required=True,
        metadata={'description':'stack to make a downsample version of'})
    image_directory = Str(
        required=True,
        metadata={'description':'directory that stores the montage scapes'})
    set_new_z = Boolean(
        required=False,
        default=False,
        missing=False,
        metadata={'description':'set to assign new z values starting from 0 (default - False)'})
    new_z_start = Int(
        required=False,
        default=0,
        missing=0,
        metadata={'description':'new starting z index'})
    remap_section_ids = Boolean(
        required=False,
        default=False,
        missing=False,
        metadata={'description':'change section ids to new z values. default = False'})
    imgformat = Str(
        required=False,
        default='tif',
        missing='tif',
        metadata={'description':'image format of the montage scapes (default - tif)'})
    scale = Float(
        required=True,
        metadata={'description':'scale of montage scapes'})
    apply_scale = Boolean(
        required=False,
        default=False,
        missing=False,
        metadata={'description':'Do you want to scale the downsample to the size of section? Default = False'})
    doFilter = Boolean(required=False, default=True, description=(
        "whether to apply default filtering when generating "
        "missing downsamples"))
    level = Int(required=False, default=1, description=(
        "integer mipMapLevel used to generate missing downsamples"))
    fillWithNoise = Boolean(required=False, default=False, description=(
        "Whether to fill the background pixels with noise when "
        "generating missing downsamples"))
    memGB_materialize = Str(required=False, default='12G', description=(
        "Java heap size in GB for materialization"))
    pool_size_materialize = Int(required=False, default=1, description=(
        "number of processes to generate missing downsamples"))
    filterListName = Str(required=False, description=(
        "Apply specified filter list to all renderings"))

    @post_load
    def validate_data(self, data):
        if data['set_new_z'] and data['new_z_start'] < 0:
            raise ValidationError('new Z start cannot be less than zero')
        elif not data['set_new_z']:
            data['new_z_start'] = min(data['zValues'])
        # FIXME will be able to remove with render-python tweak
        if data.get('filterListName') is not None:
            warnings.warn(
                "filterListName not implemented -- will use default behavior",
                UserWarning)


class MakeMontageScapeSectionStackOutput(DefaultSchema):
    output_stack = Str(
        required=True,
        description='Name of the downsampled sections stack')
