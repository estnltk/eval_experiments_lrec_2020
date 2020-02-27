#
#   Additional utilities needed for processing ENC2017 corpus
#

import re, os

from estnltk.corpus_processing.parse_enc2017 import parse_tag_attributes

#================================================
#   Pattern for ENC2017 file names
#================================================

enc2017fname_pat = re.compile('^estonian_nc17\.vert\.\d+$', re.IGNORECASE)

#================================================
#   Delimiter used in the index csv file
#================================================

ENC_INDEX_DELIMITER = '||'

#================================================
#   Load etTenTen13 texttypes
#================================================

def load_ettenten_texttypes( ettenten_texttypes_file ):
    ''' Loads ettenten13 texttypes and original doc_id-s from a file that lists XML doc headers. '''
    url_to_info = {}
    with open( ettenten_texttypes_file, 'r', encoding='utf-8' ) as f:
        for line in f:
            line=line.strip()
            if line.startswith('<doc'):
                attribs = parse_tag_attributes( line )
                assert 'id' in attribs.keys()
                assert 'url' in attribs.keys()
                assert 'texttype' in attribs.keys()
                if attribs['url'] in url_to_info:
                    print('(!) Warning: Duplicate url: {!r}'.format(attribs['url']))
                    print('    Overwriting previous info {!r} with {!r}'.format(url_to_info[attribs['url']], ( attribs['id'], attribs['texttype'] )))
                url_to_info[attribs['url']] = ( attribs['id'], attribs['texttype'] )
    return url_to_info

#================================================
#   Read from enc2017 index
#================================================

def read_from_enc_index( enc_index_fnm, convert_numbers=True ):
    ''' Reads enc2017 document index file (a csv-like file), and yields index entries.'''
    delimiter = ENC_INDEX_DELIMITER
    fields = []
    with open(enc_index_fnm, 'r', encoding='utf-8') as csv_file:
        for line in csv_file:
            line = line.strip()
            if len(line) > 0:
                if delimiter in line:
                    chunks = line.split(delimiter)
                elif delimiter[0] in line:
                    chunks = line.split('|')
                if len(fields) == 0:
                    fields = chunks
                else:
                    assert len(fields) == len(chunks)
                    result = { f:chunks[fid] for fid, f in enumerate(fields) }
                    if convert_numbers:
                        for k in result.keys():
                            if result[k].isnumeric():
                                result[k] = int(result[k])
                            elif result[k] == '|1526':  # a quick fix
                                result[k] = int(result[k][1:])
                            elif re.match('\|+\d+$', result[k]):
                                raise Exception('(!) Unexpected numeric value for {!r} in: {!r}'.format(k, result))
                    yield result


def get_entries_from_enc_index( enc_index_fnm, doc_ids ):
    ''' Gets entries with specific doc_ids from the given enc2017 documents index file. '''
    delimiter = ENC_INDEX_DELIMITER
    fields = []
    returnables = []
    with open(enc_index_fnm, 'r', encoding='utf-8') as csv_file:
        for line in csv_file:
            line = line.strip()
            if len(line) > 0:
                if delimiter in line:
                    chunks = line.split(delimiter)
                elif delimiter[0] in line:
                    chunks = line.split('|')
                if len(fields) == 0:
                    fields = chunks
                else:
                    assert len(fields) == len(chunks)
                    result = { f:chunks[fid] for fid, f in enumerate(fields) }
                    if result['doc_id'] in doc_ids:
                        returnables.append( line )
    return returnables


def get_fields_from_enc_index( enc_index_fnm ):
    ''' Gets the field names (the first line) from the given enc2017 documents index file.'''
    delimiter = ENC_INDEX_DELIMITER
    fields = []
    with open(enc_index_fnm, 'r', encoding='utf-8') as csv_file:
        for line in csv_file:
            line = line.strip()
            if len(line) > 0:
                if delimiter in line:
                    chunks = line.split(delimiter)
                elif delimiter[0] in line:
                    chunks = line.split('|')
                if len(fields) == 0:
                    fields = chunks
                else:
                    break
    return fields


#================================================
#   Get koond subcorpus_name
#================================================

