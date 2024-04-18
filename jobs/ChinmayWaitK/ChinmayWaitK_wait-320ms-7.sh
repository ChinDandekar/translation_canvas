#!/usr/bin/env bash


#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=128GB
#SBATCH --gpus=1
##SBATCH --constraint=xeon-4116 
#SBATCH --partition=aries
#SBATCH --time=5-2:34:56
#SBATCH --account=chinmay
#SBATCH --mail-type=ALL
#SBATCH --mail-user=cdandekar@ucsb.edu
#SBATCH --output=/mnt/taurus/data1/chinmay/sllamaEval/slurm_jobs/instructscore_320ms_3_out-%j.txt
#SBATCH --error=/mnt/taurus/data1/chinmay/sllamaEval/slurm_jobs/instructscore_320ms_3_err-%j.txt

export CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7

python eval.py --file_name "/mnt/taurus/data1/chinmay/instructscore_visualizer/jobs/ChinmayWaitK/wait-320ms-7.json"