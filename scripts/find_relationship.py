import argparse
import json
import os
import sys
from utils.groff_util import GroffUtil
from utils.nlp_util import NLPUtil
from utils.model_util import ModelUtil
from utils.relationship_util import RelationshipUtil

script_dir = sys.path[0]
project_dir = os.path.abspath(os.path.join(script_dir, ".."))
model_dir = "%s/models" % project_dir
output_dir = "%s/output/relation" % project_dir

groff_util = GroffUtil()
nlp_util = NLPUtil("%s/elmo-constituency-parser-2020.02.10.tar.gz" % model_dir)
relationship_util = RelationshipUtil(nlp_util)

# ############################## #
# #### Explicit R-sentences #### #
# ############################## #

def identifyExplicitRSentences(program, opt_desc_dict, alias_dict, all_option_list):
    # Convert opt_desc_dict to the format required for model scripts
    formatted_list = nlp_util.formatOptDescDict(program, opt_desc_dict)
    preprocessed_list = nlp_util.preprocessing(formatted_list, alias_dict, all_option_list)

    sent2vec_model_path = "%s/linux_w2v_300d.model" % model_dir
    xgb_model_path = "%s/xgb.m" % model_dir
    feature_num = 300
    threshold = 0.5
    model_util = ModelUtil(xgb_model_path, sent2vec_model_path, feature_num, threshold)
    # Explicit R-sentences
    positive_list, negative_list = model_util.prediction(preprocessed_list)
    return positive_list, negative_list

# ############################## #
# #### Implicit R-sentences #### #
# ############################## #

def identifyImplicitRSentences(program, opt_desc_dict):
    # Extract topic sentences (first sentence)
    topic_sent_list = nlp_util.extractTopicSentList(program, opt_desc_dict)

    implicit_rsent_list = relationship_util.findImplicitPair(topic_sent_list)

    return implicit_rsent_list

# ################################# #
# #### Relationship Extraction #### #
# ################################# #

def extractRelationships(explicit_rsent_list, implicit_rsent_list, alias_dict, option_list):
    relationship_dict = {}

    explicit_relationship_dict = relationship_util.extractExplicitRelationships(explicit_rsent_list, alias_dict, option_list)
    implicit_relationship_dict = relationship_util.extractImplicitRelationships(implicit_rsent_list)
    
    relationship_dict["conflict"] = explicit_relationship_dict["conflict"] + implicit_relationship_dict["conflict"]
    relationship_dict["conflict"] = relationship_util.deduplicationConflictList(relationship_dict["conflict"])
    relationship_dict["dependent"] = explicit_relationship_dict["dependent"]
    relationship_dict = relationship_util.deduplicationRelationshipDict(relationship_dict)

    return relationship_dict

# ##################################### #
# #### Output Content Construction #### #
# ##################################### #

def constructOutputDict(option_list, relationship_dict):
    output_dict = {}
    output_dict['options'] = {}
    output_dict['options']["total_options"] = option_list
    output_dict['options']['conflict_options'] = relationship_dict['conflict']
    output_dict['options']['dependent_options'] = relationship_dict['dependent']

    return output_dict

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='''
    CarpetFuzz - an NLP-based fuzzing assitance tool for generating valid option combinations.
        find_relationship.py - find relationships between options from the manual file.
    ''', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--file', type=str, help = 'Input manpage file (groff format).', required=True)

    args = parser.parse_args()

    input_path = args.file

    # Parsing groff file
    program, opt_desc_dict = groff_util.parseGroff(input_path)
    if len(opt_desc_dict) == 0:
        print("[ERROR] Failed to parse %s" % input_path )
        exit(0)

    # Remove quotations
    opt_desc_dict = nlp_util.removeQuotationsInOptDescDict(opt_desc_dict)

    # Split overlapping options
    opt_desc_dict, alias_dict = nlp_util.splitOptDescDict(opt_desc_dict)

    # Obtain all options list
    option_list = nlp_util.getOptList(opt_desc_dict, alias_dict, True)

    # Identify R-sentences
    explicit_rsent_list, explicit_non_rsent_list = identifyExplicitRSentences(program, opt_desc_dict, alias_dict, option_list)
    implicit_rsent_list = identifyImplicitRSentences(program, opt_desc_dict)

    # Extract relationship
    relationship_dict = extractRelationships(explicit_rsent_list, implicit_rsent_list, alias_dict, option_list)

    # Construct and save relation.json file
    option_list_without_alias = nlp_util.getOptList(opt_desc_dict, alias_dict, False)
    output_dict = constructOutputDict(option_list_without_alias, relationship_dict)

    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
        
    with open("%s/relation_%s.json" % (output_dir, program), "w") as f:
        f.write(json.dumps(output_dict))

    print("[OK] Successfully generate the relationship file - %s/relation_%s.json" % (output_dir, program))
    

    
