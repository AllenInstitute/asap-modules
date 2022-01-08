.. _mipmaps:


Generate MIPmaps
################

MIPmaps are essential for stitching and alignment and is used to
generate point matches, used for visualization, etc.

MIPmaps can be generated for a dataset loaded into a render stack.

Step 1 - Generate MIPmaps
=========================

::

   python -m asapmodules.dataimport.create_mipmaps --input_json <input_parameter_json_file> --output_json <output_json_file>

Step 2 - Apply MIPmaps to Render stack
=======================================

::

   python -m asapmodules.dataimport.apply_mipmaps_to_render --input_json <input_parameter_json_file> --output_json <output_json_file>

Example input parameter json files are included in the module’s script
files.
