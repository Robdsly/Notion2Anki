# Notion2Anki

## How to use:
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

## Troubleshooting:
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
