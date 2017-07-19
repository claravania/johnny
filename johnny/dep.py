import os
import six
import glob
import codecs
import json
import re
import numpy as np
from itertools import chain

# TODO : compare what we get from this loader with what we get from CONLL script


def py2repr(f):
    def func(*args, **kwargs):
        x = f(*args, **kwargs)
        if six.PY2:
            return x.encode('utf-8')
        else:
            return x
    return func
    

class Dataset(object):

    def __init__(self, sents, lang=None, name=None):
        self.sents = sents
        self.lang = lang
        self.name = name

    def __getitem__(self, index):
        return self.sents[index]

    def __len__(self):
        return len(self.sents)

    @py2repr
    def __repr__(self):
        return 'Dataset of %s - %s sents' % (self.lang, len(self.sents))

    def __iter__(self):
        for s in self.sents:
            yield s

    def save(self, path):
        with codecs.open(path, 'w', encoding='utf-8') as inp:
            for sent in self:
                s = '%s\n\n' % '\n'.join(str(t) for t in sent)
                inp.write(s)

    @property
    def words(self):
        return tuple(s.words for s in self.sents)

    @property
    def heads(self):
        return tuple(s.heads for s in self.sents)

    @property
    def arctags(self):
        return tuple(s.arctags for s in self.sents)

    @property
    def upostags(self):
        return tuple(s.upostags for s in self.sents)

    @property
    def xpostags(self):
        return tuple(s.xpostags for s in self.sents)

    @property
    def sent_lengths(self):
        return tuple(len(sent) for sent in self.sents)

    @property
    def arc_lengths(self):
        return tuple(chain(*[sent.arc_lengths for sent in self.sents]))

    @property
    def len_stats(self):
        sent_lens = self.sent_lengths
        self.max_sent_len = max(sent_lens)
        self.min_sent_len = min(sent_lens)
        self.avg_sent_len = np.mean(sent_lens)
        self.std_sent_len = np.std(sent_lens)
        return {'max_sent_len': self.max_sent_len,
                'min_sent_len': self.min_sent_len,
                'avg_sent_len': self.avg_sent_len,
                'std_sent_len': self.std_sent_len}

    @property
    def arc_len_stats(self):
        arc_lengths = self.arc_lengths 
        self.max_arc_len = max(arc_lengths)
        self.min_arc_len = min(arc_lengths)
        self.avg_arc_len = np.mean(arc_lengths)
        self.std_arc_len = np.std(arc_lengths)
        return {'max_arc_len': self.max_arc_len,
                'min_arc_len': self.min_arc_len,
                'avg_arc_len': self.avg_arc_len,
                'std_arc_len': self.std_arc_len}

    @property
    def stats(self):
        stats = dict(**self.len_stats)
        stats.update(**self.arc_len_stats)
        stats['num_sents'] = len(self)
        return stats


class Sentence(object):

    def __init__(self, tokens=None):
        # we are using this for dependency parsing
        # we don't care about multiword tokens or
        # repetition of words that won't be reflected in the sentence
        self.tokens = tuple(token for token in tokens if token.head != -1) or tuple()

    def __getitem__(self, index):
        return self.tokens[index]

    def __iter__(self):
        for t in self.tokens:
            yield t

    @py2repr
    def __repr__(self):
        return ' '.join(token.form for token in self.tokens)

    def __len__(self):
        return len(self.tokens)

    def displacify(self, universal_pos=True):
        arcs = [token.displacy_arc() for token in self.tokens
                if token.deprel != 'root' and token.displacy_arc()]
        words = [token.displacy_word(universal_pos=universal_pos)
                 for token in self.tokens if token.displacy_word()]
        return json.dumps(dict(arcs=arcs, words=words))

    def set_heads(self, heads):
        for t, h in zip(self.tokens, heads):
            t.head = h

    def set_labels(self, labels):
        for t, l in zip(self.tokens, labels):
            t.deprel = l

    @property
    def words(self):
        return tuple(t.form for t in self.tokens)

    @property
    def heads(self):
        return tuple(t.head for t in self.tokens)

    @property
    def arctags(self):
        return tuple(t.deprel.split(':')[0] for t in self.tokens)

    @property
    def upostags(self):
        return tuple(t.upostag for t in self.tokens)

    @property
    def xpostags(self):
        return tuple(t.xpostag for t in self.tokens)

    @property
    def arc_lengths(self):
        """Compute how long the arcs are in words"""
        return tuple(abs(head - index) if head != 0 else 1 for index, head in enumerate(self.heads, 1))


