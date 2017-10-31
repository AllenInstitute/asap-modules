EM Montage
==========

## [run_montage_job_for_section.py](run_montage_job_for_section.py)

input json:
```JSON
{
  "required": [
    "solver_options",
    "source_collection",
    "target_collection",
    "source_point_match_collection",
    "z_value",
    "solver_executable",
    "tmp_dir",
    "scratch"
  ],
  "type":"object",
  "properties": {
    "z_value": {
      "type": "integer",
      "format": "int32",
      "description": "Z value of section to be montaged"
    },
    "filter_point_matches": {
      "type": "integer",
      "default": 1,
      "description": "filter point matches before solving",
      "format": "int32"
    },
    "solver_executable": {
      "type": "string",
      "description": "matlab executable (with full path) for solving montages",
    }
  }
}
