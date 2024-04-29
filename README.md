# Introduction

A Python Flask based visualizer for InstructScore. This webapp (currently) accepts the output of Simuleval 
evaluation, but can be made to work with any prediction-reference pair. 

Given a pair, it starts a slurm job to run [InstructScore](https://arxiv.org/abs/2305.14282) evaluation on the pair.
Once the job is done running, the webapp renders the prediction-reference pair, highlighting words or phrases with errors.


# To use

```
git clone https://github.com/ChinDandekar/instructscore_visualizer
cd instructscore_visualizer
conda env create -f environment.yml
conda activate instructscore_visualizer_env
flask --app instructscore_visualizer run --debug
```


