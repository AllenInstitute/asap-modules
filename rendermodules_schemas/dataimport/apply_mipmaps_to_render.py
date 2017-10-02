import marshmallow as mm
from argschema.fields import InputDir
from ..module.render_module import RenderParameters
from marshmallow import ValidationError, validates_schema

class AddMipMapsToStackParameters(RenderParameters):
    input_stack = mm.fields.Str(
        required=True,
        description='stack for which the mipmaps are to be generated')
    output_stack = mm.fields.Str(
        required=False, default=None, allow_none=True,
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

    @validates_schema
    def validate_zvalues(self, data):
        if 'zstart' not in data.keys() or 'zend' not in data.keys():
            if 'zvalue' not in data.keys():
                raise ValidationError('Need a z value')
        if 'zvalue' not in data.keys():
            if 'zstart' not in data.keys() or 'zend' not in data.keys():
                raise ValidationError('Need a z range')