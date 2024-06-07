import re
import nltk
import spacy
import torch
import pickle
import numpy as np

from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer

from .models import SentimentRNN
from . import constants

nltk.download('punkt')
nltk.download('wordnet')
nltk.download('stopwords')

def get_list_stopword():
    stopwords = []
    try:
        with open('sa_app/static/models/stopwords.txt', 'r') as file:
            for line in file:
                stopwords.append(line.strip())
    except FileNotFoundError as e:
        raise Exception(e)
    
    return stopwords

def replace_contractions(sentence, to_replace):
    pattern = re.compile(r'\b(' + '|'.join(to_replace.keys()) + r')\b')
    
    return pattern.sub(lambda x: to_replace[x.group()], sentence)

def decontracted(phrase):
    phrase = re.sub(r"\'t", " not", phrase)
    phrase = re.sub(r"\'re", " are", phrase)
    phrase = re.sub(r"\'s", " is", phrase)
    phrase = re.sub(r"\'d", " would", phrase)
    phrase = re.sub(r"\'ll", " will", phrase)
    phrase = re.sub(r"\'ve", " have", phrase)
    phrase = re.sub(r"\'m", " am", phrase)

    return phrase

def clean_text(text):
    lemmatizer = WordNetLemmatizer()
    nlp = spacy.load("en_core_web_sm")
    stopwords = get_list_stopword()

    text = text.lower()
    text = replace_contractions(text, constants.CONTRACTION_REPLACEMENTS)
    text = decontracted(text)
    text = re.sub('[^a-zA-Z]', ' ', text)
    text = re.sub(r'\s+', ' ', text)

    words = word_tokenize(text)

    filtered_words = [word for word in words if not word in stopwords  and len(word) > 1]
    lemmas = []
    for word in filtered_words:
        lemma = lemmatizer.lemmatize(word, pos='v')
        lemmas.append(lemma)
    sentence = ' '.join(lemmas)
    doc = nlp(sentence)
    lemmas = [token.lemma_ for token in doc]

    return ' '.join(lemmas)

def get_vocab():
    try:
        with open('sa_app/static/models/tokenizer.pkl', 'rb') as f:
            vocab = pickle.load(f)
    except FileNotFoundError as e:
        raise Exception(e)
    
    return vocab

def phrase_to_ints(text):
    vocab = get_vocab()
    words = [word for word in text.split()]
    ints = [vocab.get(word, vocab['<UNK>']) for word in words]
    return ints

def pad_sequences(phrase_to_int, seq_length):
    if not isinstance(phrase_to_int[0], list):
        phrase_to_int = [phrase_to_int]
    pad_sequences = np.zeros((len(phrase_to_int), seq_length), dtype=int)
    for idx, row in enumerate(phrase_to_int):
        pad_sequences[idx, :len(row)] = np.array(row)[:seq_length]
        
    return pad_sequences

def get_model():
    vocab = get_vocab()
    n_vocab = len(vocab) + 1

    model_fname = 'sa_app/static/models/trained_model.pth'
    try:
        model = SentimentRNN(n_vocab, constants.N_OUTPUT, constants.N_EMBED, constants.N_HIDDEN, constants.N_LAYERS, constants.DEVICE)
        model.load_state_dict(torch.load(model_fname, map_location=torch.device(constants.DEVICE)))
    except IndexError:
        raise Exception('File not found')
    except Exception as e:
        raise Exception(e)

    model.to(constants.DEVICE)
    model.eval()

    return model

def predict(sentence):
    model = get_model()

    words = clean_text(sentence)
    if len(words) <= 0:
        return None, None
    text_ints = phrase_to_ints(words)
    padded_text = pad_sequences(text_ints, constants.SEQ_LENGTH)
    
    text_tensor = torch.from_numpy(padded_text)
    text_tensor = text_tensor.to(constants.DEVICE)
    
    model.eval()
    
    batch_size = text_tensor.size(0)
    h = model.init_hidden(batch_size)
    
    output, _ = model(text_tensor, h)
    predicted = output.flatten().cpu().detach().numpy()

    output = ["{:.2f}".format(num * 100) for num in predicted]
    pred = np.argmax(predicted)
    
    return output, pred


if __name__ == 'main':
    sen = 'This movie is really great'
    output, pred = predict(sen)
    print(output)
    print(pred)