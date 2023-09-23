import itertools
import os
import subprocess
import tempfile
import yaml
import sys
import pkgutil


def parse_args():
    assert len(sys.argv) > 1, "Must provide a python module to run"
    module = sys.argv[1]
    args = sys.argv[2:]

    slurm_overrides = {}
    module_args = {}
    launch_overrides = {}
    current_arg = None

    while args:
        next = args.pop(0)
        if current_arg is None or next.startswith("--"):
            assert next.startswith("--"), (
                f"Invalid argument {next}, must start with '--'. "
                "Note that positional arguments are not supported."
            )
            current_arg = next[2:]
            if not current_arg.startswith(("slurm.", "launcher.")):
                module_args[current_arg] = []
        else:
            if current_arg.startswith("slurm."):
                key = current_arg[6:]
                slurm_overrides[key] = next
            elif current_arg.startswith("launcher."):
                key = current_arg[9:]
                launch_overrides[key] = next
            else:
                module_args[current_arg].append(next)

    for key, value in module_args.items():
        module_args[key] = " ".join(value)

    return module, module_args, slurm_overrides, launch_overrides


def main():
    module, args, slurm_overrides, launch_overrides = parse_args()

    data = pkgutil.get_data(__name__, "slurm.yaml")
    assert data is not None
    default_cfg = yaml.load(data, Loader=yaml.BaseLoader)
    slurm_params = default_cfg["slurm"] or {}
    module_args = default_cfg["script"] or {}
    launch_args = default_cfg["launcher"] or {}

    if os.path.exists("slurm.yaml"):
        with open("slurm.yaml", "r") as f:
            # We don't want to convert anything, leave all options as strings.
            # (In particular, we don't want to convert time specifications like 1:00:00
            # to seconds!)
            cfg = yaml.load(f, Loader=yaml.BaseLoader)
            slurm_params.update(cfg.get("slurm", {}))
            module_args.update(cfg.get("script", {}))
            launch_args.update(cfg.get("launcher", {}))

    slurm_params.update(slurm_overrides)
    module_args.update(args)
    launch_args.update(launch_overrides)

    for key, value in module_args.items():
        module_args[key] = value.split(",")

    slurm_script, n_runs = generate_slurm_script(
        module, module_args, slurm_params, launch_args
    )
    if launch_args["confirm"]:
        print(slurm_script)
        while True:
            response = input(f"Launch {n_runs} jobs? [Y/n] ")
            if response.lower() in ["y", "yes", ""]:
                break
            if response.lower() in ["n", "no"]:
                print("Aborting.")
                return
            print("Invalid response.")

    with tempfile.NamedTemporaryFile("w", suffix=".sh") as f:
        f.write(slurm_script)
        temp_filename = f.name
        result = subprocess.run(
            ["sbatch", temp_filename], check=True, capture_output=True
        )

    print(result.stdout)
    print(result.stderr)


def generate_slurm_script(module, args, slurm_params, launch_args):
    slurm_lines = [f"#!/bin/bash"]
    for key, value in slurm_params.items():
        slurm_lines.append(f"#SBATCH --{key}={value}")

    keys, values = zip(*args.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]

    if len(combinations) > 1:
        slurm_lines.append(f"#SBATCH --array=0-{(len(combinations) - 1)}\n")
        # Create the bash script
        slurm_lines.append("PARAMS_ARRAY=(")

        for combo in combinations:
            params = " ".join(f"--{k} {v}" for k, v in combo.items())
            slurm_lines.append(f'    "{params}"')

        slurm_lines.append(")\n")

        slurm_lines.append(launch_args["preamble"])
        slurm_lines.append(
            f"{launch_args['cmd_prefix']}{module}"
            + " ${PARAMS_ARRAY[$SLURM_ARRAY_TASK_ID]}"
        )
    else:
        slurm_lines.append("\n" + launch_args["preamble"])
        slurm_lines.append(
            f"{launch_args['cmd_prefix']}{module}"
            + " "
            + " ".join(f"--{k} {v}" for k, v in combinations[0].items())
        )

    return "\n".join(slurm_lines), len(combinations)


if __name__ == "__main__":
    main()
