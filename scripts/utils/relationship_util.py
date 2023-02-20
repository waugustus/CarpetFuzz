import re
import itertools
from utils.constant import DEPENDENT_WORD_DICT, CONFLICT_WORD_DICT, DEONTIC_MODAL_LIST, NEGATIVE_WORD_LIST, ONLY_WORD_LIST
class RelationshipUtil:
    def __init__(self, nlp_util):
        self.nlp_util = nlp_util
        return

    def findImplicitPair(self, topic_sent_list):
        implicit_pair_list = []
        for pair in itertools.combinations(topic_sent_list, 2):
            
            if not any([pair[0]['object'], pair[1]['object'], pair[0]['predicate'], pair[0]['predicate']]):
                continue
            # Must have same objects
            if pair[0]["object"] != pair[1]["object"]:
                continue
            # The object "value" is usually used to refer to the option value, rather than declaring a specific attribute
            elif pair[0]["object"] in ["values", "value"]:
                continue
            # If two sentences have the same predicate ("be", "become",...) and the same subject, we think they are assigning different attributes to the same thing. Therefore, they are conflict.
            if pair[0]["predicate"] == "be" and pair[1]["predicate"] == "be":
                implicit_pair_list.append(pair)
            # Print/display/show do not conflict
            elif pair[0]["predicate"] in ["print", "display", "show"] and pair[1]["predicate"] in ["print", "display", "show"]:
                continue
            # With the same predicate, the prt need to be opposite (e.g., get on / get off)
            elif pair[0]["predicate"] == pair[1]["predicate"] and any([pair[0]["prt"], pair[1]["prt"]]) :
                prt_rel_list = self.nlp_util.comparePrepositions(pair[0]["prt"], pair[1]["prt"])
                if "antonyms" in prt_rel_list:
                    implicit_pair_list.append(pair)
            else:
                # Must have synonyms or antonyms predicates
                rel_list = self.nlp_util.comparePredicate(pair[0]["predicate"], pair[1]["predicate"])
                # If the two predicate have no relation 
                if len(rel_list) == 0 or "none" in rel_list:
                    continue
                # Two words in antonyms relation means conflict
                if "antonyms" in rel_list:
                    implicit_pair_list.append(pair)
                elif "synonyms" in rel_list:
                    # Must have parallel trees
                    constituency_tree_1 = pair[0]['tree']
                    constituency_tree_2 = pair[1]['tree']
                    if self.nlp_util.isParallelStructure(constituency_tree_1, constituency_tree_2):
                        implicit_pair_list.append(pair)
        
        return implicit_pair_list

    def extractExplicitRelationships(self, explicit_rsent_list, alias_dict, option_list):
        explicit_relationship_dict = {"conflict": [], "dependent": {}}

        all_option_list = []
        # {option: [alias]} -> {alias: option}
        alias_dict_new = {}
        for opt in option_list:
            all_option_list.append(opt)
            if opt in alias_dict:
                all_option_list += alias_dict[opt]
                for o in alias_dict[opt]:
                    alias_dict_new[o] = opt
                
        relation_dict_list = []
        for sent_dict in explicit_rsent_list:
            tmp_dict  = {}
            tmp_dict['cmd'] = sent_dict['cmd']
            # Remove value
            tmp_dict['option'] = self.nlp_util.removeValueField(sent_dict['option'])

            # Replace pronoun
            sentence = sent_dict['sent'].replace("=", " ").replace('`',' ').strip("'")
            # Try to fix broken option, if it has
            sentence = self.nlp_util.fixBrokenOptions(sentence, all_option_list)

            # Replace this program's option to pattern "option[0-9]", and replace option not belong to this program to pattern "option" 
            # Since we do not support options in pattern "-{1,2}\s+=\s+", we do not add such options in the option_map (though they are identified as valid options)
            replaced_sent, option_map = self.nlp_util.replaceOption(sentence, all_option_list)

            if len(option_map.keys()) == 0:
                print("[INFO] Explicit R-sentence without any option: %s" % sentence)
                continue

            # Split compound sentence into simple sentences
            sub_sent_list, sub_option_map_list = self.nlp_util.splitSentence(replaced_sent, option_map)

            for i, sub_sent in enumerate(sub_sent_list):
                sub_sent = self.nlp_util.preprocessEDRSentence(sub_sent)

                sub_option_map = sub_option_map_list[i]
                # Sub-sentence without any option
                if len(sub_option_map.keys()) == 0:
                    continue
                if tmp_dict['option'] not in sub_option_map:
                    sub_option_map[tmp_dict['option']] = self.nlp_util.getSelfReplaceItem()
                # Replace subject
                sub_sent = re.sub('this (option|switch|flag)', sub_option_map[tmp_dict['option']], sub_sent, flags=re.I)
                sub_sent = re.sub("^(it|this)(?=\s)", sub_option_map[tmp_dict['option']], sub_sent, flags=re.I)
                tmp_dict['sent'] = sub_sent
                info_dict = self.__organizeSentInfoDict(tmp_dict, sub_option_map)
                # {'cmd': 'xxx', 'conflict': [], 'dependent': {}}
                relation_dict = self.__extractRelationDictFromInfoDict(info_dict, alias_dict_new, all_option_list)
                relation_dict_list.append(relation_dict)

        # Merge relationships between multiple sub-sentences
        for item in relation_dict_list:
            for conflict_pair in item['conflict']:
                if conflict_pair not in explicit_relationship_dict['conflict'] and conflict_pair[::-1] not in explicit_relationship_dict['conflict']:
                    explicit_relationship_dict['conflict'].append(conflict_pair)
            for dependent_subj in item['dependent']:
                if dependent_subj not in explicit_relationship_dict['dependent']:
                    explicit_relationship_dict['dependent'][dependent_subj] = item['dependent'][dependent_subj]
                elif dependent_subj in explicit_relationship_dict['dependent'] and explicit_relationship_dict['dependent'][dependent_subj] != item['dependent'][dependent_subj]:
                    # Save the longest one
                    if explicit_relationship_dict['dependent'][dependent_subj] in item['dependent'][dependent_subj]:
                        explicit_relationship_dict['dependent'][dependent_subj] = item['dependent'][dependent_subj]
                    elif item['dependent'][dependent_subj] in explicit_relationship_dict['dependent'][dependent_subj]:
                        explicit_relationship_dict['dependent'][dependent_subj] = explicit_relationship_dict['dependent'][dependent_subj]
                    else:
                        print("[WARN] Duplicate item found: %s, %s" % ( str({dependent_subj: explicit_relationship_dict['dependent'][dependent_subj]}), str({dependent_subj: str(item['dependent'][dependent_subj])})))
        
        # Check if some dependent pairs are also conflict pairs
        for d_subj in explicit_relationship_dict['dependent']:
            if "||" in explicit_relationship_dict['dependent'][d_subj]:
                new_obj_list = []
                for d_obj in explicit_relationship_dict['dependent'][d_subj].split("||"):
                    if [d_subj, d_obj] in explicit_relationship_dict['conflict'] or [d_obj, d_subj] in explicit_relationship_dict['conflict']:
                        print("[INFO] Partial overlap between conflict and dependent: %s, %s" % (str(explicit_relationship_dict['dependent'][d_subj]), str([d_obj, d_subj])))
                    else:
                        new_obj_list.append(d_obj)
                explicit_relationship_dict['dependent'][d_subj] = "||".join(new_obj_list)
            else:
                d_obj = explicit_relationship_dict['dependent'][d_subj]
                if [d_subj, d_obj] in explicit_relationship_dict['conflict'] or [d_obj, d_subj] in explicit_relationship_dict['conflict']:
                    explicit_relationship_dict['dependent'].pop(d_subj)

        return explicit_relationship_dict
    
    def extractImplicitRelationships(self, implicit_rsent_list):
        implicit_relationship_dict = {"conflict": []}
        for pair in implicit_rsent_list:
            implicit_conflict_pair = []
            for sent_dict in pair:
                implicit_conflict_pair.append(sent_dict['option'])
            implicit_relationship_dict["conflict"].append(implicit_conflict_pair)
        return implicit_relationship_dict

    def deduplicationConflictList(self, conflict_list):
        deduplicated_conflict_list = []
        for conflict_pair in conflict_list:
            if conflict_pair not in deduplicated_conflict_list and conflict_pair[::-1] not in deduplicated_conflict_list:
                deduplicated_conflict_list.append(conflict_pair)
        return deduplicated_conflict_list

    # When a pair is identified as both conflict and dependent, we trust the conflict one
    def deduplicationRelationshipDict(self, relationship_dict):
        deduplicated_relationship_dict = {"conflict": [], "dependent": {}}
        conflict_list = relationship_dict["conflict"]
        dependent_dict = relationship_dict["dependent"]

        for conflict_pair in conflict_list:
            if conflict_pair[0] in dependent_dict and dependent_dict[conflict_pair[0]] == conflict_pair[1]:
                del dependent_dict[conflict_pair[0]]
            if conflict_pair[1] in dependent_dict and dependent_dict[conflict_pair[1]] == conflict_pair[0]:
                del dependent_dict[conflict_pair[1]]
        
        deduplicated_relationship_dict["conflict"] = conflict_list
        deduplicated_relationship_dict["dependent"] = dependent_dict

        return deduplicated_relationship_dict

    # Organize necessary information for extracting relationships
    def __organizeSentInfoDict(self, sent_dict, option_map):
        cmd = sent_dict['cmd']
        option = sent_dict['option']
        sentence = sent_dict['sent']
    
        clause_list = self.nlp_util.extractConditionClauseList(sentence)
        clause = clause_list[0] if len(clause_list) > 0 else None
        clause_traverse_dict = self.__traverseBackward(clause) if clause and len(option_map) > 0 else None
        clause_relationship = self.__determineRelationFromTraverseDict(clause_traverse_dict, "clause")

        main_clause = self.nlp_util.extractMainClause(sentence)
        main_clause_traverse_dict = self.__traverseBackward(main_clause)
        # If the subj_list is empty and the current option is not in the obj_list, we regard the current option as subject
        if len(main_clause_traverse_dict['subj_list']) == 0 and option_map[option] not in main_clause_traverse_dict['obj_list']:
            main_clause_traverse_dict['subj_list'] = [option_map[option]]
        # Pass only word in clause to main clause
        if clause_traverse_dict:
            main_clause_traverse_dict['only_list'] += clause_traverse_dict['only_list']
        main_clause_relationship = self.__determineRelationFromTraverseDict(main_clause_traverse_dict, "main")

        info_dict = {
            'cmd': cmd, 
            'sent': sentence,
            'option': option, 
            'option_map': option_map, 
            'main_clause_traverse': main_clause_traverse_dict,
            'main_clause_relationship': main_clause_relationship,
            'clause_traverse': clause_traverse_dict,
            'clause_relationship': clause_relationship
        }

        return info_dict

    def __determineRelationFromTraverseDict(self, traverse_dict, type="main"):
        if traverse_dict:
            # Positive with an even number of neg_words and Negative with an odd number of neg_words
            isNegative = True if len(traverse_dict['neg_list']) % 2 else False
            
            subj_keyword = traverse_dict['keyword_list'][0]
            obj_keyword = traverse_dict['keyword_list'][1]

            subj_relationship, subj_init_pos = self.__getKeywordRelationship(subj_keyword)
            obj_relationship, obj_init_pos = self.__getKeywordRelationship(obj_keyword)

            # Conflict > Dependent > Neutral
            # Conflict + Conflict: 3, Dependent + Dependent: 2, Conflict + Neutral: 1.5, Dependent + Neutral: 1
            score_dict = {"conflict": 1.5, "dependent": 1, "neutral": 0}

            if type == "clause":
                # Not necessary to check the modality in clause
                subj_score = score_dict[subj_relationship]
                obj_score = score_dict[obj_relationship]

                # Default return the obj relationship unless subj relationship is more strong
                relationship = subj_relationship if subj_score > obj_score else obj_relationship
                # If negative, reverse the relationship
                if isNegative and relationship != "neutral":
                    relationship = "conflict" if relationship == "dependent" else "dependent"
            else:
                subj_score = score_dict[subj_relationship] + score_dict[subj_init_pos]
                obj_score = score_dict[obj_relationship] + score_dict[obj_init_pos]

                category = subj_relationship if subj_score > obj_score else obj_relationship
                init_pos = subj_init_pos if subj_score > obj_score else obj_init_pos
                aux = traverse_dict['aux_list'][0] if subj_score > obj_score else traverse_dict['aux_list'][1]

                # Key word not in the relation keyword dict
                if category == "neutral":
                    relationship = "neutral"
                else:
                    # If the aux word is a deontic modal
                    isDenoticModel = True if aux in DEONTIC_MODAL_LIST else False
                    # If only word occurs:
                    hasOnlyWord = True if len(traverse_dict['only_list']) else False
                    # If share object
                    hasSharedObj = True if traverse_dict["has_shared_object"] else False

                    # Finite State Machine: Conflict - neutral - Dependent
                    state_machine_list = ['conflict', "neutral", "dependent"]
                    init_index = state_machine_list.index(init_pos)
                    
                    # Reverse transfer
                    if isNegative:
                        relationship = state_machine_list[init_index + 1] if category == "conflict" else state_machine_list[init_index - 1]
                    # Forward transfer
                    elif isDenoticModel or hasOnlyWord or hasSharedObj:
                        relationship = state_machine_list[max(0, init_index - 1)] if category == "conflict" else state_machine_list[min(init_index + 1, len(state_machine_list) - 1)]
                    # No transfer
                    else:
                        relationship = state_machine_list[init_index]
        # empty dict
        else:
            relationship = "neutral"
        return relationship


    def __extractRelationDictFromInfoDict(self, info_dict, alias_dict_new, all_option_list):

        option = info_dict['option']
        
        relation_dict = {'cmd': info_dict['cmd']}
        relation_dict['conflict'] = []
        relation_dict['dependent'] = {}
        
        main_clause_traverse_dict = info_dict['main_clause_traverse']
        clause_traverse_dict = info_dict['clause_traverse']

        main_clause_relationship = info_dict['main_clause_relationship']
        clause_relationship = info_dict['clause_relationship']

        option_map = info_dict['option_map']
        
        relationship = None
        subj_list, obj_list = [], []

        # Clause: A, Main clause: B
        # 1. (1,1):  A ->  B <=> ^B -> ^A: B is dependent on A 
        # 2. (1,0):  A -> ^B <=>  B -> ^A: A is conflict with B, and B is conflict with A
        # 3. (0,0): ^A -> ^B <=>  B ->  A: A is dependent on B
        # 4. (0,1): ^A ->  B <=> ^B ->  A: non-A is conflict with non-B, and non-B is conflict with non-A
        if clause_traverse_dict:

            relation_list = [-1, -1]

            if clause_relationship == "conflict":
                relation_list[0] = 0
            elif clause_relationship == "dependent":
                relation_list[0] = 1
            clause_subj_list = clause_traverse_dict['subj_list']
            clause_subj_cc = clause_traverse_dict['subj_cc']
            clause_obj_list = clause_traverse_dict['obj_list']
            clause_obj_cc = clause_traverse_dict['obj_cc']
            
            if main_clause_relationship == "conflict":
                relation_list[1] = 0
            elif main_clause_relationship == "dependent":
                relation_list[1] = 1
            main_clause_subj_list = main_clause_traverse_dict['subj_list']
            main_clause_subj_cc = main_clause_traverse_dict['subj_cc']
            main_clause_obj_list = main_clause_traverse_dict['obj_list']
            main_clause_obj_cc = main_clause_traverse_dict['obj_cc']


            # TODO: If the clause/subject has a subject and object, then fully analyze the relationship between subject and object, and do an overall conflict/dependency analysis
            if len(clause_obj_list) > 0 and len(clause_subj_list) > 0:
                print("[WARN] Unexpected situation: Clause has a complete relationship: %s" % info_dict['sent'])
            elif len(main_clause_obj_list) > 0 and len(main_clause_subj_list) > 0:
                print("[WARN] Unexpected situation: Main clause has a complete relationship: %s" % info_dict['sent'])
            else:
                if relation_list == [1, 1]:
                    subj_list = main_clause_obj_list if len(main_clause_obj_list) > 0 else main_clause_subj_list
                    obj_list = clause_obj_list if len(clause_obj_list) > 0 else clause_subj_list
                    obj_cc = clause_obj_cc if len(clause_obj_list) > 0 else clause_subj_cc
                    relationship = "dependent"
                elif relation_list == [1, 0]:
                    subj_list = clause_obj_list if len(clause_obj_list) > 0 else clause_subj_list
                    obj_list = main_clause_obj_list if len(main_clause_obj_list) > 0 else main_clause_subj_list
                    obj_cc = main_clause_obj_cc if len(main_clause_obj_list) > 0 else main_clause_subj_cc
                    relationship = "conflict"
                elif relation_list == [0, 0]:
                    subj_list = clause_obj_list if len(clause_obj_list) > 0 else clause_subj_list
                    obj_list = main_clause_obj_list if len(main_clause_obj_list) > 0 else main_clause_subj_list
                    obj_cc = main_clause_obj_cc if len(main_clause_obj_list) > 0 else main_clause_subj_cc
                    relationship = "dependent"
                elif relation_list == [0, 1]:
                    subj_list = main_clause_obj_list if len(main_clause_obj_list) > 0 else main_clause_subj_list
                    subj_list.append("^")
                    obj_list = clause_obj_list if len(clause_obj_list) > 0 else clause_subj_list
                    obj_list.append("^")
                    obj_cc = clause_obj_cc if len(clause_obj_list) > 0 else clause_subj_cc
                    relationship = "conflict"
        # No clause
        else:
            subj_list = main_clause_traverse_dict['subj_list']
            obj_list = main_clause_traverse_dict['obj_list']
            obj_cc = main_clause_traverse_dict['obj_cc']
            relationship = main_clause_relationship

        if relationship:
            relation_dict = self.__formatRelationship(subj_list, obj_list, obj_cc, relationship, option_map, relation_dict, alias_dict_new, all_option_list)

        return relation_dict

    def __traverseBackward(self, processed_sent):
        doc = self.nlp_util.nlp(processed_sent)
        traverse_dict = {}
        subj_list, obj_list, neg_list, only_list, edge_list, option_token_list = [], [], [], [], [], []
        verb_list, aux_list, with_to_flag_list, represent_option_list = [None, None], [None, None], [None, None], [None, None]
        subj_cc, obj_cc = None, None
        hasSharedObj = False

        # Traverse and collect key list
        for token in doc:
            # collect edges of current token for graph
            for child in token.children:
                edge_list.append((token, child))
            # collect option_tokens/neg_words/only_words
            if self.nlp_util.isReplacedOption(token.text):
                option_token_list.append(token)
            elif token.lemma_ in NEGATIVE_WORD_LIST:
                neg_list.append(token)
            elif token.lemma_ in ONLY_WORD_LIST:
                only_list.append(token)

        if len(option_token_list) > 0:

            # 1. Search the first option, and find its conjunctions. Then we search the first option's head to find the verb and aux
            # 2. If there is no option remaining, we regard the first option and its conjunctions as subject or object depending on 
            # its dep_ and finish the analysis. Otherwise we regard the first option of the remaining options as the first object.
            # 3. Search the verb and aux of the first object, and search the conjunctions of the first object, aux verbs, and verbs
            # to find all possible objects
            # 4. Check if there is a shared noun of the verbs of subject and object. If there is, we need to make the state transfer.

            # Check the dep of the first option
            first_option_token = option_token_list[0]

            first_conj_list = []
            first_cc = ""
            first_conj_list.append(first_option_token)
            conj_list, cc = self.nlp_util.findConjunctsOfToken(first_option_token)
            first_conj_list.extend(conj_list)
            first_cc = cc if cc else first_cc
            # If the first option is a modifier
            first_option_token = self.nlp_util.skipModifierToken(first_option_token)
            # Search Conjuncts of new token
            if first_option_token != first_conj_list[0]:
                conj_list, cc = self.nlp_util.findConjunctsOfToken(first_option_token)
                first_conj_list.extend(conj_list)
                first_cc = cc if cc else first_cc
            # Search the verb and aux of the first option token
            first_aux_token, first_verb_token, first_with_to_flag = self.nlp_util.searchVerbAndAuxOfToken(first_option_token)

            option_token_list = self.nlp_util.removeOverlapElements(option_token_list, first_conj_list)

            if len(option_token_list) == 0:
                if 'subj' in first_option_token.dep_:
                    subj_list = first_conj_list
                    subj_cc = first_cc
                    i = 0
                else:
                    obj_list = first_conj_list
                    obj_cc = first_cc
                    i = 1
                aux_list[i] = first_aux_token
                verb_list[i] = first_verb_token
                with_to_flag_list[i] = first_with_to_flag
                represent_option_list[i] = first_option_token
            # Regard remaining options as objects, and use the shortest path between subject and object to find the relationship
            else:
                subj_list = first_conj_list
                subj_cc = first_cc
                subj_verb_token = first_verb_token
                aux_list[0] = first_aux_token
                verb_list[0] = first_verb_token
                with_to_flag_list[0] = first_with_to_flag
                represent_option_list[0] = first_option_token

                obj_option_token = option_token_list[0]
                obj_list.append(obj_option_token)
                conj_list, cc = self.nlp_util.findConjunctsOfToken(obj_option_token)
                obj_list.extend(conj_list)
                obj_cc = cc if cc else obj_cc

                obj_option_token = self.nlp_util.skipModifierToken(obj_option_token)
                obj_aux_token, obj_verb_token, obj_with_to_flag = self.nlp_util.searchVerbAndAuxOfToken(obj_option_token)
                aux_list[1] = obj_aux_token
                verb_list[1] = obj_verb_token
                with_to_flag_list[1] = obj_with_to_flag
                represent_option_list[1] = obj_option_token

                # Search Conjuncts of new token
                if obj_option_token != obj_list[0]:
                    conj_list, cc = self.nlp_util.findConjunctsOfToken(obj_option_token)
                    obj_list.extend(conj_list)
                    obj_cc = cc if cc else obj_cc
                # Find conjuncts of verb and aux
                for token in verb_list + aux_list:
                    if token == None:
                        continue
                    conj_list, cc = self.nlp_util.findConjunctsOfToken(token)
                    obj_list.extend(conj_list)
                    obj_cc = cc if cc else obj_cc

                option_token_list = self.nlp_util.removeOverlapElements(option_token_list, obj_list)

                if len(option_token_list) > 0:
                    print("[WARN] Missed options: ", [token.text for token in option_token_list])

                shortest_path = self.nlp_util.findShortestPath(edge_list, subj_verb_token, obj_verb_token)
                if len(shortest_path) > 0 and len([node for node in shortest_path if node.dep_ == "dobj"]) > 0:
                    hasSharedObj = True

        # Collect keyword text. If the verb is "be", put the noun or ADJ as keyword
        ret_keyword_list = []
        for i, token in enumerate(verb_list):
            if token == None:
                keyword = None
                if represent_option_list[i]:
                    keyword_token = self.nlp_util.searchMissedKeyword(represent_option_list[i])
                    keyword = keyword_token.lemma_ if keyword_token else None
            else:
                if token.lemma_ == "be":
                    test_list = [child for child in token.children if "subj" not in child.dep_ and child.pos_ in ["NOUN", "ADJ"]]
                    keyword = test_list[0].lemma_ if len(test_list) > 0 else token.lemma_
                # Combine some compound keywords
                elif token.lemma_ == "make":
                    target_child_list = [child for child in token.children if child.dep_ == "dobj" and child.lemma_ in ["sense"]]
                    if len(target_child_list) > 0:
                        keyword = "%s %s" % (token.lemma_, target_child_list[0].lemma_)
                elif token.lemma_ == "have":
                    target_child_list = [child for child in token.children if child.dep_ == "dobj" and child.lemma_ in ["effect"]]
                    if len(target_child_list) > 0:
                        keyword = "%s %s" % (token.lemma_, target_child_list[0].lemma_)
                else:
                    # If the verb has a complement
                    tmp_keyword = None
                    for child in token.children:
                        if child.dep_ in ['ccomp']:
                            tmp_keyword = child.lemma_
                            break
                    if not tmp_keyword:
                        tmp_keyword = token.lemma_
                    keyword = tmp_keyword
            ret_keyword_list.append(keyword)

        # Collect aux text
        ret_aux_list = []
        for i, token in enumerate(aux_list):
            if token == None:
                aux = None
            else:
                aux = "%s to" % (token.lemma_) if with_to_flag_list[i] == True else "%s" % token.lemma_
            ret_aux_list.append(aux)

        # Remove irelevant neg word
        ret_neg_list = []
        for neg_token in neg_list:
            is_valid = True
            for verb_token in verb_list:
                for token in self.nlp_util.findShortestPath(edge_list, verb_token, neg_token):
                    if token.pos_ == "VERB" and token not in aux_list + verb_list:
                        is_valid = False
                        break
                if is_valid:
                    break
            if is_valid:
                ret_neg_list.append(neg_token)

        traverse_dict["aux_list"] = ret_aux_list
        traverse_dict["keyword_list"] = ret_keyword_list
        traverse_dict["subj_list"] = [token.text for token in subj_list]
        traverse_dict['subj_cc'] = subj_cc.text if subj_cc else "or"
        traverse_dict["obj_list"] = [token.text for token in obj_list]
        traverse_dict['obj_cc'] = obj_cc.text if obj_cc else "or"
        traverse_dict["neg_list"] = [token.text for token in ret_neg_list]
        traverse_dict["only_list"] = [token.text for token in only_list]
        traverse_dict["has_shared_object"] = hasSharedObj

        return traverse_dict

    def __formatRelationship(self, subj_list, obj_list, obj_cc, relationship, option_map, relation_dict, alias_dict_new, all_option_list):

        # {'option_1': '-A', 'option_2': '-B'}
        option_map_new = {v: k for k, v in option_map.items()}

        tmp_list = [[], []]
        for i in range(2):
            l = [subj_list, obj_list][i]
            for opt in l:
                option_name = option_map_new[opt]
                if option_name[-1] == "*":
                    for expanded_option in self.nlp_util.expandOptionsInRegex(option_name, all_option_list):
                        if expanded_option in alias_dict_new:
                            tmp_list[i].append(alias_dict_new[expanded_option])
                        else:
                            tmp_list[i].append(expanded_option)
                else:
                    if option_name in alias_dict_new:
                        tmp_list[i].append(alias_dict_new[option_name])
                    else:
                        tmp_list[i].append(option_name)

        subj_list = list(set(tmp_list[0]))
        obj_list = list(set(tmp_list[1]))

        if relationship == "conflict":
            # If no subj, we regard each obj is conflict with other ones. (e.g., No more than one of ...)
            if len(subj_list) == 0: 
                for c in itertools.combinations(list(set(obj_list)), 2):
                    relation_dict['conflict'].append([option for option in c])
            else:    
                # Need to be negated
                negated_flag = True if subj_list[-1] == "^" else False
                for subj in subj_list:
                    subj_key = "%s^" % subj if negated_flag else subj
                    for obj in obj_list:
                        obj_key = obj
                        if subj_key != obj_key:
                            relation_dict['conflict'].append([subj_key, obj_key])
        elif relationship == "dependent":
            assert len(subj_list) > 0
            for subj in subj_list:
                subj_key = subj if subj in option_map_new else subj
                for obj in obj_list:
                    if obj_cc == "and":
                        relation_dict['dependent'][subj_key] = "&&".join([obj for obj in obj_list if subj_key != obj])
                    elif not obj_cc or obj_cc == "or":
                        relation_dict['dependent'][subj_key] = "||".join([obj for obj in obj_list if subj_key != obj])
        
        return relation_dict

    def __getKeywordRelationship(self, keyword):
        keyword_dict = {"conflict": CONFLICT_WORD_DICT, "dependent": DEPENDENT_WORD_DICT}
        ret_relation = "neutral"
        ret_init_pos = "neutral"
        for category in keyword_dict:
            for init_pos in keyword_dict[category]:
                if keyword in keyword_dict[category][init_pos]:
                    ret_relation = category
                    ret_init_pos = init_pos
                    break
        return ret_relation, ret_init_pos