import os
import re
import logging
import pandas as pd

from shutil import move
from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer
import requests
import pause







def preprocess(text, stem=True):
    stemmer = SnowballStemmer("spanish")
    stop_words = stopwords.words("spanish")
    diccionario_stem = {}

    TEXT_CLEANING_RE = "\d+|-|_|°|/|\)|\(|\!|\?|\¡|\¿|\.|\|º,"


    def normalize(s):
        replacements = (
            ("á", "a"),
            ("é", "e"),
            ("í", "i"),
            ("ó", "o"),
            ("ú", "u"),
            ("\n", " "),
            (",", " "),
            (":", " "),
            ("#", ""),
        )
        for a, b in replacements:
            s = s.replace(a, b).replace(a.upper(), b.upper())
        return s

    text = re.sub(TEXT_CLEANING_RE, "", normalize(str(text)).lower()).strip()

    if stem:
        tokens = []
        for token in text.split():
            if token not in stop_words:
                tokens.append(stemmer.stem(token))
                if stemmer.stem(token) in diccionario_stem.keys():
                    if not (token in diccionario_stem[stemmer.stem(token)]):
                        diccionario_stem[stemmer.stem(token)] = diccionario_stem[
                            stemmer.stem(token)
                        ] + [token]
                else:
                    diccionario_stem[stemmer.stem(token)] = [token]

        tokens_unidos = " ".join(tokens)
    else:
        tokens_unidos = text

    return tokens_unidos


def tag_file(radio, clear_tags=True):
    core_dir = "core"
    backend_dir = "data_backend"

    logging.info(f"{radio}: Sentyment Analysis")

    files = [
        f"data/{radio}_transcript/{f}" for f in os.listdir(f"data/{radio}_transcript")
    ]

    ruta_stopwords = r"data/_keywords"

    df_keywords = pd.read_excel(f"{ruta_stopwords}/keywordsStem.xlsx")

    try:
        df_radio_reconocimiento = pd.concat(
            map(
                lambda f: pd.read_csv(f, encoding="utf-8-sig")[["file", "text"]],
                files,
            ),
            ignore_index=True,
        )
        print(df_radio_reconocimiento)
    except:
        return

    keywords = {
        ("agu", "potabl"): "Agua",
        ("agu", "abastec"): "Agua",
        "cuenc": "Agua",
        "miner": "Mineria",
        "agricultur": "Agricultura",
        "contamin": "Contaminación",
        "protest": "Conflicto",
        "conflict": "Conflicto",
        "combat": "Conflicto",
        "disput": "Conflicto",
        ("carreter", "huelg"): "Conflicto",
        ("carreter", "toma"): "Conflicto",
        ("carreter", "paraliz"): "Conflicto",
        ("mesa", "dialog"): "Conflicto",
        "pugn": "Conflicto",
        "colisión": "Accidente",
        "choqu": "Accidente",
        "accid": "Accidente",
        "accident": "Accidente",
        # 'enfrent': 'Conflicto',
        # 'luch':'Conflicto',
        # 'pel':'Conflicto',
    }

    keywords = {**keywords, **(df_keywords.set_index("word")["sector"].to_dict())}

    data_blacklist = eval(requests.get("http://190.223.48.219:8000/conflictividad/blacklist").text)
    blacklist = list(pd.DataFrame(data_blacklist)['word'].values)

    '''
    df_radio_reconocimiento["Sentimiento"] = (
        df_radio_reconocimiento.text.fillna("")
        .apply(str)
        .apply(lambda x: analyzer.predict(x))
    )

    print("Finalizo")

    
    df_radio_reconocimiento["Sentimiento_N"] = df_radio_reconocimiento[
        "Sentimiento"
    ].apply(lambda y: y.output)
    
    '''
    df_radio_reconocimiento["Sentimiento_N"] = 'NEG'

    df_radio_reconocimiento["text_stem"] = df_radio_reconocimiento["text"].apply(
        lambda y: preprocess(y, stem=True)
    )

    df_radio_reconocimiento["tag"] = df_radio_reconocimiento["text_stem"].apply(
        lambda y: ",".join(
            set(
                [keywords[key] for key in keywords.keys() if key in y.split(" ")]
                + [
                    keywords[key]
                    for key in keywords.keys()
                    if type(key) == tuple
                    if all([key_ in y.split(" ") for key_ in key])
                ]
            )
        )
    )

    df_radio_reconocimiento.loc[
        df_radio_reconocimiento.Sentimiento_N != "NEG", "tag"
    ] = "No tag"


    #Limpiando tags del blacklist
    df_blacklist = (df_radio_reconocimiento.text.fillna("")
                    .apply(str)
                    .apply(lambda y: any([word in y for word in blacklist]))
                    )
    df_radio_reconocimiento.loc[df_blacklist, 'tag'] = "No tag"


    df_radio_reconocimiento["datetime"] = pd.to_datetime(
        df_radio_reconocimiento["file"].apply(lambda y: re.findall("\d+", y)[0])
    )
    df_radio_reconocimiento["tag"] = df_radio_reconocimiento["tag"].replace(
        {"": "No tag"}
    )

    if clear_tags:
        df_clear = df_radio_reconocimiento.loc[
            df_radio_reconocimiento["tag"] == "No tag"
        ]
        for index, row in df_clear.iterrows():
            filename = row['file'].split("/")[-1]
            os.remove(f"data/{radio}_read/{filename}")

        df_radio_reconocimiento = df_radio_reconocimiento.loc[
            df_radio_reconocimiento["tag"] != "No tag"
        ]

    df_radio_reconocimiento.to_csv(
        f"data/tmp/{radio}_text_tag.csv", index=False, encoding="utf-8-sig"
    )

    try:
        df_radio_reconocimiento_historico = pd.read_csv(
            f"data/{radio}_text_tag_historico.csv", encoding="utf-8-sig"
        )
        df_radio_reconocimiento_historico = pd.concat(
            [df_radio_reconocimiento_historico, df_radio_reconocimiento]
        )
    except:
        df_radio_reconocimiento_historico = df_radio_reconocimiento

    df_radio_reconocimiento_historico.to_csv(
        f"data/{radio}_text_tag_historico.csv", index=False, encoding="utf-8-sig"
    )

    [*map(lambda f: os.remove(f), files)]

    for index, row in df_radio_reconocimiento.iterrows():
        move(f"data/{radio}_read/{row['file']}", f"{backend_dir}/audios")

