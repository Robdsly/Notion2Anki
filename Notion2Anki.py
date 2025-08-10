"""

How to use:
- Document your notes in Notion as follows:
    - Whatever you want as question, turn into a toggle list AND add a "Q: ". So for instance:
    >Q: What is the capital of Italy?  -> And then afterwards the answer
    - It is not possible to add images to the "outside" of a toggle list, only "inside" the toggle list itself. This
    automatically makes an image that is supposed to be on the front page appear on the back page. However, sometimes you
    want a picture on the front side of a question card. In this case, I implemented a workaround:
    >Q: Look at the following image and guess the statistical distribution underlying the data points
        Q:
        <Your Image pasted here>
        A:
        Normal distribution
    The image you pasted after the "Q:" and before the "A:" will be pasted to the front of the card.
    - If you want subheaders, you can mark them with "H:". So for instance:
    H: Descriptive and inferential statistics -> H: Inferential statistics -> H: Hypothesis testing -> Q: What is a p-value?
    Note: This only works if you import the Json file with CrowdAnki. With normal import, only the CSV file works and there will be no subdecks.
- Optional: Choose a deck name "deck_name" and name the variable deck_name accordingly
- Optional: Specify a fixed UUID "MAIN_DECK_UUID". If it is fixed and you've update something in Notion, the deck will
also be updated in Anki. Otherwise, a new deck will be created. If you want a new deck, you can let it generate, see below.
- Export Notion page you want to convert to cards to HTML folder
- Unzip folder
- Execute this script, and select the folder (enter it). If you did not properly enter, script will say it did not find
    HTML file. A csv file and a Json file containing the card content as well as a folder "Anki_media" will be created
- If there are images in the cards:
    - Navigate to your Anki media folder, in my case: /home/<user name>/.local/share/Anki2/<mail>/collection.media
    - Paste the images from the "Anki_media" folder to the "collection.media" folder
- Import without subdecks: Click "Import file" from Anki Desktop (Anki Web does not work!) and choose the CSV file
- Import with subdecks:
    - Install CrowdAnki add-on for Anki
    - Click File -> CrowdAnki: Import from disk -> Select the folder where the Json file is located -> Import
- Select the deck you want to import it in (and add some tags or whatever you want) and click import
    - Add option: Existing Notes: Update  -> Label is the front of a card. If front label different -> new card. If the
    same, Anki will update the card.
That's all!

"""


import os
import shutil
import csv
from bs4 import BeautifulSoup
from tkinter import filedialog, Tk
#from datetime import datetime
import urllib.parse
#import hashlib
import re
import json
import uuid
from collections import defaultdict

deck_name = "Data_Science"
MAIN_DECK_UUID = "cf724d70-6d64-4414-9e08-d0e424fc4567"     # Manual UUID definition
#MAIN_DECK_UUID = str(uuid.uuid4())      # Randomly generated UUID for the main deck

def build_decks_hierarchy(deck_names, deck_config_uuid, notes_by_deck, root_name=deck_name):
    tree = {}
    for deck_path in deck_names:
        parts = deck_path.split("::")
        if parts[0] == root_name:
            parts = parts[1:]  # skip root in hierarchy, otherwise 2x deck_name
        node = tree
        for part in parts:
            node = node.setdefault(part, {})

    def uuid_for_deck_name(name):
        # Deterministic UUID based on deck name string, to keep consistent between exports
        namespace = uuid.UUID(MAIN_DECK_UUID)  # Use main deck UUID as namespace
        return str(uuid.uuid5(namespace, name))

    def build_children(name, subtree, full_path):
        children = [build_children(k, v, f"{full_path}::{k}") for k, v in subtree.items()]
        return {
            "__type__": "Deck",
            "crowdanki_uuid": uuid_for_deck_name(full_path),
            "name": name,
            "notes": notes_by_deck.get(full_path, []),  # assign the notes for this deck
            "deck_config_uuid": deck_config_uuid,
            "children": children
        }

    root_name = deck_name
    #root_tree = tree[root_name]
    #return [build_children(root_name, root_tree, root_name)]
    return {
            "__type__": "Deck",
            "crowdanki_uuid": MAIN_DECK_UUID,
            "name": root_name,
            "notes": notes_by_deck.get(root_name, []),
            "deck_config_uuid": deck_config_uuid,
            "children": [build_children(k, v, f"{root_name}::{k}") for k, v in tree.items()]
        }


def clean_html_content(soup_fragment):
    # Remove all attributes except 'src' (for <img>)
    for tag in soup_fragment.find_all(True):
        tag.attrs = {k: v for k, v in tag.attrs.items() if k == 'src'}
    return soup_fragment.decode_contents().strip()

