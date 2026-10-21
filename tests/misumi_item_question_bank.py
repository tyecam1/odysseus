"""Phrasing banks for the Misumi item resolver (round 6), kept apart from the fix-time probes in test_misumi_item_resolution.py.

ITEM_FAMILIES: 8 families x 8 phrasings of a question about one recorded item ({n} is the item name). An exact item must be
answered from its own record (deterministic), never from another record and never with a "no".
TYPO_PHRASINGS: questions about a misspelt item ({t}); the misspelling may only make the item a candidate (model evidence or
"not confirmed"), never another record's answer and never a "no".
NON_INVENTORY: questions that use inventory-like words ("do we have", "any", "how many", "stock", food words) but are not about a
recorded item. None may get a deterministic household answer.
"""

ITEM_FAMILIES = {
    "casual": [
        "got any {n}?", "do we have {n} or what?", "we got {n}?", "any {n} about?", "is there {n} lying around?",
        "have we got some {n}?", "do we still have {n}?", "any {n} at all?",
    ],
    "british": [
        "Have we any {n}?", "Have we still got {n} in?", "Have we got any {n} in?", "Have we got {n} in the cupboard?",
        "Are we out of {n} yet?", "Have we run out of {n}?", "Have we any {n} left?", "Is there any {n} going?",
    ],
    "quantity": [
        "How many tins of {n} do we have?", "How many packs of {n} are left?", "How much {n} have we got?",
        "Do we have enough {n} for 4 people?", "Is there enough {n} for dinner?", "What's the quantity of {n}?",
        "How many bags of {n} are there?", "How much {n} is in the fridge?",
    ],
    "time": [
        "When does the {n} expire?", "When does the {n} go off?", "What's the expiry date of the {n}?",
        "When is the {n} best before?", "What's the best before date on the {n}?", "Has the {n} expired?",
        "Does the {n} need using up?", "What is the use by date of the {n}?",
    ],
    "anything_with": [
        "Anything with {n} in it?", "Do we have anything with {n}?", "Have we got something with {n} in it?",
        "Is there anything containing {n}?", "Got anything with {n}?", "Is there something made with {n}?",
        "Do we have anything with {n} in it?", "Anything containing {n} in the cupboard?",
    ],
    "location": [
        "Is there {n} in the larder?", "Any {n} on the top shelf?", "{n} in the freezer?", "Have we got {n} in the kitchen cupboard?",
        "Is the {n} in the pantry?", "Are there {n} in the bread bin?", "Do we keep {n} in the spice rack?",
        "Is there any {n} at home?",
    ],
    "negation_tag": [
        "We don't have any {n}, do we?", "We've got {n}, haven't we?", "Don't we have {n}?", "We haven't run out of {n}, have we?",
        "Haven't we got any {n}?", "We still have {n}, right?", "Are we not out of {n}?", "Do we not have any {n} left?",
    ],
    "shopping_stock_mix": [
        "Do we have {n} in stock or should I buy some?", "Is {n} running low?", "Are we low on {n}?", "Is the {n} finished?",
        "Is {n} all gone?", "Have we used up the {n}?", "Is there {n} left over?", "Is {n} in stock?",
    ],
}

TYPO_PHRASINGS = ["Do we have {t}?", "Any {t} left in stock?", "How much {t} do we have?", "Is {t} running low?"]

NON_INVENTORY = [
    "Do we have time to cook tonight?", "Any meal ideas?", "Any cooking classes booked?", "How many calories in an avocado?",
    "Any stock photos?", "Do we have a plan for the weekend?", "Do we have a meeting tomorrow?", "How many people are coming?",
    "Any news?", "Do we have to go out tonight?", "Is it running late?", "How much time do we have?", "Do we have a minute?",
    "Any thoughts on dinner?", "How many days until Christmas?", "Do we have plans on Saturday?", "Any word from the landlord?",
    "Do we have any idea what to cook?", "How much should we spend on food this week?", "Is there a bus strike today?",
    "Do we have a dog?", "Have we got a minute to talk?", "Any chance of rain?", "How many weeks until the holiday?",
    "Is there anything on TV tonight?", "Do we have an appointment on Monday?", "Any stock market news?",
    "How much is a pint of milk at the shop down the road?", "Do we have any money left this month?",
    "Is there time for a coffee?", "Do we have the energy to cook?", "Any recommendations for a takeaway?",
    "How many hours of sleep did I get?", "Do we have any guests coming?", "Is there a match on tonight?",
    "Any interesting podcasts?", "How much did the electricity cost?", "Do we have wifi?", "Any good films to watch?",
    "Do we have any updates on the parcel?", "Is there parking near the restaurant?", "How many steps did I walk today?",
]