def get_koond_subcorpus_name(src_file_or_url):
    '''Attempts to derive Koondkorpus' subcorpus name from the given source filename or url.
       Returns None, if the given name (or url) does not look like coming from the Koondkorpus.
    '''
    assert isinstance(src_file_or_url, str)
    if src_file_or_url.startswith( ('https://', 'http://', 'www.') ):
        return None
    if src_file_or_url.endswith('.ma'):
        f_prefix = re.sub('^([A-Za-z_\-]+)(\.|[0-9]+).*(\.ma)$', '\\1', src_file_or_url)
        if f_prefix.endswith('_'):
            f_prefix = f_prefix[:-1]
        if f_prefix.startswith('ilu_'):
            f_prefix = 'ilu'
        if f_prefix.startswith('tea_') and \
           not re.match('tea_(AA|agraar|dr|eesti_arst)$',f_prefix):
            f_prefix = 'tea'
        return f_prefix
    return None

#================================================
#   Excluding already used documents
#================================================

def load_excludable_docs_list( exlude_list_file, remove_file_ext=True ):
    ''' Loads a list of document names that should be excluded either from Koondkorpus or from etTenTen13. '''
    excludables = []
    with open(exlude_list_file, 'r', encoding='utf-8') as exc_file:
        for line in exc_file:
            line = line.strip()
            if remove_file_ext:
                m = re.match('^(.+)(\.[^.]+)$', line)
                if m:
                    line = m.group(1)
            excludables.append(line)
    return excludables

def fix_koond_excludable_docs_list( excludable_koond_docs ):
    ''' Makes some Koondkorpus specific fixes to file names to assure name matching. '''
    # Remove JSON files, get only XML files (assuming JSON files are subparts of XML files)
    excludable_koond_docs = [ f for f in excludable_koond_docs if not f.endswith('.json') and '.xml_' not in f ]
    # Fix horisont
    excludable_koond_docs = [ f if not f == 'horisont_2000.xml' else 'aja_horisont_2000.xml' for f in excludable_koond_docs ]
    excludable_koond_docs = [ f if not f == 'horisont_2000' else 'aja_horisont_2000' for f in excludable_koond_docs ]
    return excludable_koond_docs

#
#  According to the current index file, two excludable documents were not found:
#    * 'ilu_ruben_1988.tasak' from 'NC' -- 
#              probably because it was accidentially left out from the 'NC' subcorpus of ENC_2017;
#    * 'http://paanikahaire.ee/?Paanikah%E4ire' from 'web13' -- 
#              probably because our ENC_2017's web13 portion was incomplete (due to drive size 
#              limitations), and did not include document from that specific url;
#

#================================================
#   Create enc_2017 file name stub
#================================================

from estnltk import Text

def create_enc_filename_stub( doc ):
    ''' Creates a unique file name based on metadata of the given document. 
        Returns the file name (without extension).
    '''
    assert isinstance(doc, Text), '(!) Input should be EstNLTK\'s Text object. '
    assert 'src' in doc.meta,     '(!) No "src" in Text\'s meta. Are you sure this is an ENC 2017 document?'
    assert 'id' in doc.meta,      '(!) No "id" in Text\'s meta. Are you sure this is an ENC 2017 document?'
    outfname_lst = [doc.meta['src'].lower()]
    outfname_lst.append('_')
    outfname_lst.append(doc.meta['id'])
    outfname_lst.append('_')
    if 'subdoc_id' in doc.meta:
        outfname_lst.append(doc.meta['subdoc_id'])
    else:
        outfname_lst.append('x')
    return ''.join( outfname_lst )


#================================================
#   Fetch text type / category
#================================================

def fetch_text_category( doc ):
    ''' Returns text category: in case of national corpus, returns "texttype" from meta, 
        otherwise returns text's source. '''
    assert isinstance(doc, Text), '(!) Input should be EstNLTK\'s Text object. '
    assert 'src' in doc.meta,     '(!) No "src" in Text\'s meta. Are you sure this is an ENC 2017 document?'
    if doc.meta['src'].lower() == 'nc':
        if "texttype" in doc.meta:
            return 'nc_'+doc.meta["texttype"]
        else:
            return 'nc_unknown'
    else:
        return doc.meta['src']


#================================================
#   Iterate ENC_2017 files based on the          
#        index of selected docs                  
#================================================

from estnltk.corpus_processing.parse_enc2017 import parse_enc2017_file_iterator

from datetime import datetime

