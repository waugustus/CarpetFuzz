import argparse
import os
import re
import sys
import json
import random
from hashlib import md5
from utils.execution_util import ExecutionUtil

script_dir = sys.path[0]
project_dir = os.path.abspath(os.path.join(script_dir, ".."))
output_dir = "%s/output/relation" % project_dir

execution_util = ExecutionUtil()

def restoreStub(option, dict_data):
    synopsis = dict_data["synopsis"]

    new_combination = ""

    if option in dict_data["options"]:
        value = random.choice(dict_data["options"][option])
        if value.startswith("="):
            new_combination += "%s=%s " % (option, value)
        elif value.startswith("*"):
            new_combination += "%s%s " % (option, value)
        else:
            new_combination += "%s %s " % (option, value)
    else:
        new_combination += "%s " % (option)
    
    if "SUB" in synopsis and "SUB" in dict_data["options"]:
        sub_command = random.choice(dict_data["options"]["SUB"])
        stub = synopsis.replace("SUB", sub_command)
    
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

def rankFromStubsFile(option_list, dict_data, program_dir, showmap_path, seed_dir):

    coverage_dict = {}

    for option in option_list:
        stub = restoreStub(option, dict_data)
        coverage = getDryRunCoverage(stub, program_dir, seed_dir, showmap_path)
        coverage_dict[option] = coverage
    stubs_ranked_list = [item[0] for item in sorted(coverage_dict.items(), key=lambda x:x[1], reverse=True)]

    return stubs_ranked_list

def restrictOptions(relation_data, target_number, dict_data, program_dir, showmap_path, seed_dir):

    option_list = relation_data['options']['total_options']
    if len(option_list) < target_number:
        print("[x] Error: No enough options to be restricted.")
        exit(1)

    option_ranked_list = rankFromStubsFile(option_list, dict_data, program_dir, showmap_path, seed_dir)
    restricted_option_list = option_ranked_list[:target_number]

    new_relation_data = {"options": {}}

    new_total_options = []
    new_conflict_options = []
    new_dependent_options = {}
    for opt in restricted_option_list:
        if opt in relation_data["options"]["total_options"]:
            new_total_options.append(opt)
        for conflict_pair in relation_data["options"]["conflict_options"]:
            if opt in conflict_pair:
                new_conflict_options.append(conflict_pair)
        for key in relation_data["options"]["dependent_options"]:
            value = relation_data["options"]["dependent_options"][key]
            if opt in [key, value] + value.split("&&") + value.split("||"):
                new_dependent_options[key] = relation_data["options"]["dependent_options"][key]
    
    new_relation_data = {"options": {"total_options": new_total_options, "conflict_options": new_conflict_options, "dependent_options": new_dependent_options}}

    return new_relation_data


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='''
    CarpetFuzz - an NLP-based fuzzing assitance tool for generating valid option combinations.
        simplify_relation.py - restrict the number of options to reduce memory consumption.
    ''', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--relation', type=str, help = 'Path to input relation file (json format).', required=True)
    parser.add_argument('--number', type=int, help = 'Restrict the number of options (default=50)', default=50)
    parser.add_argument('--dict', type=str, help='Path to option-value dictionary file.', required=True)
    parser.add_argument("--bindir", type=str, help='Path to instrumented ELF file.', required=True)
    parser.add_argument("--seeddir", type=str, help='Path to seed file', required=True)
    parser.add_argument("--showmap", type=str, help='Path to afl-showmap in CarpetFuzz-fuzzer (default=fuzzer/afl-showmap)', default=os.path.join(project_dir, "fuzzer/afl-showmap"))

    args = parser.parse_args()

    relation_path = args.relation
    target_number = args.number
    dict_file_path = args.dict
    program_dir = args.bindir
    seed_dir = args.seeddir
    showmap_path = args.showmap

    if not os.path.exists(relation_path):
        print("[x] Error: Cannot find the relation file - %s" % relation_path)
        exit(1)

    with open("%s" % relation_path, "r") as f:
        relation_data = json.loads(f.read())

    program = relation_path.split("_")[1][:-5] 

    with open(dict_file_path, "r") as f:
        dict_data = json.loads(f.read())

    if program not in dict_data:
        print("[x] Cannot find the program %s in dictionary." % (program))
        exit(1)

    restricted_relation_data = restrictOptions(relation_data, target_number, dict_data[program], program_dir, showmap_path, seed_dir)

    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
        
    with open("%s/relation_%s_simplify.json" % (output_dir, program), "w") as f:
        f.write(json.dumps(restricted_relation_data))

    print("[OK] Successfully restrict the relationship file - %s/relation_%s_simplify.json" % (output_dir, program))
    
    