import json

from bs4 import BeautifulSoup

from ..dictionaries import DictBase
from ..exceptions import NotFoundError
from ..models import Record


class YahooDict(DictBase):

    API = 'https://tw.dictionary.yahoo.com/dictionary?p={word}'

    @property
    def provider(self):
        return 'yahoo'

    def show(self, record: Record):
        content = json.loads(record.content)
        # print word
        self.color.print(content['word'], 'yellow')
        # print pronounce
        for k, v in content.get('pronounce', []):
            self.color.print(k, end='')
            self.color.print(v, 'lwhite', end=' ')
        print()
        # print explain
        explain = content.get('explain')
        for speech in explain:
            self.color.print(speech[0], 'lred')
            for meaning in speech[1:]:
                self.color.print(
                    '{text}'.format(text=meaning[0]),
                    'org',
                    indent=2
                )
                for (english, chinese) in meaning[1:]:
                    if english:
                        print(' ' * 4, end='')
                        for i, s in enumerate(english.split('*')):
                            self.color.print(
                                s,
                                'lindigo' if i == 1 else 'indigo',
                                end=''
                            )
                        print()

                    if chinese:
                        self.color.print(chinese, 'green', indent=4)
        print()

    def _get_prompt(self) -> str:
        return '[zDict]: '

    def _get_url(self, word) -> str:
        return self.API.format(word=word)

    def query(self, word: str, verbose=False):
        '''
        :param word: look up word
        :param verbose: verbose mode flag
        '''

        keyword = word.lower()
        record = Record(word=keyword, source=self.provider, content=None)
        data = BeautifulSoup(self._get_raw(word))
        content = {}
        # handle record.word
        try:
            content['word'] = data.find('span', id='term').text
        except AttributeError:
            raise NotFoundError(word)

        # handle pronounce
        pronu_value = data.find('span', id='pronunciation_pos').text
        if pronu_value:
            pronu_value = pronu_value.split()
            content['pronounce'] = [
                    ('KK', pronu_value[0][2:]),
                    ('DJ', pronu_value[1][2:]),
            ]

        # handle sound
        # looks like the sound had been removed. 2015/05/26
        pronu_sound = data.find(class_='proun_sound')
        if pronu_sound:
            content['sound'] = [
                ('mp3', pronu_sound.find(
                        class_='source',
                        attrs={'data-type': 'audio/mpeg'}
                    ).attrs['data-src']),
                ('ogg', pronu_sound.find(
                        class_='source',
                        attrs={'data-type': 'audio/ogg'}
                    ).attrs['data-src']),
            ]

        if verbose:
            search_exp = data.find_all(class_='dd algo lst DictionaryResults')
        else:
            search_exp = data.find(
                class_='dd algo mt-20 lst DictionaryResults'
            )
            search_exp = zip(
                search_exp.find_all(class_='compTitle mb-10'),
                search_exp.find_all(class_='compArticleList mb-15 ml-10')
            )

        content['explain'] = []
        for part_of_speech, explain in search_exp:
            node = [part_of_speech.text]

            for item in explain.find_all('li', class_='ov-a'):
                pack = [item.find('h4').text]
                for example in item.find_all('span', id='example'):
                    sentence = ''
                    translation = ''

                    for word in example.contents:
                        if word.name == 'b':
                            sentence += '*' + word.text + '*'
                        elif word.name == 'span':
                            translation = word.text
                        else:
                            sentence += word

                    pack.append((sentence.strip(), translation.strip()))
                node.append(pack)
            content['explain'].append(node)

        record.content = json.dumps(content)

        if self.query_db_cache(keyword) is None:
            record.save(force_insert=True)

        return record

    def query_db_cache(self, word: str, verbose=False):
        keyword = word.lower()
        try:
            record = Record.get(word=keyword, source=self.provider)
        except Record.DoesNotExist as e:
            return None
        else:
            return record