import argschema
from argschema.fields import Nested, Bool, Int, Str

from rendermodules.module.schemas import RenderParameters
from .shared_schemas import Stack


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


class FuseStacksOutput(argschema.schemas.Schema):
    # TODO define output schema
    pass

__all__ = ['FuseStacksParameters', 'FuseStacksOutput']
