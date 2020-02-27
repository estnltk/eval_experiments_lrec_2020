#
#  Skript for making a random selection from the ENC_2017 corpus,
#  based on the index file 'enc2017_index.txt'. 
#  While making the selection, excludes documents used in Estonian 
#  UD treebank based on the lists of document names and url-s in
#  files:
#
#      exclude_ettenten13_urls_list.txt
#      exclude_koond_files_list.txt
#  
#  The script runs without arguments, assuming the index file 
#  and exclusion lists are in the current directory.
#  Creates 'enc2017_index_random_5x2000000.txt' containing
#  the random selection.
#

import re, sys
import os, os.path
from collections import defaultdict

from random import randint

from enc2017_extra_utils import ENC_INDEX_DELIMITER
from enc2017_extra_utils import read_from_enc_index
from enc2017_extra_utils import get_entries_from_enc_index
from enc2017_extra_utils import get_koond_subcorpus_name
from enc2017_extra_utils import get_fields_from_enc_index
from enc2017_extra_utils import load_excludable_docs_list
from enc2017_extra_utils import fix_koond_excludable_docs_list

# words limit for random pick (per corpus)
rand_pick_words_limit = 2000000

# index file
enc_index_file = 'enc2017_index.txt'

# exclude files that are already in another index [if required]
exclude_enc_index = None

# koond
excludable_koond_docs = load_excludable_docs_list('exclude_koond_files_list.txt')
excludable_koond_docs = set(fix_koond_excludable_docs_list( excludable_koond_docs ))

# web13
excludable_web13_docs = set(load_excludable_docs_list('exclude_ettenten13_urls_list.txt', remove_file_ext=False ))

# other index file 
excludable_enc_index_docs = set()
if exclude_enc_index is not None and os.path.exists(exclude_enc_index):
    for r in read_from_enc_index(exclude_enc_index):
        excludable_enc_index_docs.add( r['doc_id'] )

# Check the input
if not os.path.exists(enc_index_file):
    print(' (!) The input index file {!r} is missing.'.format(enc_index_file))
    sys.exit(-1)

subcorpus_token_counter = defaultdict(lambda: defaultdict(int))
for r in read_from_enc_index(enc_index_file):
    if r['doc_id'] in excludable_enc_index_docs:
        continue
    if r['src'] == 'NC':
        src_file = r['src_file_or_url']
        src_file_raw = src_file
        if src_file.endswith('.ma'):
            src_file_raw = src_file[:-3]
        if src_file_raw in excludable_koond_docs:
            continue
        if r['texttype'] in ['periodicals', 'fiction', 'science']:
            key = 'NC_'+r['texttype']
            subcorpus_token_counter[key][r['doc_id']] += r['words']
        koond_subcorpus_name = get_koond_subcorpus_name( src_file )
    elif r['src'] == 'web13':
        doc_id = str(r['doc_id'])
        url = r['src_file_or_url']
        if url in excludable_web13_docs:
            continue
        if r['texttype'] in ['forum', 'blog']:
            key = 'web13_'+r['texttype']
            subcorpus_token_counter[key][r['doc_id']] += r['words']
            key = 'web13_forums_blogs'
            subcorpus_token_counter[key][r['doc_id']] += r['words']
    elif r['src'] == 'wiki17':
        doc_id = str(r['doc_id'])
        key = 'wiki17'
        subcorpus_token_counter[key][r['doc_id']] += r['words']


print(' The corpus available for random selection (without excludable docs):')
for k in subcorpus_token_counter.keys():
    words_total = sum([subcorpus_token_counter[k][d] for d in subcorpus_token_counter[k]])
    print(' ',k, 'original_docs:',len(subcorpus_token_counter[k].keys()), ' words:',words_total )
print()

print(' Picking randomly ',rand_pick_words_limit,' words from each subcorpus:')
#random_pick_target_corpora = ['NC_periodicals', 'NC_fiction', 'NC_science', 'web13_forums_blogs']
#random_pick_target_corpora = ['wiki17']
random_pick_target_corpora = ['NC_periodicals', 'NC_fiction', 'NC_science', 'wiki17', 'web13_forums_blogs']
document_picks = defaultdict(set)
target_subcorpus_size = defaultdict(int)
for target_corpus in random_pick_target_corpora:
    doc_ids = list(subcorpus_token_counter[target_corpus].keys())
    target_subcorpus_size[target_corpus] = 0
    failed_attempts = 0
    while target_subcorpus_size[target_corpus] < rand_pick_words_limit:
        i = randint(0, len(doc_ids) - 1)
        doc_id = doc_ids[i]
        if doc_id not in document_picks[target_corpus]:
            doc_words = subcorpus_token_counter[target_corpus][doc_id]
            target_subcorpus_size[target_corpus] += doc_words
            document_picks[target_corpus].add(doc_id)
            failed_attempts = 0
        else:
            failed_attempts += 1
            if failed_attempts >= 20:
                print('(!) 20 unsuccessful random picks in a row: terminating ...')
                break
    #break
print()
print(' Results of the random selection:')
picked_doc_ids = set()
for k in sorted(document_picks.keys()):
    print(' ',k, 'original_docs:',len(document_picks[k]), ' words:',target_subcorpus_size[k] )
    for doc in document_picks[k]:
        doc_str = str(doc)
        assert doc_str not in picked_doc_ids
        picked_doc_ids.add(doc_str)
print()

print(' Picking out docs from the index:')
# Get entries
loaded_entries = get_entries_from_enc_index( enc_index_file, picked_doc_ids )
# Get header
fields = get_fields_from_enc_index( enc_index_file )
loaded_entries = [ENC_INDEX_DELIMITER.join(fields)] + loaded_entries
for i in range(10):
    print(loaded_entries[i])
print('...')
for i in range(10):
    print(loaded_entries[-1*i])

out_fname = 'enc2017_index_random_{}x{}.txt'.format(len(random_pick_target_corpora), rand_pick_words_limit)
c = 2
while os.path.exists( out_fname ):
    out_fname = 'enc2017_index_random_{}x{}_{}.txt'.format(len(random_pick_target_corpora), rand_pick_words_limit, c)
    c += 1
with open(out_fname, 'w', encoding='utf-8') as out_f:
    for entry in loaded_entries:
        out_f.write(entry)
        out_f.write('\n')

