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
    - Navigate to your Anki media folder, in my case (Arch): /home/<user name>/.local/share/Anki2/<mail>/collection.media
      For Ubuntu, it was: /home/<user name>/snap/anki-desktop/common/<anki user name>/collection.media
    - Paste the images from the "Anki_media" folder to the "collection.media" folder
- Import without subdecks: Click "Import file" from Anki Desktop (Anki Web does not work!) and choose the CSV file
- Import with subdecks:
    - Install CrowdAnki add-on for Anki
    - Click File -> CrowdAnki: Import from disk -> Select the folder where the Json file is located -> Import
- Select the deck you want to import it in (and add some tags or whatever you want) and click import
    - Add option: Existing Notes: Update  -> Label is the front of a card. If front label different -> new card. If the
    same, Anki will update the card.
That's all!

Troubleshooting:
- If you see your images on Anki desktop but not on your phone or AnkiWeb, and everything else is correct, then:
    - Open Anki on your phone
    - THree dots -> Check -> Check media
    - If it says that there are files missing, continue with the following (if not it's a different issue)
    - On your computer, go to the folder where your Anki media is stored (e.g. /home/<user name>/.local/share/Anki2/<mail>/collection.media)
    or via Tools -> Check Media -> View Files.
    - Close Anki on your desktop
    - Delete the .db file in the media folder (e.g. collection.media.db)
    - Open Anki on your desktop
    - Now it should work after syncing.

"""

# Todo: Enable new lines in question (shift + Enter).


import os
import shutil
import csv
from bs4 import BeautifulSoup
from tkinter import filedialog, Tk
import urllib.parse
import hashlib
import re
import json
import uuid
from collections import defaultdict, Counter

#deck_name = "Test vector"
deck_name = "Semester 1: Data Science Master"

# UUID
# Data_Science: "cf724d70-6d64-4414-9e08-d0e424fc4567"
# Semester 1: "cf724d70-6d64-4414-9e08-d0e424fc4568"
MAIN_DECK_UUID = "cf724d70-6d64-4414-9e08-d0e424fc9999"     # Semester 1
# MAIN_DECK_UUID = "cf724d70-6d64-4414-9e08-d0e424fc4568"     # Old Semester 1
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


def merge_consecutive_ol(soup):
    """Merge consecutive <ol> tags into a single <ol> with multiple <li> children."""
    for ol in soup.find_all("ol"):
        next_sibling = ol.find_next_sibling()
        while next_sibling and next_sibling.name == "ol":
            # Move all <li> from the sibling into the current <ol>
            for li in next_sibling.find_all("li"):
                ol.append(li)
            to_extract = next_sibling
            next_sibling = next_sibling.find_next_sibling()
            to_extract.extract()  # remove the now-empty sibling
    return soup


def extract_cards_from_html(html_path, media_src_folder, media_output_folder, csv_output_path, json_output_path):

    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    cards = []
    media_files = []

    # Default deck root
    default_deck_path = deck_name

    # helper: clean 'H:' and split '->' chains into tokens
    def parse_header_chain(raw_text):
        # Remove leading/trailing whitespace
        text = raw_text.strip()
        # Remove any leading "H:" if present
        if text.startswith("H:"):
            text = text[2:].strip()
        # Split explicit chain notation "A -> B -> C"
        parts = [p.strip() for p in text.split("->")]
        # For safety remove any leading "H:" from parts too
        cleaned = [re.sub(r'^\s*H:\s*', '', p).strip() for p in parts if p and p.strip()]
        return cleaned

    # Utility: given a <details> element, build deck parts from its ancestor H: summaries
    def deck_parts_from_ancestors(details_elem):
        ancestors = list(reversed(details_elem.find_parents('details')))
        parts = []
        for anc in ancestors:
            s = anc.find('summary')
            if not s:
                continue
            t = s.get_text(strip=True)
            if t.startswith("H:"):
                parts.extend(parse_header_chain(t))
        return parts

    details_blocks = soup.find_all('details')
    print(f"Found {len(details_blocks)} toggle blocks.")

    # Keep a fallback 'last_seen_header_chain' for cases where headers are not nested in the HTML.
    last_seen_header_chain = []

    for details in details_blocks:
        summary = details.find('summary')
        if not summary:
            continue

        raw_summary = summary.get_text(strip=True)

        # If header (H:), update last_seen_header_chain and skip (headers are not cards)
        if raw_summary.startswith("H:"):
            # parse chain - supports "H: A -> H: B" or single "H: A"
            chain = parse_header_chain(raw_summary)
            # If the header explicitly contains a chain, use it as absolute path
            if len(chain) > 1:
                last_seen_header_chain = chain
            else:
                # If it's a single header token, update stack:
                # If previous header chain is empty -> set as top-level
                # If previous element was also an H: (i.e. consecutive H's), treat as child of previous header chain
                # Otherwise set as top-level (a new branch)
                # We determine "previous element was H" by looking at the previous sibling that is a <details>.
                prev = details.find_previous_sibling()
                prev_was_H = False
                if prev and prev.name == 'details':
                    prev_summary = prev.find('summary')
                    if prev_summary and prev_summary.get_text(strip=True).startswith("H:"):
                        prev_was_H = True

                if prev_was_H and last_seen_header_chain:
                    # append as deeper level (child)
                    last_seen_header_chain = last_seen_header_chain + chain
                else:
                    # start a new header branch
                    last_seen_header_chain = chain
            # header processed; we don't add a card for it
            continue

        # Only proceed if it's a question
        if not raw_summary.startswith("Q:"):
            continue

        # Extract the question text
        question = raw_summary[2:].strip()  # remove "Q:"

        # Remove the <summary> node so the rest is the answer content
        summary.extract()   # Todo: Unnecessary code?!

        # Extract inner HTML content from <details>
        inner_html = ''.join(str(tag) for tag in details.contents)

        # Split at "Q:" and "A:" inside the full HTML if present
        q_start = inner_html.find("Q:")
        a_start = inner_html.find("A:")

        if q_start != -1 and a_start != -1 and a_start > q_start:
            front_raw = inner_html[(q_start + 2):a_start].strip()
            back_raw = inner_html[(a_start + 2):].strip()
        else:
            # Fallback: everything is the back (answer)
            front_raw = ""
            back_raw = inner_html.strip()


        def normalize_html_for_identity(html: str) -> str:
            soup = BeautifulSoup(html, "html.parser")

            for img in soup.find_all("img"):
                # Replace each image with a stable placeholder
                img.replace_with("[[IMAGE]]")

            # Optional: normalize whitespace
            text = soup.get_text(separator=" ", strip=True)
            text = re.sub(r"\s+", " ", text)

            return text

        identity_front = normalize_html_for_identity(front_raw)
        identity_back = normalize_html_for_identity(back_raw)

        identity_text = question + identity_front + "\n---\n" + identity_back
        # question is not inside identity_front. front_raw only contains what
        # is inside the dropdown between "Q:" and "A:"

        slug = slugify(identity_text, max_len=33, hash_len=32)

        #slug = slugify(front_raw+back_raw, max_len=33, hash_len=32) # 32 bit
        # is overkill, but it won't hurt either.

        front_soup = BeautifulSoup(front_raw, 'html.parser')
        back_soup = BeautifulSoup(back_raw, 'html.parser')

        # Handle images (both front and back)
        img_counter = 1
        for soup_side in (front_soup, back_soup):
            for idx, img in enumerate(soup_side.find_all('img'), start=1):
                src = img.get('src')
                if not src:
                    continue
                decoded_src = urllib.parse.unquote(os.path.basename(src))
                ext = os.path.splitext(decoded_src)[1] or ".png"
                new_name = f"img_{slug}_{img_counter}{ext}"
                src_path = os.path.join(media_src_folder, decoded_src) if media_src_folder else None
                dest_path = os.path.join(media_output_folder, new_name)
                if src_path and os.path.exists(src_path):
                    shutil.copy2(src_path, dest_path)
                    print(f"Copied image: {new_name}")
                    img['src'] = new_name
                    img_counter += 1
                    if new_name not in media_files:
                        media_files.append(new_name)
                else:
                    print(f"Missing image file: {decoded_src} (expected in {media_src_folder})")

        front_html = f"<strong>{question}</strong><br>" + clean_html_content(front_soup)
        back_soup = merge_consecutive_ol(back_soup)
        back_html = clean_html_content(back_soup)

        # === Determine deck path for this card ===
        # 1) Prefer ancestor-based headers (if the Q is nested under details that have H: summaries)
        ancestor_parts = deck_parts_from_ancestors(details)
        if ancestor_parts:
            deck_full = "::".join([default_deck_path] + ancestor_parts)
        else:
            # 2) If no ancestor header, but there was a recent header in the document order, use that
            if last_seen_header_chain:
                deck_full = "::".join([default_deck_path] + last_seen_header_chain)
            else:
                # 3) fallback
                deck_full = f"{default_deck_path}::Default"

        cards.append((front_html, back_html, deck_full, identity_text))

    # Write CSV
    with open(csv_output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Front', 'Back', 'Deck'])
        for front, back, deck, _ in cards:
            writer.writerow([front, back, deck])

    print(f"Saved {len(cards)} cards to {csv_output_path}")
    print(f"Images saved to {media_output_folder}")

    def note_uuid(note_id: str) -> str:
        return str(uuid.uuid5(uuid.UUID(MAIN_DECK_UUID), note_id))

    # Important UUIDs
    note_model_uuid = note_uuid("note_model_basic_plus") #str(uuid.uuid5(uuid.UUID(MAIN_DECK_UUID), "note_model_basic_plus"))
    deck_config_uuid = note_uuid("deck_config") #str(uuid.uuid5(uuid.UUID(MAIN_DECK_UUID), "deck_config"))

    # Create the cards
    notes_by_deck = defaultdict(list)
    seen = defaultdict(int)

    for front, back, deck, identity_text in cards:

        #identity_key = front# + "\n---\n" + back
        guid = note_uuid(identity_text)

        seen[identity_text] += 1
        occurrence = seen[identity_text]

        if occurrence > 1:
            print(f"Warning: Duplicate: {front}. The card was not duplicated.")

        note = {
            # Future ID: With Notion API, one could use the Notion ID of the block, which is even better. For my purposes, it is fine like this, for now.
            "guid": guid,   # GUID important so that new import cards are not duplicated.
            "crowdanki_uuid": guid,  # Crowdanki_UUID important so that at new import cards not duplicated.
            "note_model_uuid": note_model_uuid,
            "fields": [front, back],
            "tags": []
        }
        notes_by_deck[deck].append(note)

    all_deck_names = set(deck for _, _, deck, _ in cards)
    decks_hierarchy = build_decks_hierarchy(all_deck_names, deck_config_uuid, notes_by_deck)

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
        "children": decks_hierarchy["children"],
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

    with open(json_output_path, 'w', encoding='utf-8') as f:
        json.dump(crowdanki_export, f, indent=2, ensure_ascii=False)

    print(f"Exported single CrowdAnki JSON: {json_output_path}")


def slugify(text, max_len=50, hash_len=12):

    s = text.lower()
    s = re.sub(r'[^a-z0-9]+', '_', s).strip('_')

    # create a stable hash from the full text
    h = hashlib.sha256(text.encode('utf-8')).hexdigest()[:hash_len]

    # leave room for "_" + hash
    base_len = max_len - hash_len - 1
    s = s[:base_len]

    return f"{s}_{h}"


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
