#
#  Finds original koondkorpus texts corresponding to the ENC_2017 
#  texts listed in the index file 'enc2017_index_random_5x2000000.txt'.
#  Saves found files as Estnltk 1.6 Text objects in JSON format.
#
#  The scirpt runs without arguments, and it expects that the 
#  the current directory contains unpacked ENC 2017 files:
#
#      estonian_nc17.vert.01
#      estonian_nc17.vert.02
#      estonian_nc17.vert.03
#      ...
#      estonian_nc17.vert.08
#
#  and JSON files from the "Estonian Reference Corpus analysed
#  with EstNLTK ver.1.6_b", unpacked into the directory:
#      
#      koond_raw_json
#
#   You can obtain ENC 2017 files from:
#       https://doi.org/10.15155/3-00-0000-0000-0000-071E7L
#   and the original koondkorpus JSON files from:
#       https://doi.org/10.15155/1-00-0000-0000-0000-00156L
#
#   Optional: 
#      if you want to speed up the current process, then you 
#      can pre-process json files in the folder 'koond_raw_json' 
#      with the script  02a_reduce_koond_json_files.py
#


import os, os.path, json, re
from sys import argv
from collections import defaultdict

from enc2017_extra_utils import create_enc_filename_stub
from enc2017_extra_utils import IndexBasedENC2017DocIterator
from enc2017_extra_utils import fetch_text_category
from enc2017_extra_utils import get_partition_info_from_sys_argv

from estnltk import Text
from estnltk.converters import text_to_json, json_to_text

use_progressbar = True

# input directory containing raw koondkorpus texts:
raw_koond_json_dir = 'koond_raw_json'

# selection index 
enc_index_file = 'enc2017_index_random_5x2000000.txt'

# output directory
output_dir = 'koond_original_texts'

if not os.path.exists(output_dir):
    os.mkdir(output_dir)

partition = get_partition_info_from_sys_argv( argv )


# get list of all file names from raw koondkorpus dir
assert os.path.exists(raw_koond_json_dir)
all_koond_original_files = os.listdir( raw_koond_json_dir )

def package_koond_filelist( filelist ):
    '''Creates a mapping from koond_file_name_without_extension to the full file name.'''
    fnames = defaultdict(list)
    for fname in filelist:
        fname = fname.strip()
        fname_cut_all = re.sub('\.xml_(\d+)\.json$', '', fname)
        assert not fname_cut_all.endswith('.json')
        assert not fname_cut_all.endswith('.xml')
        fname_cut_all = fname_cut_all.lower()
        if fname not in fnames[fname_cut_all]:
            fnames[fname_cut_all].append( fname )
    return fnames

koond_original_files_dict = package_koond_filelist( all_koond_original_files )
print()
print(' Total ',len(all_koond_original_files),' original koondkorpus json files.')
print(' Total ',len(koond_original_files_dict.keys()),' original koondkorpus XML files.')
print()

def _clean_text_snippet( snippet ):
    '''Cleans given text snippet from punctuation and normalizes spaces.'''
    cleaned = []
    for c in snippet:
        if c.isalnum():
            cleaned.append( c )
        elif c.isspace():
            if len(cleaned) == 0 or \
               (len(cleaned) > 0 and not cleaned[-1].isspace()):
               cleaned.append(' ')
    return ''.join( cleaned )


def _most_words_match( snippet_a, snippet_b, reverse=False ):
    '''Tokenizes two text snippets into words and validates iff 80% of words are matching.'''
    a_words = snippet_a.split()
    b_words = snippet_b.split()
    if reverse:
        a_words.reverse()
        b_words.reverse()
    i = 0
    min_len = min(len(a_words), len(b_words))
    while i < min_len:
        a = a_words[i]
        b = b_words[i]
        if a != b:
            break
        i += 1
    # Allow a small % of last words to be missed
    allowed_miss = int(min_len * 0.2)
    return i >= min_len - allowed_miss


def is_approx_match( text1, text2 ):
    '''Checks whether 2 texts match approximately: words of the first and last 100 characters (excluding punct) are matching.
       Returns 2 booleans: ( _both_start_and_end_match , _start_matches ) 
    '''
    text1_start = _clean_text_snippet( text1[:100] )
    text1_end   = _clean_text_snippet( text1[-100:] )
    text2_start = _clean_text_snippet( text2[:100] )
    text2_end   = _clean_text_snippet( text2[-100:] )
    return (_most_words_match( text1_start, text2_start, reverse=False ) and \
            _most_words_match( text1_end, text2_end, reverse=True ), \
            _most_words_match( text1_start, text2_start, reverse=False ))


