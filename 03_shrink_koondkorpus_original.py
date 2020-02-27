#
#  After fetching koondkorpus' original texts, it turned out 
#  that the size of the new JSON corpus  was  bigger  than the 
#  size of the original ENC 2017 selection. This was due to ENC 
#  2017 having an amount of incomplete / broken documents -- 
#  if we took the original koondkorpus' texts in place of them, 
#  the size of our corpus increased.
#  
#  The soultion was to shrink the corpus: fit the subcorpora to 
#  the given token size limit by making new random selections.
#   
#  (Optionally, you may skip the random selection part and use 
#   the results of our random selection. See below for details)
#
#  The script runs without arguments, provided that required 
#  input folder is available.
#

import os, os.path, json, re
from sys import argv
from collections import defaultdict
from random import randint
import shutil

from estnltk import Text
from estnltk.converters import text_to_json, json_to_text

from enc2017_extra_utils import fetch_text_category
from enc2017_extra_utils import create_enc_filename_stub

# input directory containing original koondkorpus texts:
raw_koond_json_dir = 'koond_original_texts'

# Where to copy files
output_dir = '_plain_texts_json'
if not os.path.exists(output_dir):
    os.mkdir(output_dir)

# File containing results of our random selection
shrink_result_fnames = 'enc2017_selection_json_filenames.txt'
# If you do not want to repeat the random selection, but you want 
# to use the results of our random selection, then switch this on: 
skip_random_selection = False
if skip_random_selection:
    assert os.path.exists(shrink_result_fnames)



if skip_random_selection:
    # --------------------
    # Skip the random selection: take the results of our random selection
    # --------------------
    # 1) Load names of koondkorpus' files used in our experiment
    nc_fnames = set()
    with open(shrink_result_fnames, 'r', encoding='utf-8') as in_f:
        for line in in_f:
            line = line.strip()
            if line.startswith('nc_'):
                nc_fnames.add(line)
    # 2) Copy corresponding files
    print()
    print(' Copying files from {!r} to {!r} ...'.format(raw_koond_json_dir, output_dir))
    print()
    copied_files = 0
    for fname in os.listdir(raw_koond_json_dir):
        fpath = os.path.join( raw_koond_json_dir, fname )
        if fname in nc_fnames:
            src_path = os.path.join(raw_koond_json_dir, fname)
            trg_path = os.path.join(output_dir, fname)
            copied = shutil.copy(src_path, trg_path)
            copied_files += 1
    print(' Total {} files copied.'.format(copied_files) )
    print()
else:
    # --------------------
    # Make a new random selection
    # --------------------
    # 1) Gather size statistics about files & subcorpora
    word_counts = defaultdict(int)
    doc_counts  = defaultdict(int)
    corpus_doc_index = defaultdict(lambda: defaultdict(int))

    broken_files = []
    c = 0
    for fname in os.listdir(raw_koond_json_dir):
        if fname.endswith('.json'):
            fpath = os.path.join( raw_koond_json_dir, fname )
            try:
                original_text = json_to_text(file=fpath)
                doc_category  = fetch_text_category( original_text )
                fname_stub    = create_enc_filename_stub( original_text )
                tokens = [t for t in original_text.text.split() if len(t)>0]
                token_count = len(tokens)
                word_counts[doc_category] += token_count
                word_counts['TOTAL'] += token_count
                doc_counts[doc_category] += 1
                doc_counts['TOTAL'] += 1
                assert fname_stub not in corpus_doc_index[doc_category]
                corpus_doc_index[doc_category][fname_stub] += token_count
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                print('Broken file:', fname)
                broken_files.append( fname )
                original_text = None
            c += 1
    print('Total broken files: ',len(broken_files),'/',c)
    print('Initial statistics:')
    for k in sorted(word_counts.keys()):
        if k != 'TOTAL':
            print('{:>15}'.format(k),'\twords:','{:>15}'.format(word_counts[k]),'\tdocs:',doc_counts[k])
    k = 'TOTAL'
    print('{:>15}'.format(k),'\twords:','{:>15}'.format(word_counts[k]),'\tdocs:',doc_counts[k])
    print()

    # 2) Make the random selection
    rand_pick_words_limit = 2100000
    random_pick_target_corpora = ['nc_fiction', 'nc_periodicals', 'nc_science']
    print(' Picking randomly ',rand_pick_words_limit,' words from corpora: {!r}'.format(random_pick_target_corpora ))
    document_picks = defaultdict(set)
    target_subcorpus_size = defaultdict(int)
    for target_corpus in random_pick_target_corpora:
        if target_corpus not in corpus_doc_index.keys():
            continue
        assert target_corpus in corpus_doc_index.keys()
        doc_ids = list(corpus_doc_index[target_corpus].keys())
        target_subcorpus_size[target_corpus] = 0
        failed_attempts = 0
        while target_subcorpus_size[target_corpus] < rand_pick_words_limit:
            i = randint(0, len(doc_ids) - 1)
            doc_id = doc_ids[i]
            if doc_id not in document_picks[target_corpus]:
                doc_words = corpus_doc_index[target_corpus][doc_id]
                target_subcorpus_size[target_corpus] += doc_words
                document_picks[target_corpus].add(doc_id)
                failed_attempts = 0
            else:
                failed_attempts += 1
                if failed_attempts >= 100:
                    print('(!) 100 unsuccessful random picks in a row: terminating ...')
                    break
        #break
    print()
    k = 'nc_periodicals'
    if k not in random_pick_target_corpora:
        # Add all from the periodicals (no need to shrink)
        doc_ids = corpus_doc_index[k].keys()
        for doc_id in doc_ids:
            document_picks[k].add( doc_id )
            target_subcorpus_size[k] += corpus_doc_index[k][doc_id]

    print(' Results of the (random) selection:')
    picked_doc_ids = set()
    for k in sorted(document_picks.keys()):
        print(' ',k, 'original_docs:',len(document_picks[k]), ' words:',target_subcorpus_size[k] )
        for doc in document_picks[k]:
            doc_str = str(doc)
            assert doc_str not in picked_doc_ids
            picked_doc_ids.add(doc_str)
    print()
    print(' Copying files from {!r} to {!r} ...'.format(raw_koond_json_dir, output_dir))
    print()
    copied_files = 0
    for doc_id in picked_doc_ids:
        fname = doc_id+'.json'
        src_path = os.path.join(raw_koond_json_dir, fname)
        trg_path = os.path.join(output_dir, fname)
        copied = shutil.copy(src_path, trg_path)
        copied_files += 1
    print(' Total {} files copied.'.format(copied_files) )
    print()

