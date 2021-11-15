#!/bin/bash

#PBS -q emconnectome
#PBS -l nodes=1:ppn=32 -n
#PBS -l walltime=03:00:00
#PBS -N em_lens_correction
#PBS -r n
#PBS -j oe
#PBS -o /allen/programs/celltypes/workgroups/em-connectomics/danielk/em_lens_correction/log/pbs.log

metafile=/allen/programs/celltypes/production/wijem/long_term/reference_2018_02_21_01_56_45_00_00/_metadata_20180220175645_247488_8R_tape070A_05_20180220175645_reference_0_.json
sectionid=$(python -c "a='${metafile}';asp=a.split('/');sref=[s for s in asp if s.startswith('reference_')];print(sref[0])")
z_set=1

master_json=/allen/programs/celltypes/workgroups/em-connectomics/danielk/em_lens_correction/master.json
stack=raw_lens_stack
aligned_stack=aligned_corrected_lens_stack

basedir=/allen/programs/celltypes/workgroups/em-connectomics/danielk/em_lens_correction/
tspecout=${basedir}/lens_outputs/tspec_out_${sectionid}.json
tpairout=${basedir}/lens_outputs/tpair_out_${sectionid}.json
lpmout=${basedir}/lens_outputs/lpm_out_${sectionid}.json
meshout=${basedir}/mesh_out_${sectionid}.json
qcout=${basedir}/qc/qc_out_${sectionid}.json

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
python -m rendermodules.dataimport.generate_EM_tilespecs_from_metafile --input_json ${master_json} --output_json ${tspecout} --z ${z_set} --sectionId ${sectionid} --output_stack ${stack} --metafile ${metafile}
#create tilepairs
python -m rendermodules.pointmatch.create_tilepairs --input_json ${master_json} --z ${z_set} --zNeighborDistance 0 --xyNeighborFactor 0.1 --excludeCornerNeighbors False --excludeSameLayerNeighbors False --excludeCompletelyObscuredTiles True --output_json ${tpairout} --stack ${stack}

#find pointmatches
python -m rendermodules.mesh_lens_correction.LensPointMatches --input_json ${master_json} --tilepair_output ${tpairout} --output_json ${lpmout} --stack ${stack}

#find the lens correction, write out to new stack
python -m rendermodules.mesh_lens_correction.MeshAndSolveTransform --input_json ${master_json} --sectionId ${sectionid} --output_json ${meshout} --stack ${stack} --aligned_stack ${aligned_stack}

#run montage qc on the new stack
python -m rendermodules.em_montage_qc.detect_montage_defects --input_json ${master_json} --prestitched_stack ${stack} --poststitched_stack ${aligned_stack} --minZ ${z_set} --maxZ ${z_set} --output_json ${qcout}

