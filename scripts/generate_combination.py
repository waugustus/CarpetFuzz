import argparse
import os
import sys
import json
from utils.execution_util import ExecutionUtil

script_dir = sys.path[0]
project_dir = os.path.abspath(os.path.join(script_dir, ".."))
output_model_dir = os.path.join(project_dir, "output/model")
output_combination_dir = os.path.join(project_dir, "output/combination")


execution_util = ExecutionUtil()

def generatePictModel(program, relation_data):

    print("[*] Generating Pict Model for %s ..." % (program))
    model_content = ""

    options = relation_data['options']['total_options']
    conflict_options = relation_data['options']['conflict_options']
    dependent_options = relation_data['options']['dependent_options']

    for opt in options:
        model_content += "%s: 0, 1\n" % opt
    
    for conflict_pair in conflict_options:
        model_content += "IF [%s] = 1 THEN [%s] <> 1;\n" % (conflict_pair[0], conflict_pair[1])
    
    for dependent_key in dependent_options:
        if "||" in dependent_options[dependent_key]:
            d = dependent_options[dependent_key].split("||")
            model_content += "IF [%s] = 1 Then [%s] = 1 or [%s] = 1;\n" % (dependent_key, d[0], d[1])
        elif "&&" in dependent_options[dependent_key]:
            d = dependent_options[dependent_key].split("&&")
            model_content += "IF [%s] = 1 Then [%s] = 1 and [%s] = 1;\n" % (dependent_key, d[0], d[1])
        else:
            model_content += "IF [%s] = 1 Then [%s] = 1;\n" % (dependent_key, dependent_options[dependent_key])
    
    if not os.path.exists(output_model_dir):
        os.mkdir(output_model_dir)
        
    model_path = "%s/model_%s.txt" % (output_model_dir, program)

    with open(model_path, "w") as f:
        f.write(model_content)

    return model_path

def executePict(pict_path, model_path):
    print("[*] Executing Pict ...")
    cmd = "%s %s /c /o:6" % (pict_path, model_path)
    output = execution_util.executeCommand(cmd)
    return output

def parsePictResult(result):
    print("[*] Parsing Pict results ...")
    option_list = result.splitlines()[0].split("\t")
    combination_list = []
    for line in result.splitlines()[1:]:
        combination = ""
        for idx, label in enumerate(line.split("\t")):
            if label == "1":
                combination += "%s " % (option_list[idx])
        combination_list.append(combination)
    return combination_list

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='''
    CarpetFuzz - an NLP-based fuzzing assitance tool for generating valid option combinations.
        generate_combination.py - generate valid option combinations based on the relationship file.
    ''', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--relation', type=str, help = 'Path to input relation file (json format).', required=True)
    parser.add_argument('--pict', type=str, help = 'Path to the ELF file of pict (default=pict/build/cli/pict)', default=os.path.join(project_dir, "pict/build/cli/pict"))

    args = parser.parse_args()

    relation_path = args.relation
    pict_path = args.pict

    if not os.path.exists(relation_path):
        print("[x] Error: Cannot find the relation file - %s" % relation_path)
        exit(1)
    if not os.path.exists(pict_path):
        print("[x] Error: Cannot find the ELF file of pict - %s" % pict_path)
        exit(1)

    with open("%s" % relation_path, "r") as f:
        relation_data = json.loads(f.read())

    program = relation_path.split("_")[1][:-5]
    
    model_path = generatePictModel(program, relation_data)

    result = executePict(pict_path, model_path)

    combination_list = parsePictResult(result)

    if not os.path.exists(output_combination_dir):
        os.mkdir(output_combination_dir)
    
    with open(os.path.join(output_combination_dir, "combination_%s.txt" % (program)), "w") as f:
        f.write("\n".join(combination_list))

    print("[OK] Successfully generate the combination file - %s/combination_%s.json" % (output_combination_dir, program))
    
    