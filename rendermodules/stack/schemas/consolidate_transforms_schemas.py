from rendermodules.module.schemas import RenderParameters
from argschema.fields import Str, Int, Slice, Float
from argschema.schemas import DefaultSchema

class ConsolidateTransformsParameters(RenderParameters):
    stack = Str(required=True,
                description='stack to consolidate')
    postfix = Str(required=False, default="_CONS",
                  description='postfix to add to stack name on saving if no output defined (default _CONS)')
    transforms_slice = Slice(required=True,
                             description="a string representing a slice describing \
                             the set of transforms to be consolidated (i.e. 1:)")
    output_stack = Str(required=False,
                       description='name of output stack (default to adding postfix to input)')
    pool_size = Int(required=False, default=10,
                    description='name of output stack (default to adding postfix to input)')
    minZ = Float(required=False,
                 description="""minimum z to consolidate in read in from stack and write to output_stack\
                 default to minimum z in stack""")
    maxZ = Float(required=False,
                 description="""minimaximummum z to consolidate in read in from stack and write to output_stack\
                 default to maximum z in stack""")


class ConsolidateTransformsOutputParameters(DefaultSchema):
    output_stack = Str(required=True, description="name of output stack")
    numZ = Int(required=True, description="Number of z values processed")
