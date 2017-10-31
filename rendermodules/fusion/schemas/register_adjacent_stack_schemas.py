import mm
from argschema.fields import Int, Str

from rendermodules.module.schemas import RenderParameters, DefaultSchema
from .shared import Transform

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

__all__ = ['RegisterSubvolumeParameters', 'RegisterSubvolumeOutputParameters']
