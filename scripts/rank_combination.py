#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import re
import json
import random
import argparse
from hashlib import md5
from utils.execution_util import ExecutionUtil

script_dir = sys.path[0]
project_dir = os.path.abspath(os.path.join(script_dir, ".."))
output_dir = os.path.join(project_dir, "output/stubs")

execution_util = ExecutionUtil()

def restoreStub(combination, dict_data):
    synopsis = dict_data["synopsis"]

    new_combination = ""
    for opt in combination.split(" "):
        if opt in dict_data["options"]:
            value = random.choice(dict_data["options"][opt])
            if value.startswith("="):
                new_combination += "%s=%s " % (opt, value)
            elif value.startswith("*"):
                new_combination += "%s%s " % (opt, value)
            else:
                new_combination += "%s %s " % (opt, value)
        else:
            new_combination += "%s " % (opt)
    
    if "SUB" in synopsis and "SUB" in dict_data["options"]:
        sub_command = random.choice(dict_data["options"]["SUB"])
        synopsis = synopsis.replace("SUB", sub_command)
    
    stub = synopsis.replace("OPTIONS", new_combination)
    return stub

def getDryRunCoverage(stub, program_dir, seed_dir, showmap_path):
    # Save stub into a temporary .argv file
    tmpfile_path = "/tmp/.dry-run-tmpfile-%s" % (md5(stub.encode("utf-8")).hexdigest())
    # Replace space with 0x00
    new_stub = ' '.join(stub.split()).replace(" ", "\x00") + "\x00"
    # Choose the first seed since it is more likely to be fuzzed in a limited time
    new_stub = new_stub.replace("@@", os.path.join(seed_dir, os.listdir(seed_dir)[0]))
    with open(tmpfile_path, "w") as f:
        f.write(new_stub)
    # Pass the temporary file to the program since it has been instrumented
    cmd = ("%s -e -o /dev/null -- %s/%s %s" % (showmap_path, program_dir, stub.split(" ")[0], tmpfile_path))
    # Execute
    output = execution_util.executeCommand(cmd)
    # Delete the temporary file
    os.remove(tmpfile_path)
    # Find the coverage data
    coverage = re.compile(r'Captured (\d+) tuples').findall(output)
    if len(coverage) == 0:
        print("[Error] Failed to get bitmap through cmd line: %s" % cmd)
        exit(1)
    return int(coverage[0])

def rankFromStubsFile(combination_list, dict_data, program_dir, showmap_path, seed_dir):

    coverage_dict = {}

    for combination in combination_list:
        stub = restoreStub(combination, dict_data)
        coverage = getDryRunCoverage(stub, program_dir, seed_dir, showmap_path)
        coverage_dict[stub] = coverage
    stubs_ranked_list = [item[0] for item in sorted(coverage_dict.items(), key=lambda x:x[1], reverse=True)]

    return stubs_ranked_list

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='''
    CarpetFuzz - an NLP-based fuzzing assitance tool for generating valid option combinations.
        rank_combination.py - rank valid option combinations based on their dry-run coverage.
    ''', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--combination', type=str, help='Path to combination file.', required=True)
    parser.add_argument('--dict', type=str, help='Path to option-value dictionary file.', required=True)
    parser.add_argument("--bindir", type=str, help='Path to instrumented ELF file.', required=True)
    parser.add_argument("--seeddir", type=str, help='Path to seed file', required=True)
    parser.add_argument("--showmap", type=str, help='Path to afl-showmap in CarpetFuzz-fuzzer (default=fuzzer/afl-showmap)', default=os.path.join(project_dir, "fuzzer/afl-showmap"))
    args = parser.parse_args()

    combination_file_path = args.combination
    dict_file_path = args.dict
    program_dir = args.bindir
    seed_dir = args.seeddir
    showmap_path = args.showmap

    program = combination_file_path.split("_")[1][:-4]
    
    with open(combination_file_path, "r") as f:
        combination_list = f.read().splitlines()

    with open(dict_file_path, "r") as f:
        dict_data = json.loads(f.read())

    if program not in dict_data:
        print("[x] Cannot find the program %s in dictionary." % (program))
        exit(1)

    stubs_ranked_list = rankFromStubsFile(combination_list, dict_data[program], program_dir, showmap_path, seed_dir)

    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    with open("%s/ranked_stubs_%s.txt" % (output_dir, program), "w") as f:
        f.write("%d\n%s"% (len(stubs_ranked_list), "\n".join(stubs_ranked_list)))

    print("[OK] Successfully generate the ranked stub file - %s/ranked_stubs_%s.txt" % (output_dir, program))
