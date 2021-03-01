#!/usr/bin/env python3

import os
import subprocess
import sys

if 'PASH_TOP' in os.environ:
    PASH_TOP = os.environ['PASH_TOP']
else:
    GIT_TOP_CMD = [ 'git', 'rev-parse', '--show-toplevel', '--show-superproject-working-tree']
    PASH_TOP = subprocess.run(GIT_TOP_CMD, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True).stdout.rstrip()

sys.path.append(os.path.join(PASH_TOP, "compiler"))

import matplotlib.pyplot as plt
import gather_results

experiments = ["minimal_grep",
               "minimal_sort",
               "topn",
               "wf",
               "spell",
               "diff",
               "bigrams",
               "set-diff",
               "double_sort",
               "shortest_scripts"]
scaleup_numbers = [2, 16]

## TODO: Abstract this in an argument
standard_disk_results_dir = os.path.join("results", "standard_disk_instance", "eurosys_small")
fast_disk_results_dir = os.path.join("results", "fast_disk_instance", "eurosys_small")


def plot(all_results, experiments, scaleup_numbers, pash_config='split'):
    fig = plt.figure()
    columns = 5
    rows = (len(experiments) // columns) + 1
    # hspace=0.05
    hspace=0.15
    gs = fig.add_gridspec(rows, columns, hspace=hspace)


    for i, experiment in enumerate(experiments):
        ax = fig.add_subplot(gs[i])
        for config_name, config_results in all_results.items():
            speedups = config_results[experiment][pash_config]
            seq_time_ms = config_results[experiment]['sequential']
            seq_time = seq_time_ms / 1000.0
            ys = [seq_time / speedup for speedup in speedups]
            ax.plot(scaleup_numbers, ys, label=config_name+"-pash")
            seq_ys = [seq_time for _ in scaleup_numbers]
            ax.plot(scaleup_numbers, seq_ys, label=config_name + "-bash")
        
        text = "{}".format(gather_results.pretty_names[experiment])
        # text_relative_y = .91
        text_relative_y = 1.05
        ax.text(.5, text_relative_y, text,
                horizontalalignment='center',
                transform=ax.transAxes)
        ax.set_xticks(scaleup_numbers)

    plt.legend(loc='lower right', fontsize=16)
    # plt.title(pretty_names[experiment])

    fig.set_size_inches(columns * 6, rows * 5)
    plt.tight_layout()
    plt.savefig(os.path.join('plots', "one_liners.pdf"),bbox_inches='tight')


standard_disk_results = {}
fast_disk_results = {}

for experiment in experiments:
    standard_disk_speedup_results, _, standard_sequential_time = gather_results.collect_scaleup_line_speedups(experiment, scaleup_numbers, standard_disk_results_dir)
    standard_disk_results[experiment] = standard_disk_speedup_results
    standard_disk_results[experiment]['sequential'] = standard_sequential_time

    fast_disk_speedup_results, _, fast_sequential_time = gather_results.collect_scaleup_line_speedups(experiment, scaleup_numbers, fast_disk_results_dir)
    fast_disk_results[experiment] = fast_disk_speedup_results
    fast_disk_results[experiment]['sequential'] = fast_sequential_time

all_results = {
    "standard-disk": standard_disk_results,
    "fast-disk": fast_disk_results,
}
if not os.path.exists('plots'):
    os.makedirs('plots')

plot(all_results, experiments, scaleup_numbers)