class IndexBasedENC2017DocIterator:
    """ Iterates over ENC 2017 corpus files based on the given index of selected documents.
        Yields documents one by one.
    """ 
    
    def __init__(self, enc_corpus_dir,\
                       enc_index_file,\
                       use_progressbar=False,\
                       verbose=True,\
                       no_tokenization=False,\
                       partition=None,\
                       vert_skip_list=[], \
                       take_only_first=-1 ):
        self.enc_corpus_dir = enc_corpus_dir
        # Collect analysable corpus files
        self.enc_corpus_files = []
        for fname in sorted(os.listdir(self.enc_corpus_dir)):
            if enc2017fname_pat.match( fname ):
                if fname not in vert_skip_list:
                    self.enc_corpus_files.append( fname )
        self.enc_index_file = enc_index_file
        self.use_progressbar = use_progressbar
        self.verbose = verbose
        self.take_only_first = take_only_first
        if self.take_only_first > 0:
            self.use_progressbar = False
        if partition is not None:
            # validate partition info
            assert isinstance(partition, tuple) and \
                   len(partition)==2 and \
                   isinstance(partition[0], int) and \
                   isinstance(partition[1], int) and \
                   0 < partition[0] and \
                   partition[0] <= partition[1], \
                 '(!) partition should be a tuple (k, n), where n is the number sections into which the enc index should be partitioned, and k is the partition that should be selected by the current iterator (so that 1 <= k <= n).'
        self.partition = partition
        # Should we load tokenization from ENC files?
        self.no_tokenization = no_tokenization
        # stats
        self.enc_file_count = 0
        self.doc_count = 0


    @staticmethod
    def fetch_index_entries_of_enc_file( index_file, enc_file ):
        ''' Fetches all document id-s from the given index file that correspond to the given enc_file. '''
        doc_ids = []
        for r in read_from_enc_index(index_file, convert_numbers=False):
            if r['file'].lower() == enc_file.lower():
                doc_ids.append( r['doc_id'] )
        return doc_ids


    def partition_doc_ids( self, doc_ids ):
       ''' Divides doc_ids into n groups and returns k-th group (if self.partition is not None). '''
       if self.partition is not None:
            n = self.partition[1]
            k = self.partition[0]
            # *** Create placeholders for groups
            groups = []
            for i in range(n):
                groups.append([])
            # *** Split docs into groups
            j = 0
            for doc_id in doc_ids:
                groups[j].append( doc_id )
                j += 1
                if j >= n:
                    j = 0
            # *** check
            assert sum( [len(g) for g in groups] ) == len( doc_ids )
            # *** use a part instead of the whole
            doc_ids = groups[k-1]
       return doc_ids


    def iterate( self ):
        ''' Iterates over ENC 2017 corpus files and yields documents based on the given index of selected documents.'''
        startTime = datetime.now()
        for fname in self.enc_corpus_files:
            if self.verbose:
                print()
                print('Processing ',fname,'...')
            # Get index entries for given file
            target_docs_ids = IndexBasedENC2017DocIterator.fetch_index_entries_of_enc_file( self.enc_index_file, fname )
            target_docs_ids = self.partition_doc_ids( target_docs_ids )
            if self.verbose:
                partition_info = ''
                if self.partition is not None:
                    partition_info = '(partition {} / {})'.format(self.partition[0],self.partition[1])
                print('',len(target_docs_ids),'documents will be processed {} ...'.format(partition_info))
            doc_count_sub = 0
            if len(target_docs_ids) > 0:
                for text in parse_enc2017_file_iterator( fname, 
                                                         focus_doc_ids = set(target_docs_ids),
                                                         line_progressbar='ascii' if (self.use_progressbar and self.verbose) else None, 
                                                         tokenization='preserve_partially' if not self.no_tokenization else 'none' ):
                    if self.take_only_first > 0 and doc_count_sub >= self.take_only_first:
                        break
                    self.doc_count += 1
                    doc_count_sub += 1
                    yield text
            self.enc_file_count += 1
        if self.verbose:
            print()
            if self.partition is not None:
                print('Partition {} / {} processing complete.'.format(self.partition[0],self.partition[1]))
            print('ENC2017 files processed: ', self.enc_file_count)
            print('Docs processed:          ', self.doc_count)
            print('Total processing time:   {}'.format( datetime.now()-startTime ) )
        
        
#================================================
#  Parse partition info from command line args
#================================================

def get_partition_info_from_sys_argv( argv, verbose=True ):
    # Attempt to load partition info
    partition=None
    if len(argv) >= 2:
        part_str = argv[1]
        m = re.match('^(\d+)\s*[,/]\s*(\d+)$', part_str)
        if m:
            k = int( m.group(1) )
            n = int( m.group(2) )
            partition=(k,n)
        else:
            print('(!) Partition info should be in the format k,n where k and n are integers so that 1 <= k <= n')
    if verbose and partition is not None:
        print('>> Using index partition:',partition)
    return partition



