.. _lens-correction:

Lens distortion correction
##########################

The lens distortion correction transforms can be computed using the
following modules

Step 1 - Compute lens distortion correction
============================================

Compute lens distortion correction transformation

(Assumes that the images for computation are loaded into a render stack.
)

::

   python -m asapmodules.mesh_lens_correction.do_mesh_lens_correction --input_json <input_parameter_json_file> --output_json <output_json_file>

An example input json file is provided in the do_mesh_lens_correcton.py
file

Step 2 - Apply lens correction
================================

Apply lens correction transformations to the input render stack (update
the raw tilespecs)

::

   python -m asapmodules.lens_correction.apply_lens_correction --input_json <input_parameter_json_file> --output_json <output_json_file>

An example input json file is provided in the apply_lens_correction.py
file
