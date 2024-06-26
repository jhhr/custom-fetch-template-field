import base64
import math
import random
import time
from operator import itemgetter

from anki.consts import QUEUE_TYPE_SUSPENDED
from anki.decks import DeckManager
from anki.template import TemplateRenderContext
from anki.utils import ids2str
from aqt import mw

from .utils import write_custom_data, filter_init


def get_ord_from_model(model, fld_name):
    card_id_fld = next((f for f in model["flds"] if f["name"] == fld_name), None)
    if card_id_fld is not None:
        return card_id_fld["ord"]
    return None


VALID_ARGS = ["from_did", "from_deck_name", "from_note_type_id",
              "from_note_type_name", "select_card_by_fld_name",
              "fld_name_to_get_from_card", "cur_deck_white_list",
              "pick_card_by", "multi_value_count", "multi_value_separator"]

PICK_CARD_BY_VALID_VALUES = ('random', 'random_stable', 'least_reps')


def on_fetch_filter(
        text: str, field_name: str, filter_str: str, context: TemplateRenderContext
) -> str:
    """
     The filter syntax is like this:
     {{fetch[
      from_did='deck_id';
      from_deck_name='from_deck_name';
      from_note_type_id='note_type_id'
      from_note_type_name='from_note_type_name';
      cur_deck_white_list=['deck_name1', 'deck_name2', ...'];
      select_card_by_fld_name='note_fld_name_to_get_card_by';
      pick_card_by='random'/'random_stable'/'least_reps[ord]';
      fld_name_to_get_from_card='note_field_name_to_get';
      multi_value_count='number_of_cards_to_get';
      multi_value_separator='separator_for_multiple_results(default=", ")';
     ]:Field}}
    """
    if not (filter_str.startswith("fetch[") and filter_str.endswith("]")):
        return text

    args_dict, is_cache, show_error_message = filter_init("fetch", VALID_ARGS, filter_str, context)

    (
        from_did,
        from_deck_name,
        from_note_type_id,
        from_note_type_name,
        select_card_by_fld_name,
        fld_name_to_get_from_card,
        cur_deck_white_list,
        pick_card_by,
        multi_value_count,
        multi_value_separator
    ) = itemgetter(
        "from_did",
        "from_deck_name",
        "from_note_type_id",
        "from_note_type_name",
        "select_card_by_fld_name",
        "fld_name_to_get_from_card",
        "cur_deck_white_list",
        "pick_card_by",
        "multi_value_count",
        "multi_value_separator"
    )(args_dict)

    # Get from_did either directly or through from_deck_name
    if from_did is None:
        if from_deck_name is not None:
            from_did = mw.col.decks.id_for_name(from_deck_name)
        else:
            show_error_message(
                "Error in 'fetch[]' field args: Either 'from_did=' or 'from_deck_name=' value must be provided"
            )
            return ''

    # Get from_note_type_id either directly or through from_note_type_name
    if from_note_type_id is None:
        if from_note_type_name is not None:
            from_note_type_id = mw.col.models.id_for_name(from_note_type_name)
            if from_note_type_id is None:
                show_error_message(
                    f"Error in 'fetch[]' field args: Note type for from_note_type_name='{from_note_type_name}' not found, check your spelling",
                )
                return ''
        else:
            show_error_message(
                "Error in 'fetch[]' field args: Either 'from_note_type_id=' or 'from_note_type_name=' value must be provided")
            return ''

    if select_card_by_fld_name is None:
        show_error_message("Error in 'fetch[]' field args: 'select_card_by_fld_name=' value must be provided")
        return ''

    if fld_name_to_get_from_card is None:
        show_error_message(
            "Error in 'fetch[]' field args: 'fld_name_to_get_from_card=' value must be provided",
        )
        return ''

    if pick_card_by is None:
        show_error_message("Error in 'fetch[]' field args: 'pick_card_by=' value must be provided")
        return ''
    elif pick_card_by not in PICK_CARD_BY_VALID_VALUES:
        show_error_message(
            f"Error in 'fetch[]' field args: 'pick_card_by=' value must be one of {PICK_CARD_BY_VALID_VALUES}",
        )
        return ''

    if multi_value_count:
        try:
            multi_value_count = int(multi_value_count)
            if multi_value_count < 1:
                raise ValueError
        except ValueError:
            show_error_message(
                "Error in 'fetch[]' field args: 'multi_value_count=' value must be a positive integer"
            )
            return ''
    else:
        multi_value_count = 1

    DM = DeckManager(mw.col)

    if cur_deck_white_list is not None:
        # Check if the current deck is in the white list, otherwise we don't fetch
        card = context.card()
        cur_deck_id = card.odid or card.did
        all_decks = DM.all_names_and_ids(include_filtered=False)
        # whitelist deck is a list of deck or sub deck names
        # parent names can't be included since adding :: would break the filter text
        whitelist_dids = [
            deck.id for
            deck in all_decks if
            any(
                deck.name.endswith(f"::{whitelist_deck_name}") for
                whitelist_deck_name in cur_deck_white_list
            )
        ]
        if cur_deck_id not in whitelist_dids:
            return ''

    if multi_value_separator is None:
        multi_value_separator = ", "

    # First, fetch the ord value of the select_card_by_fld_name
    model = mw.col.models.get(from_note_type_id)
    if model is None:
        show_error_message(
            f"Error in 'fetch[]' field args: Note type for from_note_type_id='{from_note_type_id}' not found, check your spelling"
        )
        return ''

    fld_ord_to_id_card = get_ord_from_model(model, select_card_by_fld_name)
    fld_ord_to_get = get_ord_from_model(model, fld_name_to_get_from_card)
    if fld_ord_to_get is None:
        show_error_message(
            f"Error in 'fetch[]' field args: No field with name '{fld_name_to_get_from_card}' found in the note type '{model['name']}'"
        )
        return ''

    # Now select from the notes table the ones we have a matching field value
    # `flds` is a string containing a list of values separated by a 0x1f character)
    # We need to get the value in that list in index `fld_ord_to_id_card`
    # and test whether it has a substring `text`
    note_ids = None
    # First, check if we have cached the note_ids from a similar query already in extra_state
    notes_query_id = base64.b64encode(f"note_ids{from_note_type_id}{fld_ord_to_id_card}{text}".encode()).decode()
    try:
        note_ids = context.extra_state[notes_query_id]
    except KeyError:
        note_ids = []
        for note_id, fields_str in mw.col.db.all(
                f"select id, flds from notes where mid={from_note_type_id}"):
            if fields_str is not None:
                fields = fields_str.split("\x1f")
                if text in fields[fld_ord_to_id_card]:
                    note_ids.append(note_id)
                    context.extra_state[notes_query_id] = note_ids

    print(f"len(note_ids)={len(note_ids)}")

    if len(note_ids) == 0:
        show_error_message(
            f"Error in 'fetch[]' query: Did not find any notes where '{select_card_by_fld_name}' contains '{text}'"
        )
        if is_cache:
            # Set cache time into card.customData, so we don't keep querying this again
            write_custom_data(context.card(), "fc", math.floor(time.time()))
            mw.col.update_card(context.card())
        return ''
    else:
        print(f"Found {len(note_ids)} notes with '{select_card_by_fld_name}' containing '{text}'")
    note_ids_str = ids2str(note_ids)

    # Next, find cards with from_did and nid in the note_ids
    # Check for cached result again

    did_list = ids2str(DM.deck_and_child_ids(from_did))

    cards_query_id = base64.b64encode(f"cards{did_list}{from_note_type_id}{select_card_by_fld_name}".encode()).decode()
    try:
        cards = context.extra_state[cards_query_id]
    except KeyError:
        cards = mw.col.db.all(
            f"""
            SELECT
                id,
                nid
            FROM cards
            WHERE (did IN {did_list} OR odid IN {did_list})
            AND nid IN {note_ids_str}
            AND queue != {QUEUE_TYPE_SUSPENDED}
            """
        )
        context.extra_state[cards_query_id] = cards

    if (len(cards) == 0):
        show_error_message(
            f"Error in 'fetch[]' query: Did not find any non-suspended cards with from_did={from_did} for the notes whose '{select_card_by_fld_name}' contains '{text}'")
        if is_cache:
            # Set cache time into card.customData, so we don't keep querying this again
            write_custom_data(context.card(), "fc", math.floor(time.time()))
            mw.col.update_card(context.card())
        return ''

    # select a card or cards based on the pick_card_by value
    selected_cards = []
    result_val = ""
    for i in range(multi_value_count):
        # remove already selected cards from cards
        selected_card = None
        selected_val = ""
        # We don't make this key entirely unique as we want to cache the selected card for the same deck_id and
        # from_note_type_id combination, so that getting a different field from the same card type will still return the same card
        card_select_key = base64.b64encode(
            f"selected_card{did_list}{from_note_type_id}{pick_card_by}{i}".encode()).decode()
        print("card_select_key", card_select_key,
              f'{did_list}{from_note_type_id}{fld_name_to_get_from_card}{pick_card_by}{i}')

        if pick_card_by == 'random':
            # We don't want to cache this as it should in fact be different each time
            selected_card = random.choice(cards)
        elif pick_card_by == 'random_stable':
            # pick the same random card for the same deck_id and from_note_type_id combination
            # this will still work for multi_value_count as we're caching the selected card by the index too
            try:
                selected_card = context.extra_state[card_select_key]
                print("selected_card from cached key value")
            except KeyError:
                selected_card = random.choice(cards)
                context.extra_state[card_select_key] = selected_card
        elif pick_card_by == 'least_reps':
            # Loop through cards and find the one with the least reviews
            # Check cache first
            try:
                selected_card = context.extra_state[card_select_key]
            except KeyError:
                selected_card = min(cards,
                                    key=lambda c: mw.col.db.scalar(f"SELECT COUNT() FROM revlog WHERE cid = {c[0]}"))
                context.extra_state = {}
                context.extra_state[card_select_key] = selected_card
        if selected_card is None:
            show_error_message("Error in 'fetch[]' query: could not select card")

        selected_cards.append(selected_card)
        # Remove selected card so it can't be picked again
        cards = [c for c in cards if c != selected_card]
        selected_note_id = selected_card[1]

        # And finally, return the value from the field in the note
        # Check for cached result again
        result_val_key = base64.b64encode(f"{selected_note_id}{fld_ord_to_get}{i}".encode()).decode()
        try:
            selected_val = context.extra_state[result_val_key]
        except KeyError:
            target_note_vals_str = mw.col.db.scalar(f"SELECT flds FROM notes WHERE id = {selected_note_id}")
            if target_note_vals_str is not None:
                target_note_vals = target_note_vals_str.split("\x1f")
                selected_val = target_note_vals[fld_ord_to_get]
                context.extra_state[result_val_key] = selected_val

        result_val += f"{multi_value_separator if i > 0 else ''}{selected_val}"

        # If we've run out of cards, stop and return what we got
        if len(cards) == 0:
            break

    return result_val