#================================================
#   Iterate EstNLTK json files in a directory    
#================================================

from estnltk.converters import json_to_text
from tqdm import tqdm

class EstnltkJsonDocIterator:
    """ Iterates over a directory containing estnltk json files.
        Allows to filter file names by prefixes and suffixes.
        Yields documents one by one.
    """ 
    
    def __init__(self, corpus_dir,\
                       use_progressbar=False,\
                       verbose=True,\
                       partition=None,\
                       prefixes=[],\
                       suffixes=['.json'],\
                       skip_list=[], \
                       take_only_first=-1 ):
        self.corpus_dir = corpus_dir
        # Collect analysable corpus files
        self.enc_corpus_files = []
        self.use_progressbar = use_progressbar
        self.verbose = verbose
        self.take_only_first = take_only_first
        if self.take_only_first > 0:
            self.use_progressbar = False
        self.prefixes = prefixes
        self.suffixes = suffixes
        self.skip_list = skip_list
        if partition is not None:
            # validate partition info
            assert isinstance(partition, tuple) and \
                   len(partition)==2 and \
                   isinstance(partition[0], int) and \
                   isinstance(partition[1], int) and \
                   0 < partition[0] and \
                   partition[0] <= partition[1], \
                 '(!) partition should be a tuple (k, n), where n is the number sections into which the enc index should be partitioned, and k is the partition that should be selected by the current iterator (so that 1 <= k <= n).'
        self.partition = partition
        # stats
        self.json_file_count = 0


    def partition_doc_names( self, doc_names ):
       ''' Divides doc_names into n groups and returns k-th group (if self.partition is not None). '''
       if self.partition is not None:
            n = self.partition[1]
            k = self.partition[0]
            # *** Create placeholders for groups
            groups = []
            for i in range(n):
                groups.append([])
            # *** Split docs into groups
            j = 0
            for doc in doc_names:
                groups[j].append( doc )
                j += 1
                if j >= n:
                    j = 0
            # *** check
            assert sum( [len(g) for g in groups] ) == len( doc_names )
            # *** use a part instead of the whole
            doc_names = groups[k-1]
       return doc_names


    def iterate( self ):
        ''' Iterates over estnltk json files and yields documents based on the given selection criteria (prefix/suffix selections and partitions).'''
        startTime = datetime.now()
        # Collect input files
        files = os.listdir(self.corpus_dir)
        filtered_files = []
        for f in sorted(files):
            if f in self.skip_list:
                continue
            start_matches  = [f.startswith(s) for s in self.prefixes]
            ending_matches = [f.endswith(s) for s in self.suffixes]
            if (len(start_matches) == 0 or any(start_matches)) and (any(ending_matches) or len(ending_matches) == 0):
                filtered_files.append( f )
        filtered_files = self.partition_doc_names( filtered_files )
        if self.verbose:
            partition_info = ''
            if self.partition is not None:
                partition_info = '(partition {} / {})'.format(self.partition[0],self.partition[1])
            print('',len(filtered_files),'documents will be processed {} in {!r}...'.format(partition_info, self.corpus_dir))
        # Iterate over inputs
        iterator = tqdm(filtered_files, ascii=True)
        if not self.use_progressbar:
            iterator = filtered_files
        for fname in iterator:
            if self.take_only_first > 0 and self.json_file_count >= self.take_only_first:
                break
            text_obj = json_to_text( file=os.path.join(self.corpus_dir,fname) )
            self.json_file_count += 1
            yield text_obj
        if self.verbose:
            print()
            if self.partition is not None:
                print('Partition {} / {} processing complete.'.format(self.partition[0],self.partition[1]))
            print('JSON files processed:    ', self.json_file_count)
            print('Total processing time:   {}'.format( datetime.now()-startTime ) )


    def get_input_files( self ):
        '''Returns the sorted list of input files based on the given selection criteria (prefix/suffix selections and partitions).
           [ for testing purposes ]
        '''
        # Collect input files
        files = os.listdir(self.corpus_dir)
        filtered_files = []
        for f in sorted(files):
            if f in self.skip_list:
                continue
            start_matches  = [f.startswith(s) for s in self.prefixes]
            ending_matches = [f.endswith(s) for s in self.suffixes]
            if (len(start_matches) == 0 or any(start_matches)) and (any(ending_matches) or len(ending_matches) == 0):
                filtered_files.append( f )
        return self.partition_doc_names( filtered_files )

