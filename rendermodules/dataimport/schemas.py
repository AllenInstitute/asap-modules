import marshmallow as mm
from argschema.fields import InputDir, InputFile, Str, Int, Boolean, Float
from ..module.schemas import (StackTransitionParameters, InputStackParameters,
                              OutputStackParameters)
from marshmallow import ValidationError, post_load
from argschema.schemas import DefaultSchema



class GenerateMipMapsOutput(DefaultSchema):
    levels = Int(required=True)
    output_dir = Str(required=True)


class GenerateMipMapsParameters(InputStackParameters):
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


class AddMipMapsToStackParameters(StackTransitionParameters):
    mipmap_dir = InputDir(
        required=True,
        description='directory to which the mipmaps will be stored')
    levels = mm.fields.Int(
        required=False, default=6,
        description='number of levels of mipmaps, default is 6')
    imgformat = mm.fields.Str(
        required=False, default="tiff",
        description='mipmap image format, default is tiff')



class GenerateEMTileSpecsParameters(OutputStackParameters):
    metafile = InputFile(
        required=True,
        description="metadata file containing TEMCA acquisition data")
    image_directory = InputDir(
        required=False,
        description=("directory used in determining absolute paths to images. "
                     "Defaults to parent directory containing metafile "
                     "if omitted."))
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


class GenerateEMTileSpecsOutput(DefaultSchema):
    stack = Str(required=True,
                description="stack to which generated tiles were added")


class MakeMontageScapeSectionStackParameters(OutputStackParameters):
    montage_stack = Str(
        required=True,
        metadata={'description':'stack to make a downsample version of'})
    image_directory = InputDir(
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
    imgformat = Str(
        required=False,
        default='tif',
        missing='tif',
        metadata={'description':'image format of the montage scapes (default - tif)'})
    scale = Float(
        required=True,
        metadata={'description':'scale of montage scapes'})

    @post_load
    def validate_data(self, data):
        if data['set_new_z'] and data['new_z_start'] < 0:
            raise ValidationError('new Z start cannot be less than zero')
        elif not data['set_new_z']:
            data['new_z_start'] = min(data['zValues'])


class MakeMontageScapeSectionStackOutput(DefaultSchema):
    output_stack = Str(
        required=True,
        description='Name of the downsampled sections stack')
