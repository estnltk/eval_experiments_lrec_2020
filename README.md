
This repository contains source code of the evaluation experiments reported in the paper _"EstNLTK 1.6: Remastered Estonian NLP Pipeline"_ that was submitted for LREC 2020.

The evaluation focuses on the task of full morphological analysis: word and sentence segmentation of the text, followed by morphological analysis and disambiguation.
The main evaluation compares outputs of EstNLTK's previous version (1.4.1), EstNLTK's version 1.6.4beta, and StanfordNLP's version 0.2.0. 
An additional evaluation compares different morphological disambiguation methods of EstNLTK 1.6: the default morphological disambiguation, corpus-based disambiguation and neural morphological disambiguation.

## Prerequisites

In order to conduct the experiments, you need:

* `.vert` files from Estonian National Corpus 2017 (ENC-2017): <br/> 
    [https://doi.org/10.15155/3-00-0000-0000-0000-071E7L](https://doi.org/10.15155/3-00-0000-0000-0000-071E7L) <br/>
    (.xz compressed files should be unpacked into the directory `'scripts_and_data'`)

* JSON files from "Estonian Reference Corpus analysed with EstNLTK ver.1.6_b" (Laur, 2018): <br/>
    [https://doi.org/10.15155/1-00-0000-0000-0000-00156L](https://doi.org/10.15155/1-00-0000-0000-0000-00156L) <br/>
    (.zip compressed files should be unpacked into sub-directory named `'scripts_and_data/koond_raw_json'`)

* [Anaconda](https://www.anaconda.com/distribution/) (or [Miniconda](https://docs.conda.io/en/latest/miniconda.html)) installed and the following environments created:

	* Environment with Python 3.5 that has [EstNLTK v1.4.1](https://github.com/estnltk/estnltk) installed;
	* Environment with Python 3.6 that has [EstNLTK v1.6.4beta](https://github.com/estnltk/estnltk), [StanfordNLP v0.2.0](https://stanfordnlp.github.io/stanfordnlp/), and [tqdm](https://github.com/tqdm/tqdm) installed;

## Experiment steps

Experiment scripts and additional files can be found from the folder `'scripts_and_data'`.

### 1. Preprocessing

Our preprocessing was a long and bumpy road. 
At first, we hoped that we can use the ENC-2017 corpus for all of our experiments. However, it turned out that the Estonian Reference Corpus part in ENC-2017 has a serious flaw: it misses information about paragraph boundaries, which is crucial for sentence segmentation. 
In order to overcome the problem, we took the Estonian Reference Corpus texts from [(Laur, 2018)](https://doi.org/10.15155/1-00-0000-0000-0000-00156L) instead -- from the version of the corpus in which paragraph endings are marked by double newlines.

Before discovering the problems with the Estonian Reference Corpus, we had already made our random selection of documents from ENC-2017, which can be seen in the file `enc2017_index_random_5x2000000.txt`.
During the process of replacing the Estonian Reference Corpus part in our selection with texts from (Laur, 2018), we discovered that an amount of documents (that should have been identical in both corpora) were actually matching only partially. 
It was often that a single document from (Laur, 2018) was split into multiple documents in ENC-2017.
As a result, after replacing the Estonian Reference Corpus part, some of its subcorpora overgrew the token number threshold.
In order to restore the balance in subcorpora, we shrinked the Estonian Reference Corpus part, discarding documents until the threshold was (very roughly) met again.

Preprocessing scripts <br/> (to be run in the Python 3.6 environment):

  * `00_index_corpus.py` -- creates document index for the [ENC-2017](https://doi.org/10.15155/3-00-0000-0000-0000-071E7L) corpus. This index is a basis for making the random selection from the corpus;
  * `01_pick_randomly.py` -- makes a random selection from the corpus, based on the index file created in the previous step. While making the selection, excludes documents of the Estonian UD treebank (based on the information in files prefixed with `exclude_`). As a result, creates the selection index file. <br/> 
  Note: if you do not want to make a new random selection, then you can skip the steps 00 and 01, and use our index file: `enc2017_index_random_5x2000000.txt`;
  * `02a_reduce_koond_json_files.py` -- (optional, but highly recommended step) reduces the Estonian Reference Corpus JSON files of [(Laur, 2018)](https://doi.org/10.15155/1-00-0000-0000-0000-00156L) to files that only contain the raw textual content and metadata. This speeds up the processing in step 02b;
  * `02b_fetch_koond_original_texts.py` -- based on the selection index, processes the Estonian Reference Corpus documents and finds (heuristically) their original textual contents from (Laur, 2018) files. Writes documents with corrected textual content, ENC-2017 metadata and id-s into EstNLTK's JSON files;
  * `03_shrink_koondkorpus_original.py` -- After the step 02b, the size of the Estonian Reference Corpus selection overgrew the token number threshold (because ENC-2017 contains incomplete documents, while (Laur, 2018) has them in full length). This step shrinks the corpus: refits the subcorpora to the token number threshold;
  * `04_postcorrect_koondkorpus_original.py` -- post-processes the JSON corpus obtained in the previous step: removes old sentence annotation markings (single newlines) from texts.
  * `05_fetch_web13_and_wiki17.py` -- finalizes the pre-processing: based on the selection index, fetches documents from ENC-2017's web13 and wiki17 sub-corpora, and saves as EstNLTK's JSON files;

Detailed usage information can be found in headers of the scripts.

The final selection of documents (file names) that we obtained after these preprocessing steps can be found from the file `enc2017_selection_json_filenames.txt`.

### 2. Corpus annotation

Steps 06-12 involve corpus annotation. Note that this is a time-consuming process, and whenever possible, it is recommended to run multiple instances of the annotation script simultaneously to speed it up. Scripts 08-12 can take an argument, which tells into how many parts the corpus should be split, and which part of the corpus should be processed. For instance, passing `(1,2)` to the script instructs it to split the data into 2 parts and to process only the first part of the data. 

Detailed information about the usage can be found in headers of the scripts.     

The script to be run in the Python 3.5 environment:

  * `06_annotate_with_v1_4_json.py` -- annotates json files in the input directory with EstNLTK v1.4;

Scripts to be run in the Python 3.6 environment:

  * `07_convert_v1_4_json_to_v1_6_json.py` -- converts annotations in EstNLTK v1.4 json files to EstNLTK v1.6 format annotations. Saves as json documents;
  * `08_annotate_v1_6_segmentation.py` -- annotates documents for EstNLTK v1.6 segmentation;
  * `09_annotate_v1_6_morph.py` -- annotates documents for EstNLTK v1.6 morphological analysis and (default) disambiguation;
  * `10_annotate_with_stanfordnlp.py` -- annotates documents for StanfordNLP's segmentation and linguistic analysis (uses `processors='tokenize,pos,lemma'`);
  * `11_annotate_v1_6_cb_morph.py` -- annotates documents for EstNLTK's corpus-based morphological analysis and disambiguation;
  * `12_annotate_v1_6_neural_morph.py` -- annotates documents for EstNLTK's neural morphological disambiguator;

### 3. Finding annotation differences

Scripts to be run in the Python 3.6 environment:

  * `13_diff_segment_v1_4_against_v1_6.py` -- finds differences in segmentation annotations of EstNLTK v1.4 and EstNLTK v1.6;
  * `14_diff_segment_against_stanfordnlp.py` -- finds differences in segmentation annotations of EstNLTK v1.6 and StanfordNLP;
  * `15_diff_morph_v1_4_against_v1_6.py` -- finds differences in morphological annotations of EstNLTK v1.4 and EstNLTK v1.6;
  * `16_diff_morph_against_stanfordnlp.py` -- finds differences in morphological annotations of EstNLTK v1.6 and StanfordNLP;
  * `17_diff_morph_v1_6_against_corpusbased.py` -- finds differences in morphological annotations of EstNLTK's default morphological tagger and the corpus-based morphological disambiguator;
  * `18_diff_morph_against_neuraldisamb.py` -- finds differences in morphological annotations of EstNLTK's default morphological tagger and the neural morphological disambiguator;

Each of these scripts creates a separate folder in which it saves the found differences. 
Differences between annotation layers will be accumulated in new layers (so called "diff_layers") and saved again as json files (so that document-wise differences will be available for examination).
In addition, all differences are also aggregated into a single file and formatted in a way that they are more easily judgeable by human evaluators. 
The aggregated "human-readable" differences can be found from text files with the suffix `_diff_gaps.txt`.

Each of the scripts also collects the quantitative results (annotation similarity ratios) during the process.
These results will be printed out after the script finishes its work. 


### 4. Taking random selections for manual evaluation

Once you have obtained big files with "human-readable" differences, you can start making random selections for the manual evaluation.

  * `19_pick_randomly_from_diff_gaps.py` -- selects randomly a number of differences from the given `*_diff_gaps.txt` text file. The selection is balanced in a way that equal number of differences is taken from each sub-corpus; 


## Our results

You can find our results from the folder `'results'`. Annotation similarity ratios are in files prefixed with `eval_`, and manual evaluation results are in files prefixed with `manual_chk_`.

---