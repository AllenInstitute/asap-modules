import marshmallow as mm
import argschema
from argschema.fields import Bool, Int, Str, Nested

from rendermodules.module.schemas import RenderParameters


# shared schemas
class Transform(argschema.schemas.DefaultSchema):
    className = Str(required=True)
    dataString = Str(required=True)
    type = Str(validator=mm.validate.OneOf(['leaf']), required=True)


class Stack(argschema.schemas.DefaultSchema):
    stack = Str(required=True)
    transform = Nested(Transform, required=False)
    children = Nested("self", many=True)
    fuse_stack = Bool(required=False, default=True, description=(
        "whether to include this stack's in the output of fusion"))


# register adjacent schemas
HOMOGRAPHY_TRANSFORM_CLASSES = [
    'TRANSLATION',
    'RIGID',
    'SIMILARITY'
    'AFFINE',
]


class RegisterSubvolumeParameters(RenderParameters):
    stack_a = Str(required=True, description="'parent' stack to remain fixed")
    stack_b = Str(required=True, description=(
        "'child' stack which moves to register to stack_a"))
    transform_type = Str(
        validator=mm.validate.OneOf(HOMOGRAPHY_TRANSFORM_CLASSES),
        required=False, default='RIGID', description=(
            "Homography model to fit.  Can be 'RIGID', 'AFFINE', "
            "'SIMILARITY', or 'TRANSLATION'"))
    pool_size = Int(required=False, default=1,
                    description='multiprocessing pool size')


class RegisterSubvolumeOutputParameters(argschema.schemas.DefaultSchema):
    stack_a = Str(required=True,
                  description=("'parent' stack remaining fixed for this "
                               "transform to register"))
    stack_b = Str(required=True,
                  description=("'child' stack which moves with this "
                               "transformation in order to register"))
    transform = Nested(
        Transform, required=False, default=None, allow_none=True,
        description="")


# fuse adjacent schemas
class FuseStacksParameters(RenderParameters):
    stacks = Nested(Stack, required=True,
                    description=('stack dictionary representing directed '
                                 'graph of stacks'))
    interpolate_transforms = Bool(
        required=False, default=True,
        description=('whether to use an InterpolatedTransform '
                     'class to interpolate the transforms of '
                     'overlapping sections'))
    output_stack = Str(required=True,
                       description=('stack to which fused representations '
                                    'should be added'))
    pool_size = Int(required=False, default=1,
                    description='multiprocessing pool size')
    create_nonoverlapping_zs = Bool(
        required=False, default=False,
        description=("upload uninterpolated sections for sections "
                     "without overlap"))
    close_stack = Bool(required=False, default=False, description=(
        "whether to set output stack to COMPLETE on finishing"))
    max_tilespecs_per_import_process = Int(
        required=False, default=None, allow_none=True, description=(
            "maximum number of tilespecs (written to tempfile) per "
            "import processing group.  Default unlimited."))


class FuseStacksOutput(argschema.schemas.DefaultSchema):
    stack = Str(required=True, description='resulting stack from fused stacks')


__all__ = [
    'Stack', 'Transform',
    'RegisterSubvolumeParameters', 'RegisterSubvolumeOutputParameters',
    'FuseStacksParameters', 'FuseStacksOutput'
    ]
