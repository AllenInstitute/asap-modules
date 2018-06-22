#!/bin/bash

#PBS -q emconnectome
#PBS -l nodes=1:ppn=32 -n
#PBS -l walltime=03:00:00
#PBS -N em_lens_correction
#PBS -r n
#PBS -j oe
#PBS -o /allen/programs/celltypes/workgroups/em-connectomics/danielk/em_lens_correction/log/pbs.log

master_json=/allen/programs/celltypes/workgroups/em-connectomics/danielk/em_lens_correction/master.json
z_set=100
sectionid=tmp_sectionId
stack=raw_lens_stack
aligned_stack=aligned_corrected_lens_stack

dvar=$(date "+%Y%m%d%H%M%S")
tspecout=/allen/programs/celltypes/workgroups/em-connectomics/danielk/em_lens_correction/lens_outputs/tspec_out_${dvar}.json
tpairout=/allen/programs/celltypes/workgroups/em-connectomics/danielk/em_lens_correction/lens_outputs/tpair_out_${dvar}.json
lpmout=/allen/programs/celltypes/workgroups/em-connectomics/danielk/em_lens_correction/lens_outputs/lpm_out_${dvar}.json
meshout=/allen/programs/celltypes/workgroups/em-connectomics/danielk/em_lens_correction/lens_outputs/mesh_out_${dvar}.json
qcout=/allen/programs/celltypes/workgroups/em-connectomics/danielk/em_lens_correction/qc/qc_out_${dvar}.json

#set java variables for render-modules
export RENDER_CLIENT_JAR=/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/dev/render-ws-java-client-standalone.jar
if [[ -v PBS_JOBID ]];
then
    export RENDER_JAVA_HOME=/shared/utils.x86_64/jdk_8u91
    export JAVA_HOME=/shared/utils.x86_64/jdk_8u91
    module load anaconda/4.3.1
    module load java
else
    export RENDER_JAVA_HOME=/usr
    export JAVA_HOME=/usr
fi

source activate /allen/programs/celltypes/workgroups/em-connectomics/danielk/conda/render-modules-lens

#make a new stack section with the lc tiles
python -m rendermodules.dataimport.generate_EM_tilespecs_from_metafile --input_json ${master_json} --output_json ${tspecout} --z ${z_set} --sectionId ${sectionid} --output_stack ${stack}
#create tilepairs
python -m rendermodules.pointmatch.create_tilepairs --input_json ${master_json} --z ${z_set} --zNeighborDistance 0 --xyNeighborFactor 0.1 --excludeCornerNeighbors False --excludeSameLayerNeighbors False --excludeCompletelyObscuredTiles True --output_json ${tpairout} --stack ${stack}

#find pointmatches
python -m rendermodules.mesh_lens_correction.LensPointMatches --input_json ${master_json} --tilepair_output ${tpairout} --output_json ${lpmout} --stack ${stack}

#find the lens correction, write out to new stack
python -m rendernodules.mesh_lens_correction.MeshAndSolveTransform --input_json ${master_json} --sectionId ${sectionid} --output_json ${meshout} --stack ${stack} --aligned_stack ${aligned_stack}

#run montage qc on the new stack
python -m rendermodules.em_montage_qc.detect_montage_defects --input_json ${master_json} --prestitched_stack ${stack} --poststitched_stack ${aligned_stack} --minZ ${z_set} --maxZ ${z_set} --output_json ${qcout}

