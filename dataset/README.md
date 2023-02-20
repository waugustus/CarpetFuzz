# Dataset

This directory contains the training dataset and validation dataset used by our model. You can use them to train your own model.

## Directory Structure ##

```
dataset
├── manpage_dataset
│   ├── man.zip
├── training_dataset
│   ├── negative.txt
│   └── positive.txt
└── validation_dataset
    ├── negative.txt
    └── positive.txt
```

1. **manpage_dataset**
   
   The corpus crawled from the Debian Manpages Project.
   
2. **training_dataset**
   
   Training dataset obtained from the manpage_dataset with active learning process.

3. **validation_dataset**
   
   Validation dataset for the final model. 