"""Makes the database from the plaintext dictionary."""

from typing import List, Tuple, Iterable, Dict, Set, Optional
from re import sub as rsub
import more_itertools as mit
import multiprocessing as mp
from sqlalchemy import create_engine, Table, Column, String, Integer, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()
engine = create_engine('sqlite:///abcd.sqlite', echo=False)

consonants = 'бвгджзклмнрпстфхцчшщ'
consonants_j = consonants + 'й'
consonants_for_e = 'бвгдзклмнрпстфх'
vowels = 'аэиоу'
pairs = {'б': 'п', 'в': 'ф', 'г': 'к', 'д': 'т', 'ж': 'ш', 'з': 'с'}
pairs_r = {'п': 'б', 'ф': 'в', 'к': 'г', 'т': 'д', 'ш': 'ж', 'с': 'з'}
unpaired = "чцщх"
transform = {}
transform2 = {}

for x in pairs:
    for y in pairs.values():
        transform[x + y] = pairs[x] + y
        if x != 'в':
            transform[y + x] = pairs_r[y] + x
    for y in unpaired:
        transform[x + y] = pairs[x] + y

for c in consonants_j:
    transform2[c + c] = c

def phonetize(word: str) -> str:
    #word = word.lower().strip().replace("'", "_")

    if word not in ["мно_го", "немно_го", "премно_го", "намно_го", "ненамно_го",
        "стро_го", "нестро_го", "на_строго", "убо_го"]:
        word = rsub("о(_?)го$", "о\\1во", word)

    word = rsub("(чу_?)в(ств)", "\\1\\2", word)
    word = rsub("(здра_?)в(ств)", "\\1\\2", word)

    word = word.replace("действи", "дистви")
    word = word.replace("рейту", "риту")
    word = word.replace("сейча", "сича")

    word = word.replace("лнц", "нц").replace("стн", "сн").replace("здн", "зн").replace("стк", "ск").replace("здк", "ск")

    word = rsub(f'([^{consonants}])я', '\\1йа', word)
    word = rsub(f'([^{consonants}])ю', '\\1йу', word)
    word = rsub(f'([^{consonants}])ё', '\\1йо', word)
    word = word.replace('ьо', 'ьйо')
    word = rsub(f'([^{consonants}])е', '\\1йэ', word)
    word = word.replace('я', 'ьа')
    word = word.replace('ю', 'ьу')
    word = rsub(f'([{consonants_for_e}])ё', '\\1ьо', word)
    word = word.replace("ё", "о")
    word = rsub(f'([{consonants_for_e}])е', '\\1ьэ', word)
    word = word.replace('е', 'э')
    word = rsub('([аэиыоу])и', '\\1йи', word)
    word = rsub(f'([{consonants_for_e}])и', '\\1ьи', word)
    word = word.replace('ы', 'и')

    word = rsub('о([^_`])', 'а\\1', word)
    word = rsub('э([^_])', 'и\\1', word)
    word = rsub('о$', 'а', word)
    word = rsub('э$', 'и', word)
    word = rsub('([чшщжй])а', '\\1и', word)

    for s1, s2 in transform.items():
        word = word.replace(s1, s2)

    for s1, s2 in transform2.items():
        word = word.replace(s1, s2)

    word = word.replace('тс', 'ц')
    word = rsub('[сш]ч', 'щ', word)

    for c1, c2 in pairs.items():
        word = rsub(f'{c1}$', c2, word)

    return word


class TransWord(Base): # type: ignore
    __tablename__ = 'main'
    word = Column(String)
    gram = Column(String)
    trans = Column(String)
    word_id = Column(Integer, primary_key=True)
    starred = Column(Boolean)

    def __init__(self, word: str, gram: str, trans: str, word_id: int, starred: bool) -> None:
        self.word = word
        self.gram = gram
        self.trans = trans
        self.word_id = word_id
        self.starred = starred

    def __repr__(self) -> str:
        star = '*' if self.starred else ''
        return f"#{self.word_id} {star}{self.word}: {self.trans} [{self.gram.trim()}]"


# Checking IDs for uniqueness:
# (is not currently used!)
ids: Dict[int, str] = dict()
def ensure_id(raw_id: str, line: str) -> int:
    if not raw_id.isdecimal():
        print(f"[id] not decimal: {raw_id}. Line: {line}")
    id_ = int(raw_id, base=10)
    if id_ in ids:
        print(f"[id] not unique. Line: {line}")
        print(f"[id] original id line: {ids[id_]}")
    ids[id_] = line
    return id_

def lineToWord(line: str) -> Optional[TransWord]:
    parts = line.split('|')
    if len(parts) >= 4:
        raw_word = parts[0].strip().lower()
        starred = raw_word.startswith('*')
        word = raw_word[1:] if starred else raw_word
        gram = f" {parts[1].strip().lower()} "
        raw_trans = parts[2].strip().lower().replace("'", "_")
        trans = phonetize(raw_trans)
        word_id = int(parts[-1].strip())
        return TransWord(word, gram, trans, word_id, starred)
    else:
        return None


if __name__ == "__main__":
    started = datetime.now()
    print(f"Started: {started}")

    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    print('Clearing the db table...')
    session.query(TransWord).delete()

    print('Populating the db table from the dictionary file:')
    with open('hagen-morph.txt', encoding='windows-1251') as file:
        with mp.Pool() as pool:
            optWords = pool.imap_unordered(lineToWord, file, chunksize=1_000)
            words = (word for word in optWords if word is not None)
            chunks = mit.chunked(words, 100_000)
            for index, chunk in enumerate(chunks):
                print(f' chunk {index} ({chunk[0].word} — {chunk[-1].word})...')
                session.bulk_save_objects(chunk)
    
    print('Committing data into the db...')
    session.commit()
    
    finished = datetime.now()
    print(f"Finished: {finished}")
    print(f"Elapsed: {finished - started}")
