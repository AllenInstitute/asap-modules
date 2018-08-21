from rendermodules.module.schemas import (RenderParameters,
                                          StackTransitionParameters)
from argschema.fields import (Str, Int, Slice, Float, Boolean,
                              List, Nested, InputDir)
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
    overwrite_zlayer = Boolean(
        required=False, default=False,
        description=("whether to remove the existing layer from the "
                     "target stack before uploading."))



class ConsolidateTransformsOutputParameters(DefaultSchema):
    output_stack = Str(required=True, description="name of output stack")
    numZ = Int(required=True, description="Number of z values processed")


class MipMapDirectories(DefaultSchema):
    level = Int(required=True, description=(
        "mipMapLevel for which parent directory will be changed"))
    directory = InputDir(required=True, description=(
        "directory where relocated mipmaps are found."))


class RedirectMipMapsParameters(StackTransitionParameters):
    new_mipmap_directories = Nested(
        MipMapDirectories, required=True, many=True)


class RedirectMipMapsOutput(DefaultSchema):
    zValues = List(Int, required=True)
    output_stack = Str(required=True)


class RemapZsParameters(StackTransitionParameters):
    remap_sectionId = Boolean(required=False)
    new_zValues = List(Int, required=True)


class RemapZsOutput(DefaultSchema):
    zValues = List(Int, required=True)
    output_stack = Str(required=True)

class SwapZsParameters(RenderParameters):
    source_stack = Str(required=True,
                        description="List of stacks from which sections needs to be swapped")
    target_stack = Str(required=True,
                        description="List of stacks to which sections needs to be swapped")
    zValues = List(Int, 
                   required=True,
                   description="List of z values to be swapped")
    delete_source_stacks = Boolean(
        required=False,
        default=False,
        missing=False,
        description="Do you want to delete the temp source stacks after swapping to a new one - Default=False")
    
class SwapZsOutput(DefaultSchema):
    zValues = List(Int, required=True)
    output_stack = Str(required=True,
                        description="List of newly swapped stacks")