def extract_cards_from_html(html_path, media_src_folder, media_output_folder, csv_output_path, json_output_path):
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    #date_str = datetime.now().strftime("%Y-%m-%d")
    #folder_name = os.path.basename(os.path.dirname(html_path)).replace(" ", "_")
    #img_counter = 1

    cards = []
    media_files = []
    current_deck = f"{deck_name}::Default"

    details_blocks = soup.find_all('details')
    print(f"Found {len(details_blocks)} toggle blocks.")

    for details in details_blocks:

        summary = details.find('summary')
        if not summary:
            continue

        raw_question = summary.get_text(strip=True)
        if raw_question.startswith("H:"):
            current_deck = f"{deck_name}::{raw_question[2:].strip()}"#f"{deck_name}::{raw_question[2:].strip()}"
            #raw_question.extract()  # Remove from HTML so it doesn't show in answer
            continue
        if not raw_question.startswith("Q:"):
            continue  # Skip if it doesn't start with "Q:"
        question = raw_question[2:].strip()  # Remove the "Q:"
        summary.extract()  # remove <summary> so the rest is just the answer

        # Clean and prepare answer HTML
        #answer_soup = BeautifulSoup(str(details), 'html.parser')
        #answer_html = clean_html_content(answer_soup)
        # Extract inner HTML content from <details> without wrapping in <details>
        inner_html = ''.join(str(tag) for tag in details.contents)
        slug = slugify(question)

        # Split at "Q:" and "A:" inside the full HTML
        q_start = inner_html.find("Q:")
        a_start = inner_html.find("A:")

        if q_start != -1 and a_start != -1 and a_start > q_start:
            front_raw = inner_html[(q_start + 2):a_start].strip()   # +2 because Q: is 2 characters long
            back_raw = inner_html[(a_start + 2):].strip()
        else:
            # Fallback if not both Q:/A: found
            front_raw = ""
            back_raw = inner_html.strip()

        # Parse front and back into separate soups
        front_soup = BeautifulSoup(front_raw, 'html.parser')
        back_soup = BeautifulSoup(back_raw, 'html.parser')
        #inner_soup = BeautifulSoup(inner_html, 'html.parser')

        # Handle images
        #for img in inner_soup.find_all('img'):     # Use this if image names by date
        for soup in [front_soup, back_soup]:
            for idx, img in enumerate(soup.find_all('img'), start=1):
                src = img.get('src')
                if not src:
                    continue
                #ext = os.path.splitext(src)[-1]  # Get extension   # Use this if image names by date
                #new_name = f"img_{folder_name}_{date_str}_{img_counter:03}{ext}" # Use this if image names by date
                decoded_src = urllib.parse.unquote(os.path.basename(src))
                ext = os.path.splitext(decoded_src)[1]  # e.g. ".png"
                new_name = f"img_{slug}_{idx}{ext}"
                src_path = os.path.join(media_src_folder, decoded_src)
                dest_path = os.path.join(media_output_folder, new_name)
                if os.path.exists(src_path):
                    shutil.copy2(src_path, dest_path)
                    print(f"Copied image: {new_name}")
                    img['src'] = new_name   # Update src to just the file name (Anki expects this)
                    #img_counter += 1
                    if new_name not in media_files:
                        media_files.append(new_name)
                else:
                    print(f"Missing image file: {decoded_src}")

        front_html = f"<strong>{question}</strong><br>" + clean_html_content(front_soup)
        back_html = clean_html_content(back_soup)
        cards.append((front_html, back_html, current_deck))
        #cards.append((front_html, back_html))
        #answer_html = clean_html_content(inner_soup)
        #cards.append((question, answer_html))

    # Write CSV
    with open(csv_output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Front', 'Back', 'Deck'])
        for front, back, deck in cards:
            writer.writerow([front, back, deck])

    print(f"Saved {len(cards)} cards to {csv_output_path}")
    print(f"Images saved to {media_output_folder}")


    # Write Json file
    note_model_uuid = str(uuid.uuid5(uuid.UUID(MAIN_DECK_UUID), "note_model_basic_plus"))
    deck_config_uuid = str(uuid.uuid5(uuid.UUID(MAIN_DECK_UUID), "deck_config"))

    crowdanki_export = {
        "crowdanki_uuid": MAIN_DECK_UUID,
        "name": deck_name,
        "deck_config_uuid": deck_config_uuid,
        "deck_configurations": [
            {
                "crowdanki_uuid": deck_config_uuid,
                "name": "Default",
                "autoplay": True,
                "dyn": False,
                "lapse": {
                    "delays": [10],
                    "leechAction": 0,
                    "leechFails": 8,
                    "minInt": 1,
                    "mult": 0
                },
                "maxTaken": 60,
                "new": {
                    "bury": True,
                    "delays": [1, 10],
                    "initialFactor": 2500,
                    "ints": [1, 4, 7],
                    "order": 1,
                    "perDay": 20,
                    "separate": True
                },
                "replayq": True,
                "rev": {
                    "bury": True,
                    "ease4": 1.3,
                    "fuzz": 0.05,
                    "ivlFct": 1,
                    "maxIvl": 36500,
                    "minSpace": 1,
                    "perDay": 200
                },
                "timer": 0,
                "mod": 0,  # Unix timestamp (you can leave it as 0 or import `time` and use `int(time.time())`)
            }
        ],
        "media_files": media_files,
        "notes": [],
        "children": [],
        "note_models": [
            {
                "__type__": "NoteModel",
                "crowdanki_uuid": note_model_uuid,
                "name": "Basic+",
                "type": 0,
                "mod": 0,
                "sortf": 0,
                "latexPre": "\\documentclass[12pt]{article}\n\\special{papersize=3in,5in}\n\\usepackage[utf8]{inputenc}\n\\usepackage{amssymb,amsmath}\n\\pagestyle{empty}\n\\setlength{\\parindent}{0in}\n\\begin{document}\n",
                "latexPost": "\\end{document}",
                "css": ".card {\n font-family: arial;\n font-size: 20px;\n text-align: center;\n color: black;\n background-color: white;\n}\n",
                "flds": [
                    {
                        "name": "Front",
                        "ord": 0,
                        "font": "Arial",
                        "size": 20,
                        "rtl": False,
                        "sticky": False,
                        "media": [],
                        "description": "",
                        "collapsed": False,
                        "excludeFromSearch": False,
                        "plainText": False,
                        "preventDeletion": False,
                        "tag": None,
                        "id": None
                    },
                    {
                        "name": "Back",
                        "ord": 1,
                        "font": "Arial",
                        "size": 20,
                        "rtl": False,
                        "sticky": False,
                        "media": [],
                        "description": "",
                        "collapsed": False,
                        "excludeFromSearch": False,
                        "plainText": False,
                        "preventDeletion": False,
                        "tag": None,
                        "id": None
                    }
                ],
                "tmpls": [
                    {
                        "name": "Card 1",
                        "ord": 0,
                        "qfmt": "{{Front}}",
                        "afmt": "{{FrontSide}}<hr id=answer>{{Back}}",
                        "bqfmt": "",
                        "bafmt": "",
                        "did": None,
                        "sticky": False,
                        "id": None
                    }
                ],
                "req": [
                    [0, "any", [0]]
                ],
                "tags": [],
                "vers": [],
                "latexsvg": False
            }
        ]
    }

    notes_by_deck = defaultdict(list)
    for front, back, deck in cards:
        note = {
            "note_model_uuid": note_model_uuid,
            "fields": [front, back],
            "tags": []
        }
        notes_by_deck[deck].append(note)

    all_deck_names = set(deck for _, _, deck in cards)  # Collect all unique deck names from cards:
    decks_hierarchy = build_decks_hierarchy(all_deck_names, deck_config_uuid, notes_by_deck)
    print(json.dumps(decks_hierarchy, indent=2))
    crowdanki_export["children"] = decks_hierarchy["children"]
    #crowdanki_export.pop("children", None)  # remove the empty key

    with open(json_output_path, 'w', encoding='utf-8') as f:
        json.dump(crowdanki_export, f, indent=2, ensure_ascii=False)

    print(f"Exported single CrowdAnki JSON: {json_output_path}")


def slugify(text):
    s = text.lower()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    return s.strip('_')[:50]

def main():
    # File dialog to choose folder
    root = Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="Select Notion HTML export folder")
    if not folder:
        print("No folder selected.")
        return

    # Find the HTML file and media folder (e.g. /assets)
    html_file = None
    media_folder = None

    for filename in os.listdir(folder):
        if filename.endswith('.html'):
            html_file = os.path.join(folder, filename)
        elif os.path.isdir(os.path.join(folder, filename)):
            media_folder = os.path.join(folder, filename)

    if not html_file:
        print("❌ No .html file found in folder.")
        return

    media_output = os.path.join(folder, "anki_media")
    os.makedirs(media_output, exist_ok=True)

    csv_output = os.path.join(folder, "anki_cards.csv")
    json_output = os.path.join(folder, os.path.basename(os.path.normpath(folder))+".json")  # CrowdAnki expects the Json file to have the same name as the folder

    extract_cards_from_html(html_file, media_folder, media_output, csv_output, json_output)


if __name__ == "__main__":
    main()
