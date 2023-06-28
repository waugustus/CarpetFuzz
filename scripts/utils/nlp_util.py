import re
import string
import nltk
import spacy
import lemminflect
from nltk.corpus import wordnet
from nltk.tree import Tree, ParentedTree
from utils.constant import STOPWORD_LIST, CONTRACTION_MAP, GLOVE_WORD_LIST, REPLACE_ITEM_LIST, SELF_REPLACE_ITEM, ANTONYM_PREPOSITION_LIST
from allennlp.predictors import Predictor 
import networkx as nx

class NLPUtil:
    def __init__(self, constituency_model_path):
        self.nlp = spacy.load("en_core_web_sm")
        self.predictor_constituency = Predictor.from_path(constituency_model_path)
        return
    
    def isParallelStructure(self, constituency_tree_1, constituency_tree_2):
        relation_tree_1 = self.__getNodes(constituency_tree_1)
        relation_tree_2 = self.__getNodes(constituency_tree_2)
        if relation_tree_1 == relation_tree_2:
            return True
        if len(relation_tree_1) == 0 or len(relation_tree_2) == 0:
            return False
        len_relation_tree_1 = len(relation_tree_1)
        len_relation_tree_2 = len(relation_tree_2)
        if len_relation_tree_1>len_relation_tree_2:
            if relation_tree_2[:len_relation_tree_2-1][:-1] == relation_tree_2[:-1][:-1] and relation_tree_2[:-1][-1] in relation_tree_1[:len_relation_tree_2-1][-1]:
                return True
        elif len_relation_tree_1<len_relation_tree_2:
            if relation_tree_2[:len_relation_tree_1-1][:-1] == relation_tree_1[:-1][:-1] and relation_tree_1[:-1][-1] in relation_tree_2[:len_relation_tree_1-1][-1]:
                return True
        return False

    def findShortestPath(self, edges, source, target):
        graph = nx.Graph(edges)
        try:
            shortest_path = nx.shortest_path(graph, source=source, target=target)
        except nx.NetworkXNoPath:
            shortest_path = []
        return shortest_path

    def getSynonymsAndAntonyms(self, word):
        synonyms = []
        antonyms = []
        for syn in wordnet.synsets(word):
            for l in syn.lemmas():
                synonyms.append(l.name())
                if l.antonyms():
                    antonyms.append(l.antonyms()[0].name())
        return list(set(synonyms)), list(set(antonyms))

    def predictConstituencyTree(self, sent):
        sent = sent.replace("..",".").replace("(","").replace(")","").replace("{","").replace("}","")
        tree = self.predictor_constituency.predict(sentence=sent)['trees']
        constituency_tree = Tree.fromstring(tree)
        return constituency_tree

    def removeQuotationsInOptDescDict(self, opt_desc_dict):
        new_opt_desc_dict = {}

        for opt in opt_desc_dict:
            new_opt_desc_dict[opt.replace("\"", "").replace("\'", "").strip()] = opt_desc_dict[opt].replace("\"", "").replace("\'", "").strip()
        return new_opt_desc_dict

    def splitOptDescDict(self, opt_desc_dict):
        splitted_opt_desc_dict = {}
        alias_dict = {}
        blank_opt_list = []
        for opt in opt_desc_dict:
            desc = opt_desc_dict[opt].replace("  ", " ").strip()
            # If the desc is empty, we combine this opt with the following opt
            if desc == "":
                blank_opt_list.append(opt)
                continue
            doc = self.nlp(desc)
            topic_sentence = list(doc.sents)[0].text

            # Combine blank options and reset the list
            if len(blank_opt_list) > 0:
                opt = "%s, %s" % (", ".join(blank_opt_list).strip(), opt)
                blank_opt_list = []

            # options combined by "and", we regard these options as independent of each other
            if " and " in opt:
                for splitted_part in opt.split(" and "):
                    # A, B, C, D, and E
                    for sub_part in splitted_part.split(","):
                        splitted_opt_list = re.split('\||,|/', sub_part)
                        if len(splitted_opt_list) > 1:
                            key = self.removeValueField(splitted_opt_list[0])
                            if key in splitted_opt_desc_dict:
                                splitted_opt_desc_dict[key] += " %s" % desc
                            else:
                                splitted_opt_desc_dict[key] = desc
                            tmp_alias_list = []
                            for alias in splitted_opt_list[1:]:
                                if not self.removeValueField(alias).startswith("-"):
                                    continue
                                tmp_alias_list.append(self.removeValueField(alias))
                            if len(tmp_alias_list) > 0:
                                alias_dict[key] = tmp_alias_list
                            
                        else:
                            key = self.removeValueField(sub_part)
                            if not key.startswith("-"):
                                continue
                            if key in splitted_opt_desc_dict:
                                splitted_opt_desc_dict[key] += " %s" % desc
                            else:
                                splitted_opt_desc_dict[key] = desc
            else:
                # "or" works like ", "
                opt = opt.replace(" or ", ", ")
                # replace pattern like "-w --warning"
                opt = re.sub("(-{1,2}[a-z0-9A-Z-*=]+) +(?=-{1,2}[a-z0-9A-Z-*=]+)", r"\1, ", opt)
                # Several options are put together (, / |)
                splitted_opt_list = re.split('\||,|/', opt)
                if len(splitted_opt_list) > 1:
                    # If the subject is a plural, we regard these options as independent of each other
                    if self.__isStartsWithDTPl(topic_sentence):
                        for splitted_opt in splitted_opt_list:
                            splitted_opt_desc_dict[self.removeValueField(splitted_opt)] = desc
                    # Else we take the first option and record other alias
                    else:
                        key = self.removeValueField(splitted_opt_list[0])
                        if key in splitted_opt_desc_dict:
                            splitted_opt_desc_dict[key] += " %s" % desc
                        else:
                            splitted_opt_desc_dict[key] = desc
                        tmp_alias_list = []
                        for alias in splitted_opt_list[1:]:
                            if not self.removeValueField(alias).startswith("-"):
                                continue
                            tmp_alias_list.append(self.removeValueField(alias))
                        if len(tmp_alias_list) > 0:
                            alias_dict[key] = tmp_alias_list
                else:
                    key = self.removeValueField(opt)
                    if key in splitted_opt_desc_dict:
                        splitted_opt_desc_dict[key] += " %s" % desc
                    else:
                        splitted_opt_desc_dict[key] = desc
        return splitted_opt_desc_dict, alias_dict

    def formatOptDescDict(self, program, opt_desc_dict):
        
        formatted_list = []

        for opt in opt_desc_dict:

            desc = opt_desc_dict[opt].replace("  ", " ").strip()
            doc = self.nlp(desc)

            for sent in doc.sents:
                if sent.text.isspace():
                    continue
                formatted_list.append({"cmd": program, "option": opt, "sent": sent.text})

        return formatted_list


    # Extract the first sentence (topic sentence), preprocess the topic sentence, and extract predicate and object
    def extractTopicSentList(self, program, opt_desc_dict):
        topic_sent_list = []

        for opt in opt_desc_dict:

            desc = opt_desc_dict[opt].replace("  ", " ").strip()
            doc = self.nlp(desc)

            for sent in doc.sents:
                sentence = self.preprocessIDRSentence(sent.text)
                if sentence == "":
                    continue
                constituency_tree = self.predictConstituencyTree(sentence)
                simplified_tree, topic_sentence, neg_flag = self.__simplifyConstituencyTree(constituency_tree)
                predicate, object, prt = self.__getPredAndObj(topic_sentence)
                if neg_flag and predicate:
                    predicate = "non_%s" % predicate 
                # Several options are put together
                splitted_opt_list = re.split('\||,', opt)
                if len(splitted_opt_list) > 1:
                    # If the subject is a plural, we regard these options as independent of each other
                    if self.__isStartsWithDTPl(sentence):
                        for splitted_opt in splitted_opt_list:
                            topic_sent_list.append({"cmd": program, "option": splitted_opt.split(" ")[0], "sent": sent.text, "predicate": predicate, "object": object, "prt": prt, "tree": simplified_tree})
                    # Else we take the first option
                    else:
                        topic_sent_list.append({"cmd": program, "option": splitted_opt_list[0].split(" ")[0], "sent": sent.text, "predicate": predicate, "object": object, "prt": prt, "tree": simplified_tree})
                else:
                    topic_sent_list.append({"cmd": program, "option": splitted_opt_list[0].split(" ")[0], "sent": sent.text, "predicate": predicate, "object": object, "prt": prt, "tree": simplified_tree})
                break

        return topic_sent_list

    # preprocessing for model
    def preprocessing(self, formatted_list, alias_dict, all_option_list):
        preprocessed_list = []
        for sent_dict in formatted_list:

            # Not need to consider '=' in model prediction, so we remove it
            sent = sent_dict['sent'].replace("=", " ")
            option = sent_dict['option']
            alias_list = alias_dict[option] if option in alias_dict else []

            preprocessed_sent, option_map = self.replaceOption(sent, all_option_list)
        
            preprocessed_sent = re.sub("^this (switch|flag)", "This ", preprocessed_sent, flags=re.I)
            preprocessed_sent = re.sub("^this (?!option)", "This option ", preprocessed_sent, flags=re.I)
            # May have multiple "option"
            preprocessed_sent = re.sub("(option ?){2,}", "option", preprocessed_sent)

            option_map_new = {}
            for opt in option_map:
                if opt == option or (option in alias_dict and opt in alias_list):
                    option_map_new[option_map[opt]] = "param_current"
                else:
                    option_map_new[option_map[opt]] = "param_other"

            contractions_pattern = re.compile('({})'.format('|'.join(CONTRACTION_MAP.keys())), flags=re.IGNORECASE | re.DOTALL)
            expanded_sentence = contractions_pattern.sub(self.__expandMatch, preprocessed_sent)

            filtered_sentence = re.sub(r'[?|$|&|*|%|@|(|)|~]', r'', expanded_sentence.strip())

            tokens = nltk.word_tokenize(filtered_sentence)

            tagged_sent = nltk.pos_tag(tokens)
            lemmas_sent = []
            for tag in tagged_sent:
                word_pos = self.__getPosFromTag(tag[1])
                if not self.isReplacedOption(tag[0]) and word_pos is not None:
                    lemmas_sent.append(lemminflect.getLemma(tag[0], upos=word_pos)[0])
                else:
                    lemmas_sent.append(tag[0])

            stopword_list = STOPWORD_LIST
            filtered_tokens = [
                token for token in lemmas_sent if token.lower() not in stopword_list]
            norm_sent = re.sub("--{1,}", "", " ".join(filtered_tokens))

            item_list = []
            for item in nltk.word_tokenize(norm_sent):
                if self.isReplacedOption(item):
                    item = option_map_new[item]
                item_list.append(item)

            new_sent = " ".join(item_list).lower()
            # remove digit
            norm_sent = re.sub(r'[0-9]+', '', new_sent).strip()
            # remove extra spaces
            norm_sent = re.sub(' +', ' ', norm_sent)
            # remove punctuation
            norm_sent = re.sub(r"[%s]+" % string.punctuation, "", norm_sent)
            # some replace rules
            norm_sent = norm_sent.lower().replace('-- ', '--').replace('- ', '-').replace(' ( ', '(').replace(' ) ', ')').strip()

            norm_sent_tokens = [token for token in norm_sent.split(' ') if token in GLOVE_WORD_LIST]
            sent_dict["preprocessed_sent"] = ' '.join(norm_sent_tokens).replace("  ", " ")
            preprocessed_list.append(sent_dict)
        return preprocessed_list

    # Preprocessing for IDR relationship extraction
    def preprocessIDRSentence(self, sentence):
        # Remove all content in quotations
        sentence = re.sub(r'\(.*?\)', '', sentence)
        # remove digit, maybe we can use token.like_num to do this
        sentence = re.sub(r'[0-9]+', '', sentence)
        sentence = re.sub(r' +', ' ', sentence)
        sentence = re.sub(r'\.{2,}', '.', sentence)
        sentence = re.sub(r'[{}\(\)]', '', sentence)
        sentence = re.sub(r'by default', '', sentence, flags=re.I)
        sentence = re.sub(r'^note that', '', sentence, flags=re.I)
        sentence = sentence.split(":")[0].strip()
        # Add subject to topic sentence starting with a verb
        
        sentence = self.__addSubjectToSentence(sentence)
        sentence, option_map_dict = self.replaceOption(sentence)
        # Avoid splitted mistakenly by constituency parser, "non-" - > "non -"
        sentence = sentence.replace("-", "_")
        
        return sentence

    # Preprocessing for EDR relationship extraction
    def preprocessEDRSentence(self, sentence):
        sentence = re.sub(r'^by default', '', sentence, flags=re.I)
        sentence = re.sub(r'^note that', '', sentence, flags=re.I)
        sentence = self.__addSubjectToSentence(sentence)

        return sentence.strip()


    def splitSentence(self, sent, option_map):
        sent = sent.replace("(","").replace(")","")
        sub_sent_list = []
        sub_option_map_list = []
        doc = self.nlp(sent)
        conj_token_index_list = []

        # {'-A': 'option1'} -> {'option1': '-A'}
        reversed_option_map = {v: k for k, v in option_map.items()}

        for token in doc:
            if (token.tag_.startswith("V") or token.head.tag_.startswith("V")) and token.dep_ in ["conj"]:
                conj_token_index_list.append(token.i)
        conj_token_index_list.append(token.i + 1)
        start_index= 0
        for conj_token_index in conj_token_index_list:
            sent_token_list = []
            sub_option_map = {}
            for i in range(start_index, conj_token_index):
                # Skip the last cc
                if i == conj_token_index - 1 and doc[i].text in ["and", "or", "but"]:
                    continue
                if doc[i].text in reversed_option_map:
                    sub_option_map[reversed_option_map[doc[i].text]] = doc[i].text
                # Save the original option
                sent_token_list.append(doc[i].text)
            sub_sent_list.append(" ".join(sent_token_list).strip().strip(",").strip())
            sub_option_map_list.append(sub_option_map)
            start_index = conj_token_index
    
        return sub_sent_list, sub_option_map_list

    def extractConditionClauseList(self, processed_sent):
        constituency_tree = self.predictConstituencyTree(processed_sent)
        return self.__getSubtrees(0, constituency_tree)

    def extractMainClause(self, processed_sent):
        condition_clause_list = self.extractConditionClauseList(processed_sent)
        main_clause = ""
        
        if len(condition_clause_list) > 0:
            # Remove condition clause
            for condition_clause in condition_clause_list:
                try:
                    main_clause = processed_sent.replace(condition_clause, "")
                except:
                    pass
        else:
            main_clause = processed_sent
        return main_clause

    def getReplaceItem(self):
        for item in REPLACE_ITEM_LIST:
            yield item
    
    def getSelfReplaceItem(self):
        return SELF_REPLACE_ITEM

    def replaceOption(self, sent, included_list=[]):
        option_map_dict = {}
        option_list = self.__findOptionsInSent(sent)
        item_generator = self.getReplaceItem()
        for option in option_list:
            if option not in option_map_dict:
                if included_list:
                    # e.g., --keep-*
                    r = re.compile("^%s.*$" % option[:-1]) if option[-1] == "*" else re.compile("^%s$" % option)
                    # Options not belong to this program
                    if not any(r.match(opt) for opt in included_list):
                        sent = re.sub("%s(?![a-zA-Z0-9\-\*])" % re.escape(option), "option", sent).strip()
                        continue
                replace_item = next(item_generator)
                option_map_dict[option] = replace_item
                sent = re.sub("%s(?![a-zA-Z0-9\-\*])" % re.escape(option.replace("*", "\*")), replace_item, sent).strip()
            
        r = sorted(option_map_dict.items(), key=lambda kv: len(str(kv[0])), reverse=True)
        option_map_dict = {i[0]: i[1] for i in r}

        if sent.startswith("(") and sent.endswith(")"):
            sent = sent.lstrip("(").rstrip(")").strip()

        return sent, option_map_dict

    def isReplacedOption(self, text):
        target_list = REPLACE_ITEM_LIST + [SELF_REPLACE_ITEM]
        return text in target_list

    def removeValueField(self, opt):
        # -a=xxx, -a[xxxx], -a<xxxx>, -a xxx
        return re.split("=|\[|<| ", opt.strip())[0]

    # Only used in check if an option belong to a program
    def getOptList(self, opt_desc_dict, alias_dict, alias_flag):
        opt_list = []
        for key in opt_desc_dict:
            if key == "alias":
                continue
            opt_list.append(key)
        if alias_flag:
            for opt in alias_dict:
                opt_list.extend(alias_dict[opt])
        return list(set(opt_list))

    def findConjunctsOfToken(self, token):
        conj_list = []
        cc = None
        for conj in token.conjuncts:
            # check if the conj is an option
            if self.isReplacedOption(conj.text):
                conj_list.append(conj)
                if conj.i > 0 and conj.nbor(-1).dep_ == "cc":
                    cc = conj.nbor(-1)
            else:
                # Check if option in the children 
                for child in conj.subtree:
                    if self.isReplacedOption(child.text):
                        conj_list.append(child)
                        if child.i > 0 and child.nbor(-1).dep_ == "cc":
                            cc = child.nbor(-1)
        return conj_list, cc

    def comparePredicate(self, predicate_1, predicate_2):
        # Since predicate can have more than one word, we split them
        predicate_1_root = predicate_1.split(" ")
        predicate_2_root = predicate_2.split(" ")
        if len(predicate_1_root) != len(predicate_2_root):
            return []
        rel_list = []

        for idx in range(len(predicate_1_root)):
            predicate1 = predicate_1_root[idx]
            predicate2 = predicate_2_root[idx]
            synonyms_vb1 = self.getSynonymsAndAntonyms(predicate1)[0]
            antonyms_vb1 = self.getSynonymsAndAntonyms(predicate2)[1]
            synonyms_vb2 = self.getSynonymsAndAntonyms(predicate2)[0]
            antonyms_vb2 = self.getSynonymsAndAntonyms(predicate2)[1]

            if predicate1 == predicate2 or predicate1 in synonyms_vb2 or predicate2 in synonyms_vb1:
                rel_list.append("synonyms")
            elif predicate1 in antonyms_vb2 or predicate2 in antonyms_vb1 or ("non_" + predicate1 == predicate2) or ("non_" + predicate2) == predicate1:
                rel_list.append("antonyms")
            else:
                rel_list.append("none")
        return rel_list

    def comparePrepositions(self, prep_1, prep_2):
        # Since predicate can have more than one word, we split them
        prep_1_root = prep_1.split(" ")
        prep_2_root = prep_2.split(" ")
        if len(prep_1_root) != len(prep_2_root):
            return []
        rel_list = []

        for idx in range(len(prep_1_root)):
            prep1 = prep_1_root[idx]
            prep2 = prep_2_root[idx]

            if prep1 == prep2:
                rel_list.append("synonyms")
            elif prep1 not in ANTONYM_PREPOSITION_LIST or prep2 not in ANTONYM_PREPOSITION_LIST:
                rel_list.append("none")
            elif ANTONYM_PREPOSITION_LIST[prep_1] == prep_2 and ANTONYM_PREPOSITION_LIST[prep_2] == prep_1:
                rel_list.append("antonyms")
            else:
                rel_list.append("none")
        return rel_list

    def removeOverlapElements(self, list1, list2):
        return [e for e in list1 if e not in list2]

    def searchVerbAndAuxOfToken(self, token):
        aux_token, verb_token, with_to_flag = None, None, False
        tmp_token, root_token = None, None
        while True:
            if not tmp_token and token.pos_ in ['AUX', 'VERB']:
                tmp_token = token
            if token.dep_ == "ROOT":
                root_token = token
            if token == token.head:
                break
            token = token.head
        # If this sentence has no verb, check if the root is misjudged
        if not tmp_token:
            if root_token:
                root_lemma_list = lemminflect.getAllLemmas(root_token.text)
                if "VERB" in root_lemma_list:
                    verb_token = root_token
        elif tmp_token.pos_ == 'AUX':
            # 'Ought' as a modal verb cannot be conjugated, i.e. 'oughts'
            if tmp_token.text == "ought":
                aux_token = tmp_token
                # verb is the head of 'to'
                verb_token = aux_token.nbor(1).head
                with_to_flag = True
            elif tmp_token.lemma_ == "be":
                aux_token = tmp_token
                verb_token = aux_token.head
                with_to_flag = False
        elif tmp_token.pos_ == "VERB":
            # If the verb is need/have to, regard it as an aux
            if tmp_token.lemma_ in ['have', 'need'] and tmp_token.nbor(1).text == 'to':
                aux_token = tmp_token
                verb_token = aux_token.nbor(1).head
                with_to_flag = True
            # Normal verb
            else:
                verb_token = tmp_token
                aux_token_list = [child for child in verb_token.children if child.pos_ == 'AUX']
                aux_token = None if len(aux_token_list) == 0 else aux_token_list[0]
                with_to_flag = False
        return aux_token, verb_token, with_to_flag

    def skipModifierToken(self, token):
        ret_token = token
        if token.dep_ in ["nmod", "appos" ,"compound", "amod"]:
            for ancestor in token.ancestors:
                if ancestor.pos_ == "NOUN" and ancestor.dep_ not in ["nmod", "appos" ,"compound", "amod"]:
                    ret_token = ancestor
                    break
        return ret_token

    def searchMissedKeyword(self, token):
        ret_token = None
        # e.g., Similar to -A
        if token.dep_ == "pobj":
            ret_token = token.head
            while ret_token != ret_token.head and (ret_token.pos_ != "ADJ"):
                ret_token = ret_token.head
        return ret_token

    # e.g., --keep-*
    def expandOptionsInRegex(self, option, all_option_list):
        r = re.compile("^%s.*$" % option[:-1])
        return list(filter(r.match, all_option_list))

    # Some options may miss their "-", we attempt to fix them 
    def fixBrokenOptions(self, sentence, option_list):
        if "following options:" not in sentence:
            return sentence
        sentence = sentence.replace("-", "_")
        doc = self.nlp(sentence)
        end_pattern_list = ["."]
        fix_start_flag = False
        for token in doc:
            if fix_start_flag:
                if not token.is_punct:
                    # Regard as an option if the fixed token is in the option list
                    if "-%s" % token.text.replace("_", "-") in option_list:
                        sentence = sentence.replace(token.text, "-%s" % token.text.replace("_", "-"))
                    elif "--%s" % token.text.replace("_", "-") in option_list:
                        sentence = sentence.replace(token.text, "--%s" % token.text.replace("_", "-"))
            if token.lemma_ == "option" and doc[token.i - 1].text == "following":
                fix_start_flag = True
            if fix_start_flag and token.text in end_pattern_list:
                break
        return sentence.replace("_", "-")

    def __addSubjectToSentence(self, sentence):
        
        word_list = sentence.split(" ")
        first_word = word_list[0].lower()
        first_word_lemma_list = lemminflect.getAllLemmas(first_word)

        if "VERB" in first_word_lemma_list:
            doc = self.nlp(sentence)
            # If the first word also can be a noun
            if "NOUN" in first_word_lemma_list:
                second_word = word_list[1].lower()
                second_word_lemma_list = lemminflect.getAllLemmas(second_word)
                # If the first word is a plural noun, it must not be a verb, so it must be a singular
                # If the second word is a VBZ, the first word cannot be verb
                if "VERB" in second_word_lemma_list and second_word in lemminflect.getInflection(second_word_lemma_list['VERB'][0], tag="VBZ") and doc[1].pos_ in ["VERB", "AUX"]:
                    sentence = re.sub(' +', ' ', " ".join(word_list))
                    return sentence
            wnl_word = first_word_lemma_list['VERB'][0]
            tmp_list = word_list[1:]
            isPassive = False
            if doc[0].pos_ == "VERB":
                if doc[0].tag == "VBN":
                    isPassive = True
            else:
                # If the first word can be both VBN and VB, we regard it as VB ("do")
                if first_word in lemminflect.getInflection(wnl_word, 'VBN') and first_word not in lemminflect.getInflection(wnl_word, 'VB'):
                    isPassive = True
            prefix_list = ["It is", lemminflect.getInflection(wnl_word, tag='VBN')[0]] if isPassive else ["It", lemminflect.getInflection(wnl_word, tag='VBZ')[0]]
            word_list = prefix_list + tmp_list

        sentence = re.sub(' +', ' ', " ".join(word_list))

        return sentence

    def __findOptionsInSent(self, sent):
        # Add a space for regex, and tokenize to seperate option and punctuations
        sentence = " %s " % (self.__joinMistakenlySplitedToken(" ".join(nltk.word_tokenize(sent))))
        option_list = [item.strip() for item in re.findall(r"(?<=\s)-{1,2}.*?(?=\s)", sentence)]
        return list(set(option_list))

    def __simplifyConstituencyTree(self, tree):
        # Remove redundant subtreess
        found_subtree = False
        for i, subtree in enumerate(tree):
            if subtree.label() == "S" and not found_subtree: 
                found_subtree = True
            elif subtree.label() == "S" and found_subtree:
                del tree[i]
        if tree[-1].label() == ",":
            del tree[-1]

        # Remove ADVP subtrees
        ptree = ParentedTree.convert(tree)
        advp_list = []
        for subtree in ptree.subtrees():
            if subtree.label() == "ADVP":
                advp_list.append(subtree)
        for advp_subtree in advp_list:
            advp_subtree.parent().remove(advp_subtree)

        # Remove aux at beginning
        # start with a model verb
        neg_flag = False
        remove_subject_flag = False
        if len(ptree) > 1 and ptree[1].label() == "VP":
            if ptree[1][0].label() == "MD" or (ptree[1][0].label().startswith("VB") and ptree[1][0].leaves()[0].lower() in ["does", "oughts"]):
                if ptree[1][1].label() == "RB":
                    ptree[1].remove(ptree[1][1])
                    neg_flag = True
                ptree[1].remove(ptree[1][0])

                if ptree[0].leaves()[0].lower() == "it":
                    ptree[0].parent().remove(ptree[0])
                    remove_subject_flag = True

        new_sentence = self.__addSubjectToSentence(self.__joinMistakenlySplitedToken(' '.join(ptree.leaves())))
        if remove_subject_flag:
            new_sentence = self.__addSubjectToSentence(new_sentence)
        new_tree = self.predictConstituencyTree(new_sentence)

        return new_tree, new_sentence, neg_flag
    
    def __joinMistakenlySplitedToken(self, sentence):
        return sentence.replace("-- ","--").replace(" - ", "-").replace("- *", "-*")

    def __expandMatch(self, contraction):
        match = contraction.group(0)
        first_char = match[0]
        expanded_contraction = CONTRACTION_MAP.get(match)\
            if CONTRACTION_MAP.get(match)\
            else CONTRACTION_MAP.get(match.lower())
        expanded_contraction = first_char+expanded_contraction[1:]
        return expanded_contraction

    def __getPosFromTag(self, tag):
        pos = None
        if tag.startswith('J'):
            pos = "ADJ"
        elif tag.startswith('V'):
            pos = "VERB"
        elif tag.startswith('N'):
            pos = "NOUN"
        elif tag.startswith('R'):
            pos = "ADV"
        return pos

    def __getPredAndObj(self, sentence):

        doc = self.nlp(sentence)

        edge_list = []
        verb_candidate_list = []
        attr, predicate, object, prt = "", "", "", ""
        root_token, object_candidate_token = None, None
        find_root_flag, find_verb_flag = False, False
            
        # Traverse and collect key list
        for token in doc:
            # collect edges of current token for graph
            for child in token.children:
                edge_list.append((token, child))
            if not find_verb_flag and token.tag_.startswith("V"):
                find_verb_flag = True
            if not find_root_flag and token.dep_ == "ROOT":
                root_token = token
                find_root_flag = True
                # If the root is a word like "be", "become", we only need to check its subject
                if root_token.lemma_ in ["be", "become", "seem"] or (root_token.lemma_ == "look" and doc[root_token.i + 1].text == "like"):
                    target_child_list = [child for child in root_token.children if child.dep_ in ["nsubj", "csubj"]]
                    if len(target_child_list) > 0:
                        subject_token = target_child_list[0]
                        if subject_token.pos_ not in ["PRON"] and subject_token.text not in ["default"]:
                            predicate = "be"
                            closest_mod_token = self.__getClosestModToken(subject_token)
                            pobj_token = None
                            find_prep_result = [child for child in subject_token.children if child.text == "of"]
                            if len(find_prep_result) > 0:
                                find_pobj_result = [child for child in find_prep_result[0].children if child.dep_ == "pobj"]
                                if len(find_pobj_result) > 0:
                                    pobj_token = find_pobj_result[0]
                            object = "%s %s" % (closest_mod_token.text, subject_token.text) if closest_mod_token else subject_token.text
                            if pobj_token:
                                closest_pobj_mod_token = self.__getClosestModToken(pobj_token)
                                object = "%s of %s %s" % (object, closest_pobj_mod_token.text, pobj_token.text) if closest_pobj_mod_token else "%s of %s" % (object, pobj_token.text)
                            return predicate.lower(), object.lower(), prt.lower()
                if root_token.tag_.startswith("V"):
                    predicate = lemminflect.getLemma(root_token.text, upos="VERB")[0]
                    find_prep_result = [child.text for child in root_token.children if child.dep_ in ["prt", "prep"]]
                    if len(find_prep_result) > 0:
                        # if "%predicate_%prep" is a verb phrase if it is in the wordnet dataset
                        prt = find_prep_result[0] if len(wordnet.synsets("%s_%s" % (predicate, find_prep_result[0]))) > 0 else ""
            elif token.head.dep_ == "ROOT" and ((token.dep_ in ['pobj', 'dobj', 'nsubjpass'])):
                object_candidate_token = token
            # check 'to do' 
            # elif token.tag_ in ['VBN','VBZ','VB']:
            elif find_root_flag and token.tag_ == "TO" and token.head.pos_ == "VERB":
                    verb_token = token.head
                    verb_candidate_list.append(verb_token)

        # Fot topic sentence without a verb, we regard the root word as the object
        if not find_verb_flag:
            predicate = ""
            object = root_token.text
        else:
            for verb_token in verb_candidate_list:
                verb_count = 0
                # Find all verbs behind root
                for node in self.findShortestPath(edge_list, root_token, verb_token):
                    if node.pos_ == "VERB":
                        verb_count += 1
                if verb_count == 2:
                    predicate += " " + lemminflect.getLemma(verb_token.text, upos='VERB')[0]
                    find_prep_result = [child.text for child in verb_token.children if child.dep_ in ["prt", "prep"]]
                    if len(find_prep_result) > 0:
                        # if "%predicate_%prep" is a verb phrase if it is in the wordnet dataset
                        prt = find_prep_result[0] if len(wordnet.synsets("%s_%s" % (predicate, find_prep_result[0]))) > 0 else ""
                    object_list =  [child.text for child in verb_token.children if child.dep_ in ['nsubj', 'nsubjpass']]
                    object = object_list[0] if len(object_list) > 0 else ""
                    attr = " ".join([lemminflect.getLemma(child.text,upos='VERB')[0] for child in verb_token.children if child.dep_ in ['acomp','xcomp']])
            
            if object_candidate_token:
                closest_mod_token = None
                pobj_token = None
                closest_mod_token = self.__getClosestModToken(object_candidate_token)
                find_prep_result = [child for child in object_candidate_token.children if child.text == "of"]
                if len(find_prep_result) > 0:
                    find_pobj_result = [child for child in find_prep_result[0].children if child.dep_ == "pobj"]
                    if len(find_pobj_result) > 0:
                        pobj_token = find_pobj_result[0]
                object = "%s %s" % (closest_mod_token.text, object_candidate_token.text) if closest_mod_token else object_candidate_token.text
                if pobj_token:
                    closest_pobj_mod_token = self.__getClosestModToken(pobj_token)
                    object = "%s of %s %s" % (object, closest_pobj_mod_token.text, pobj_token.text) if closest_pobj_mod_token else "%s of %s" % (object, pobj_token.text)

        predicate = self.__joinMistakenlySplitedToken(re.sub(' +', ' ', predicate.replace("be", "") + " " + attr).strip())
        object = self.__joinMistakenlySplitedToken(object)
        return predicate.lower(), object.lower(), prt.lower()
    
    def __getClosestModToken(self, token):

        closest_mod_token = None
        for child in token.children:
            # Get the closest compound/nmod
            if child.dep_ in ['compound','nmod']:
                if not closest_mod_token:
                    closest_mod_token = child
                else:
                    if abs(child.i - token.i) < abs(closest_mod_token.i - token.i):
                        closest_mod_token = child
        return closest_mod_token

    def __getNodes(self, constituency_tree):
        productions = []
        for child in constituency_tree:
            child_productions = child.productions()
            for prod in child_productions:
                prod = str(prod)
                if "'" not in prod:
                    productions.append(prod)
        if len(productions) > 0:
            productions[-1] = productions[-1].split(' ')[0]
        return  productions

    def __getSubtrees(self, granularity, tree):
        subtrees = []
        if granularity == 0:
            for subtree in tree.subtrees():
                if subtree.label() == "SBAR" and subtree.leaves()[0].lower() in ['if','when','unless','while', 'after', 'only', 'just', 'even']:
                    subtrees.append(' '.join(subtree.leaves()))

        elif granularity == 1:
            for subtree in tree.subtrees():
                if subtree.label() in ["S","SBAR","FRAG"]:
                    subtrees.append(' '.join(subtree.leaves())) 
                
        return subtrees

    def __isStartsWithDTPl(self, sentence):
        doc = self.nlp(sentence)

        for token in doc:
            if token.tag_ in ['DT'] and token.text.lower() in ["these"]:
                if token.head.tag_ in ['NNS'] and token.head.text.lower() in ["options", "switches", "flags", "commands", "directives", "configures"]:
                    token = token.head
                for child in token.children:
                    if child.dep_ in ["appos"]:
                        return False
                return True
        return False