@six.python_2_unicode_compatible
class Token(object):

    # this is what each tab delimited attribute is expected to be
    # in the conllu data - exact order
    CONLLU_ATTRS = ['id', 'form', 'lemma', 'upostag', 'xpostag',
                    'feats', 'head', 'deprel', 'deps', 'misc']

    def __init__(self, *args):
        for i, prop in enumerate(args):
            label = Token.CONLLU_ATTRS[i]
            if label in ['head']:
                # some words have _ as head when they are a multitoken representation
                # in that case replace with -1
                setattr(self, Token.CONLLU_ATTRS[i], int(prop) if prop != '_' else -1)
            else:
                setattr(self, Token.CONLLU_ATTRS[i], prop)

    @py2repr
    def __repr__(self):
        return '\t'.join(six.text_type(getattr(self, attr)) for attr in Token.CONLLU_ATTRS)

    def __str__(self):
        return '\t'.join(six.text_type(getattr(self, attr)) for attr in Token.CONLLU_ATTRS)
    
    def displacy_word(self, universal_pos=True):
        """ return a dictionary that matches displacy format """
        tag = self.upostag if universal_pos else self.xpostag
        if '-' not in self.id:
            return dict(tag=tag, text=self.form)
        else:
            return dict()

    def displacy_arc(self):
        """ return a dictionary that matches displacy format """
        # sometimes id, head can be two numbers separated by - : 4-5
        try:
            start_i, end_i = (int(self.id) - 1, int(self.head) - 1)
            start, end, direction =  (start_i, end_i, 'left') if start_i <= end_i else (end_i, start_i, 'right')
            return dict(start=start, end=end, dir=direction, label=self.deprel)
        except Exception:
            return dict()


class UDepLoader(object):
    """Loader for universal dependencies datasets"""

    AVAILABLE_LOADERS = ['CONLL2017', 'CONLL2006']

    def __init__(self, name, **kwargs):
        if name.startswith('CONLL2017'):
            self.loader = CONLL2017Loader(name, **kwargs)
        elif name.startswith('CONLL2006'):
            self.loader = CONLL2006Loader(name, **kwargs)
        else:
            raise ValueError('Unknown loader, name does not start with '
                    'one of %s' % self.AVAILABLE_LOADERS)

    def load_train_dev(self, lang, verbose=False):
        return self.loader.load_train_dev(lang, verbose=verbose)

    @staticmethod
    def get_env_var(name):
        return '%s_FOLDER' % name

    @staticmethod
    def load_conllu_sents(path):
        """ Read in conll file and return a list of sentences """
        CONLLU_COMMENT = '#'
        sents = []
        with codecs.open(path, 'r', encoding='utf-8') as inp:
            tokens = []
            for line in inp:
                line = line.rstrip()
                # we ignore documents for the time being
                if tokens and not line:
                    sents.append(Sentence(tokens))
                    tokens = []
                if line and not line.startswith(CONLLU_COMMENT):
                    cols = line.split('\t')
                    assert(len(cols) == 10)
                    tokens.append(Token(*cols))
        return sents

    @staticmethod
    def load_conllu(path):
        return Dataset(UDepLoader.load_conllu_sents(path))


