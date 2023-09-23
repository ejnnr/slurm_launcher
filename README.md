# Slurm launcher
This is a very simple Python script for launching Slurm array jobs. It's currently
tailored to my use case and makes quite a few assumptions, for example:
- The slurm script consists of some header lines followed by a single main command
- The main command takes arguments using the argparse syntax, i.e. `--arg1 val1 --arg2 val2`
- Currently no support for positional arguments to the main command

That said, it should be easy to modify the script to suit your needs.

## Installation
Easiest is probably
```bash
pip install git+https://github.com/ejnnr/slurm_launcher.git
```
This will install the script as `slurm_launcher` in your path. (I personally alias
this to `slurm` but didn't make that the default to make clashes less likely.)

## Usage
Simple example:
```bash
slurm_launcher my_project.train --verbose --lr 0.01 --batch_size 32
```
This will generate the following Slurm script and submit it to the queue after asking
you for confirmation:
```bash
#!/bin/bash
#SBATCH --output=slurm/%A_%a.out

srun python -m my_project.train --verbose --lr 0.01 --batch_size 32
```

The main selling point is that you can automatically do grid searches by specifying
multiple comma-separated values for an argument:
```bash
slurm_launcher my_project.train --verbose --lr 0.01,0.001 --batch_size 32,64
```
will generate
```bash
#!/bin/bash
#SBATCH --output=slurm/%A_%a.out
#SBATCH --array=0-3

PARAMS_ARRAY=(
    "--verbose --lr 0.01 --batch_size 32"
    "--verbose --lr 0.01 --batch_size 64"
    "--verbose --lr 0.001 --batch_size 32"
    "--verbose --lr 0.001 --batch_size 64"
)
srun python -m my_project.train ${PARAMS_ARRAY[$SLURM_ARRAY_TASK_ID]}
```

You can set arbitrary `sbatch` arguments on the fly using `--slurm.<arg> <val>`:
```bash
slurm_launcher my_project.train --epochs 10 --slurm.mem 8gb
```

Finally, you can also define arguments by putting a file called `slurm.yaml` in the
current directory. See `src/slurm_launcher/slurm.yaml` for the default configuration
and possible options.

In particular, you may want to set a preamble:
```yaml
launcher:
  preamble: |
    cd /path/to/my/project
    source venv/bin/activate
```
This will be run before the main `srun` command.

You can also override how the main command should be launched via `launcher.cmd_prefix`.
The default is `"srun python -m "`, but you may want e.g. `"srun python3 "` instead,
or `"srun python -m my_project."`, or something other than Python.
