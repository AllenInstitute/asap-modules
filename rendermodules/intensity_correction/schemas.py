from argschema.fields import InputFile, InputDir, Str, Float, Int, OutputDir, Bool
from ..module.schemas import RenderParameters

class MakeMedianParams(RenderParameters):
    input_stack = Str(required=True,
                      description='Input stack to derive median from')
    file_prefix = Str(required=False, default="Median",
                      description='File prefix for median image file that is saved')
    output_directory = OutputDir(required=True,
                                 description='Output Directory for saving median image')
    output_stack = Str(required=True,
                       description='Output stack to save correction into')
    minZ = Int(required=True,
               description='z value for section')
    maxZ = Int(required=True,
               description='z value for section')
    pool_size = Int(required=False, default=20,
                    description='size of pool for parallel processing (default=20)')
    close_stack = Bool(required=False, default=False,
                       description="whether to close stack or not")


class MultIntensityCorrParams(RenderParameters):
    input_stack = Str(required=True,
                      description="Input stack")
    output_stack = Str(required=True,
                       description='Output stack')
    correction_stack = Str(required=True,
                           description='Correction stack (usually median stack for AT data)')
    output_directory = OutputDir(required=True,
                                 description='Directory for storing Images')
    z_index = Int(required=True,
                  description='z value for section')
    pool_size = Int(required=False, default=20,
                    description='size of pool for parallel processing (default=20)')
    cycle_number = Int(required=False, default=2,
                       description="what cycleNumber to upload for output_stack on render")
    cycle_step_number = Int(required=False, default=1,
                            description="what cycleStepNumber to upload for output_stack on render")
    close_stack = Bool(required=False, default=False,
                       description="whether to close stack or not")
    clip = Bool(required=False, default=True,
                       description="whether to clip values")
    scale_factor = Float(required=False,default=1.0,
		       description="scaling value")
    # move_input = Bool(required=False, default=False,
    #                   description="whether to move input tiles to new location")
    # move_input_regex_find = Str(required=False,
    #                             default="",
    #                             description="regex string to find in input filenames")
    # move_input_regex_replace = Str(required=False,
    #                                default="",
    #                                description="regex string to replace in input filenames")
