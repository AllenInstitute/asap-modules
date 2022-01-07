
# 2D Stitching

2D stitching of serial sections involves the following process

## 1. Create tilepairs for the serial section

```
python -m asapmodules.pointmatch.create_tilepairs --input_json <input_parameter_json_file> --output_json <output_json_file>
```

## 2. Generate point matches for the serial section

ASAP utilizes the SIFT point matching module in Render to compute the point matches. There also exists an opencv version of SIFT computation in ASAP.

### Point matching implementation from Render to be run on Spark cluster

This requires Spark to be installed in the setup.

```
python -m asapmodules.pointmatch.generate_point_matches_spark --input_json <input_parameter_json_file> --output_json <output_json_file>
```

### Point matching implementation from Render to be run on PBS cluster

```
python -m asapmodules.pointmatch.generate_point_matches_qsub --input_json <input_parameter_json_file> --output_json <output_json_file>
```

### Point matching implementation using opencv

```
python -m asapmodules.pointmatch.generate_point_matches_opencv --input_json <input_parameter_json_file> --output_json <output_json_file>
```

The point matches will be saved in a point match collection in the Render web service.

## 3. Solve for transformations

The bigfeta solver can be invoked from asap to solve for transformations using the following commmand

```
python -m asapmodules.solver.solve --input_json <input_parameter_json_file> --output_json <output_json_file>
```

## 4. Montage QC

The solver writes the transformations in the tilespecs associated with the serial section in the render stack. Once this is done, the QC module can be run to gather statistics about the quality of the stitching and also visualization plots of the stitched section.

```
python -m asapmodules.em_montage_qc.detect_montage_defects --input_json <input_parameter_json_file> --output_json <output_json_file>
```

The QC plots will be saved in the output directory specified in the input_parameter_json_file and the sections with issues will be found in the output_json_file.