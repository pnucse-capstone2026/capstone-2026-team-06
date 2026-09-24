import scispacy
import spacy

class MentionDetection:

    def __init__(self):
        self.nlp = spacy.load("en_core_sci_scibert")

    def extract(self, question: str):
        doc = self.nlp(question)

        mentions = []
        seen = set()

        for ent in doc.ents:
            mention = ent.text.strip()

            # 완전히 동일한 mention 제거
            if mention not in seen:
                seen.add(mention)
                mentions.append(mention)

        return mentions