# Skip non-koondkorpus .vert files
vert_skip_list = ['estonian_nc17.vert.05', 'estonian_nc17.vert.06', 'estonian_nc17.vert.07', \
                  'estonian_nc17.vert.08', 'estonian_nc17.vert.09', 'estonian_nc17.vert.10']
doc_count = 0
iterator = IndexBasedENC2017DocIterator('.', enc_index_file, vert_skip_list=vert_skip_list, \
                                        partition=partition, no_tokenization=True, \
                                        use_progressbar=use_progressbar, verbose=True, take_only_first=-1)
broken_docs = []
missing_file_names = []
text_not_found  = []
koond_exhausted = False
skip_doc_orig_filenames = ['tea_energia']  # skip files not in koondkorpus
for doc in iterator.iterate():
    doc_src = doc.meta['src'].lower() if 'src' in doc.meta else '--'
    if not koond_exhausted and doc_src not in ['nc', '--']:
        print(" >> {} koondkorpus documents processed.".format( doc_count ) )
        print(" >> All koondkorpus documents have been exhausted.")
        koond_exhausted = True
    if koond_exhausted:
        continue
    fname_stub = create_enc_filename_stub( doc )
    outfname = fname_stub+'.json'
    doc_orig_filename_ma = None
    if "filename" in doc.meta:
        doc_orig_filename_ma = doc.meta['filename']
    else:
        print('(!) Original file name missing from the document: {}. Skipping.'.format(fname_stub))
        broken_docs.append( fname_stub )
        continue
    doc_orig_filename = re.sub( '.ma$', '', doc_orig_filename_ma )
    # Find corresponding file(s) from "all_koond_original_files"
    if doc_orig_filename.lower().startswith('tea_agraar'):
        # ENC_2017 name:     'tea_agraar'
        # koondkorpus name:  'agraar'
        doc_orig_filename = doc_orig_filename[4:]
    if doc_orig_filename.lower() in skip_doc_orig_filenames:
        print('(!) Skipping {}.'.format(fname_stub))
        continue
    if doc_orig_filename.lower() in koond_original_files_dict:
        koond_files = koond_original_files_dict[ doc_orig_filename.lower() ]
        #
        # Problems:
        #
        #    1) One koondkorpus file may be spilt into several ENC_2017 files;
        #       For instance, 'aja_EPL_2004_04_20.xml_0.json' is split into
        #                      3 ENC2017 files:  
        #                         'nc_10759_661035', 
        #                         'nc_10759_661036',
        #                         'nc_10759_661037'
        #       Solution: take whole content of 'aja_EPL_2004_04_20.xml_0.json' as 
        #                 the content of 'nc_10759_661035' and hope that it also 
        #                 covers the remaining files;
        #       
        #    2) NC part of ENC_2017 contains files not in the original koondkorpus:
        #       'tea_energia' ==> 'Energiaõpik'
        #       Solution: skip 'tea_energia' altogether ...
        #
        #    3) Some of the articles mismatch because the koondkorpus article 
        #       accidentially has the paragraph filled with author's name, while 
        #       ENC has correctly moved author's name to the metadata.
        #       Examples:
        #         'nc_255_28029.json' ==>  'aja_EPL_2002_04_29.xml_45.json'
        #         'nc_10148_624217'   ==>  'aja_pm_1996_11_13.xml_50.json'
        #         'nc_10148_624218'   ==>  'aja_pm_1996_11_13.xml_51.json'
        #         'nc_10175_625295'   ==>  'aja_pm_1996_08_19.xml_12.json'
        #         ...
        #         'nc_17215_741897'   ==> 'tea_EMS_2001.tasak.xml_5.json'
        #
        #       Solution: remove the first paragraph from koondkorpus article's
        #                 text and then try to match again ...
        #
        in_koond_texts = []
        title_match    = []
        for kid, k_file in enumerate( koond_files ):
            k_file_text = json_to_text(file=os.path.join(raw_koond_json_dir, k_file) )
            # First, check for title match
            k_file_title = k_file_text.meta.get('title', '=====')
            doc_title = doc.meta.get('article', '-----')
            has_title_match = False
            title_full_match, title_start_match = is_approx_match( doc_title, k_file_title )
            if title_full_match:
                has_title_match = True
                title_match.append( (k_file, k_file_text) )
            # Second, check for textual content match
            full_match, start_match = is_approx_match( doc.text, k_file_text.text )
            if full_match:
                k_file_text.meta['_to_enc2017_match_type'] = 'start_&_end'
                in_koond_texts.append( (k_file, k_file_text) )
            elif start_match:
                # Only start matches: re-check if the following 300 chars also match
                text1_start = _clean_text_snippet( doc.text[:300] )
                text2_start = _clean_text_snippet( k_file_text.text[:300] )
                if _most_words_match( text1_start, text2_start, reverse=False ):
                    print('(!) Only start of the {} matches. Including all.'.format(fname_stub))
                    k_file_text.meta['_to_enc2017_match_type'] = 'only_start'
                    in_koond_texts.append( (k_file, k_file_text) )
            # Third, try to match textual content again after the first paragraph of koondkorpus 
            #        document has been removed ... (there might be a superfluous line)
            if not full_match and not start_match:
                k_file_text_mod = re.sub('^[^\n]+\n\n', '', k_file_text.text)
                if len(k_file_text_mod) > 0:
                    full_match, start_match = is_approx_match( doc.text, k_file_text_mod )
                    if full_match:
                        k_file_text.meta['_to_enc2017_match_type'] = 'start_partly_&_end'
                        in_koond_texts.append( (k_file, k_file_text) )
                    elif start_match:
                        # Only start matches: re-check if the following 300 chars also match
                        text1_start = _clean_text_snippet( doc.text[:300] )
                        text2_start = _clean_text_snippet( k_file_text_mod[:300] )
                        if _most_words_match( text1_start, text2_start, reverse=False ):
                            print('(!) Only start of the {} matches. Including all.'.format(fname_stub))
                            k_file_text.meta['_to_enc2017_match_type'] = 'only_start_partly'
                            in_koond_texts.append( (k_file, k_file_text) )
        if in_koond_texts:
            # Ok, there might be more than one file, so we try to merge ...
            new_text = []
            new_text_meta = defaultdict(set)
            for (k_file, k_file_text) in in_koond_texts:
                new_text.append( k_file_text.text )
                for key in k_file_text.meta.keys():
                    new_key = ('_koond_'+key).replace('__','_')
                    new_text_meta[new_key].add( k_file_text.meta[key] )
                new_text_meta['_koond_json_file'] = set([k_file])
            # Create a new text by merging the original texts
            new_text_obj = Text( '\n\n'.join(new_text) )
            for meta_key in new_text_meta.keys():
                new_text_obj.meta[ meta_key ] = '||'.join(list(new_text_meta[meta_key]))
            new_text_obj.meta[ '_koond_original_texts_count' ] = len( new_text )
            # Carry over metadata from the corresponding ENC file
            for meta_key in doc.meta.keys():
                new_text_obj.meta[ meta_key ] = doc.meta[ meta_key ]
            # Write out Text object
            fpath = os.path.join( output_dir, outfname )
            text_to_json( new_text_obj, file=fpath )
        else:
            if not title_match:
                # Only if we do not even match a title
                print('(!) {} cannot be matched by title nor by textual content. Skipping.'.format(fname_stub))
                text_not_found.append(fname_stub) 
    else:
        print('(!) Original file name {} not in the list of koondkorpus files. Skipping.'.format(doc_orig_filename))
        broken_docs.append( fname_stub )
        missing_file_names.append( doc_orig_filename )
        continue

    doc_count += 1
    #if doc_count > 1:
    #    break
print()
print()
if text_not_found:
    print(' Original text not found for documents ({}): {}'.format(len(text_not_found), text_not_found))
if broken_docs:
    print(' Broken documents ({}): {}'.format(len(broken_docs), broken_docs))
if missing_file_names:
    print(' Missing .ma files ({}): {}'.format(len(missing_file_names), missing_file_names))
print(' Total koondkorpus documents processed: ',doc_count)
print('')