class CONLL2006Loader(object):

    def __init__(self, name, datafolder=None, train_percentage=0.8):
        super(CONLL2006Loader, self).__init__()
        try:
            env_var = UDepLoader.get_env_var(name)
            self.datafolder = datafolder or os.environ[env_var]
            assert(os.path.isdir(self.datafolder))
        except KeyError:
            raise ValueError('You need to specify the path to the universal dependency '
                'root folder either using the datafolder argument or by '
                'setting the %s environment variable.' % env_var)
        self.train_percentage = train_percentage
        self.name = name
        file_path = os.path.join(self.datafolder, '*', '*', '*', '*', '*', '*.conll')
        file_paths = [f for f in glob.glob(file_path)]
        self.train_map = dict((os.path.basename(f).split('_', 1)[0], f)
                              for f in file_paths
                              if 'train' in f)
        # can't use 'test' since some files don't have test in the name!
        self.test_map = dict((os.path.basename(f).split('_', 1)[0], f)
                              for f in file_paths
                              if '_gs' in f)
        assert(len(self.train_map) == len(self.test_map))

    def __repr__(self):
        return ('<CONLL2006Loader object from folder %s with %d languages>'
                % (self.datafolder, len(self.langs)))

    def load_train_dev(self, lang, verbose=False):
        p = self.train_map.get(lang, None)
        if p:
            sents = UDepLoader.load_conllu_sents(p) 
            num_sents = len(sents)
            split_index = int(num_sents * self.train_percentage)
            train = Dataset(sents[:split_index], lang=lang, name=self.name)
            dev = Dataset(sents[split_index:], lang=lang, name=self.name)
            if verbose:
                print('Loaded %d sentences from %s' % (len(train), p))
                print('Loaded %d sentences from %s' % (len(dev), p))
            return train, dev
        else:
            raise ValueError("Couldn't find a training file for %s"
                             % (lang))

    @property
    def langs(self):
        return list(six.viewkeys(self.train_map))


class CONLL2017Loader(object):
    LANG_FOLDER_REGEX = 'UD_(?P<lang>[A-Za-z\-\_]+)'
    PREFIX = 'UD_'
    TRAIN_SUFFIX = 'ud-train.conllu'
    DEV_SUFFIX = 'ud-dev.conllu'

    def __init__(self, name, datafolder=None):
        super(CONLL2017Loader, self).__init__()
        try:
            env_var = UDepLoader.get_env_var(name)
            self.datafolder = datafolder or os.environ[env_var]
        except KeyError:
            raise ValueError('You need to specify the path to the universal dependency '
                'root folder either using the datafolder argument or by '
                'setting the %s environment variable.' % env_var)
        self.lang_folders = dict()
        self.name = name
        found = False
        for lang_folder in os.listdir(self.datafolder):
            match = re.match(self.LANG_FOLDER_REGEX, lang_folder)
            if match:
                lang = match.groupdict()['lang']
                self.lang_folders[lang] = lang_folder
                found = True
        if not found:
            raise ValueError('No UD language folders '
                             'found in dir %s' % self.datafolder)

    def __repr__(self):
        return ('<CONLL2017Loader object from folder %s with %d languages>'
                % (self.datafolder, len(self.langs)))

    def load_train_dev(self, lang, verbose=False):
        p = os.path.join(self.datafolder, self.lang_folders[lang])
        train_filename = [fn for fn in os.listdir(p) 
                        if fn.endswith(self.TRAIN_SUFFIX)]
        if train_filename:
            train_filename = train_filename[0]
            train_path = os.path.join(p, train_filename)
            train = Dataset(UDepLoader.load_conllu_sents(train_path),
                            lang=lang, name=self.name)
            if verbose:
                print('Loaded %d sentences from %s' % (len(train), train_path))
        else:
            raise ValueError("Couldn't find a %s file for %s"
                             % (lang, self.TRAIN_SUFFIX))
        dev_filename = [fn for fn in os.listdir(p) 
                        if fn.endswith(self.DEV_SUFFIX)]
        if dev_filename:
            dev_filename = dev_filename[0]
            dev_path = os.path.join(p, dev_filename)
            dev = Dataset(UDepLoader.load_conllu_sents(dev_path),
                          lang=lang, name=self.name)
            if verbose:
                print('Loaded %d sentences from %s' % (len(dev), dev_path))
        else:
            raise ValueError("Couldn't find a %s file for %s"
                             % (lang, self.DEV_SUFFIX))
        return train, dev

    @property
    def langs(self):
        return list(six.viewkeys(self.lang_folders))
