# Models #

This directory contains the models used by CarpetFuzz.

|Name|Description|Training Parameter|
|---|---|---|
|elmo-constituency-parser-2020.02.10.tar.gz (Download)|AllenNLP's parser model. We use this model to obtain the constituency tree of a sentence.| - |
|linux_w2v_300d.model|Word2Vec model trained on the Debian Manpages. This model is used to map words into vectors|size = 300, window = 5, and other default settings|
|xgb.m|XGBoost model trained on our dataset. This model is used to identify the relationship among options from a sentence.| max_depth = 6, n_estimators = 200, colsample_bytree = 0.8, subsample = 0.8, learning_rate = 0.1, and other default settings|