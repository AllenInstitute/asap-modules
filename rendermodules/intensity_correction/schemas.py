from argschema.fields import Str, Float, Int, Bool
from ..module.schemas import StackTransitionParameters


class MakeMedianParams(StackTransitionParameters):
    file_prefix = Str(required=False, default="Median",
                      description='File prefix for median image file that is saved')
    output_directory = Str(required=True,
                                 description='Output Directory for saving median image')
    num_images = Int (required=False,default=-1,
                             description="Number of images to randomly subsample to generate median")

class MultIntensityCorrParams(StackTransitionParameters):
    correction_stack = Str(required=True,
                           description='Correction stack (usually median stack for AT data)')
    output_directory = Str(required=True,
                                 description='Directory for storing Images')
    # TODO add create_stack metadata
    cycle_number = Int(required=False, default=2,
                    description="what cycleNumber to upload for output_stack on render")
    cycle_step_number = Int(required=False, default=1,
                         description="what cycleStepNumber to upload for output_stack on render")
    clip = Bool(required=False, default=True,
                       description="whether to clip values")
    scale_factor = Float(required=False,default=1.0,
		       description="scaling value")
    clip_min = Int(required=False, default=0,
                  description='Min Clip value')
    clip_max = Int(required=False, default=65535,
                  description='Max Clip value')

    # move_input = Bool(required=False, default=False,
    #                   description="whether to move input tiles to new location")
    # move_input_regex_find = Str(required=False,
    #                             default="",
    #                             description="regex string to find in input filenames")
    # move_input_regex_replace = Str(required=False,
    #                                default="",
    #                                description="regex string to replace in input filenames")
