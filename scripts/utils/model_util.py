import joblib
import nltk
import gensim
import numpy as np


class ModelUtil:
    def __init__(self, xgb_model_path, sent2vec_model_path, feature_num, threshold):
        self.xgb_clf = joblib.load(xgb_model_path)
        self.sent2vec_model = gensim.models.Word2Vec.load(sent2vec_model_path)
        self.num_features = feature_num
        self.threshold = threshold
        return

    def prediction(self, preprocessed_list):
        preprocessed_sent_list = [item['preprocessed_sent'] for item in preprocessed_list]
        token_list = [nltk.word_tokenize(sent) for sent in preprocessed_sent_list]
        vocabulary_dict = set(self.sent2vec_model.wv.index_to_key)
        vector_list = [self.__average_word_vectors(tokenized_sentence, vocabulary_dict) for tokenized_sentence in token_list]
        predicted = self.xgb_clf.predict_proba(vector_list)
        prediction_list = [1 if pred[1] >= self.threshold else 0 for pred in predicted]

        positive_list, negative_list = [], []
        for idx in range(len(prediction_list)):
            tmp_dict = {}
            tmp_dict['cmd'] = preprocessed_list[idx]['cmd']
            tmp_dict['option'] = preprocessed_list[idx]['option']
            tmp_dict['sent'] = preprocessed_list[idx]['sent']
            if prediction_list[idx] == 1:
                positive_list.append(tmp_dict)
            else:
                negative_list.append(tmp_dict)
        return positive_list, negative_list

    def __average_word_vectors(self, words, vocabulary):
        feature_vector = np.zeros((self.num_features,), dtype='float64')
        nwords = 0
        for word in words:
            if word in vocabulary:
                nwords = nwords+1
                feature_vector = np.add(feature_vector, self.sent2vec_model.wv[word])
        if nwords:
            feature_vector = np.divide(feature_vector,nwords)
        return feature_vector