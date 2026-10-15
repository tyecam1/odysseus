"""The ONE safety gate for learned adaptation in Misumi (round-5 repair, 2026-10-15).

Learned behaviour (an approved persona style such as "keep answers brief", or a learned routing overlay such as "send kitchen
questions to Jin") is a convenience. On a turn about an emergency, an injury, poisoning, gas, fire, self-harm, abuse or a
child's safety it can do harm (brevity that drops the "call 999" step; a kitchen question routed to a music persona). So the
gate is FAIL-SAFE: learned behaviour applies only when a turn is *positively benign* by a conservative check, and every
doubt resolves to "not benign" - which costs nothing but the learned convenience on that one turn.

``is_benign_turn`` is False when ANY of these holds (all text is scanned - the whole turn, plus any recent context the
caller passes - never a prefix):

* a safety lexicon matches: emergency services, medical symptoms, injuries and falls, collapse, breathing and colour change,
  poisoning and ingestion (verb + substance), medicines and dosing, gas/CO, fire/smoke/burning, electricity, drowning,
  self-harm and suicidal phrasing, violence and abuse (verb + person), animal bites, missing children - including common
  Spanish, French, German, Italian, Portuguese and Dutch terms (accents are folded first);
* a key safety word appears with a one-letter typo ("swallowd", "breahting", "unconcious", "ambulence");
* a reserved governance matter is named (standards, values, boundaries, ratification, Level 5/6, privacy, retention);
* the turn contains letters outside the Latin script (we cannot assess it, so it is not "positively benign");
* the text is too long to assess within the budget.

HONEST LIMITS: this is a lexicon, i.e. a mitigation, not a classifier. It will miss some paraphrases (it is tested on the
reported ones, typos, long prompts and the listed languages) and it will flag some harmless turns (that only withholds learned
style/routing). A model-based or trained-classifier safety gate is FUTURE WORK and is not claimed here.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Iterable

MAX_ASSESS_CHARS = 200_000  # beyond this a turn is simply not assessed as benign (fail-safe, bounded cost)

_TYPOGRAPHIC = str.maketrans({"’": "'", "‘": "'", "‛": "'", "ʼ": "'", "“": '"', "”": '"',
                              "„": '"', "–": "-", "—": "-", " ": " ", " ": "\n", " ": "\n"})


def normalise(text: object) -> str:
    """Lower-case, typographic quotes folded, accents removed ('lejía' -> 'lejia', 'Küche' -> 'kuche'), 'ß' -> 'ss'."""
    folded = unicodedata.normalize("NFKD", str(text or "").translate(_TYPOGRAPHIC))
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return folded.replace("ß", "ss").lower()


# A person as the object of a verb ("hits me", "bit my son", "attacked the kids").
_OBJ = (r"(?:me|us|him|her|them|my\s+\w+|our\s+\w+|his\s+\w+|their\s+\w+|the\s+(?:kids?|children|baby|toddler|dog))\b")
_HARMFUL = (r"(?:bleach|cleaner|cleaning\s+product|detergent|chemicals?|pods?|tablets?|pills?|medicine|meds|batter(?:y|ies)|magnets?|"
            r"antifreeze|white\s+spirit|paint\s+thinner|turps|weed\s?killer|rat\s+poison|slug\s+pellets|dishwasher|washing\s+(?:up\s+)?"
            r"(?:liquid|powder|tablet)|laundry|capsules?|e-?liquid|vape\s+(?:juice|liquid)|lighter\s+fluid|petrol|bleach|drain\s+"
            r"cleaner|mushrooms?|berries|nicotine|perfume|nail\s+polish|lamp\s+oil|essential\s+oils?|lithium)")

# (domain, pattern) over the NORMALISED text. Patterns err towards a match; only cheap unambiguous carve-outs exist.
_DOMAINS: tuple[tuple[str, str], ...] = (
    ("emergency", r"\b(?:emergenc\w*|urgent\w*|ambulance|paramedics?|999|911|112|a\s*&\s*e|er\s+room|hospital|"
                  r"call\s+(?:an?\s+)?(?:doctor|gp|nurse|police)|help\s+(?:me|us|him|her)\b[^\n]{0,60}\b(?:quick|now|please)|sos|mayday|"
                  r"poison\s+control|nhs\s+111|111)\b"),
    ("gas-co", r"\bgas\w*\s+(?:leak\w*|smell\w*|escap\w*|hiss\w*)|\b(?:smell\w*|stink\w*|whiff|reek\w*)\b[^.!?\n]{0,30}\bgas\b|"
               r"\bgas\b[^.!?\n]{0,30}\b(?:smell\w*|stink\w*|whiff|leak\w*)|\bleak\w*\s+gas\b|\bcarbon\s+monoxide\b|"
               r"\bco\s+(?:alarm|detector|poisoning|leak)\b|\brotten\s+eggs?\b|\bgassy\s+smell\b"),
    ("fire-smoke", r"\bfire\b(?!\s+(?:up|off|away)\b)|\bon\s+fire\b|\bcaught\s+fire\b|\bflames?\b|\bblaze\b|"
                   r"\bsmoke\b|\bsmoky\b|\bsmoking\s+(?:socket|plug|oven|pan|wire|appliance|charger)\b|\bburning\b|\bscorch\w*|"
                   r"\bspark(?:s|ing|ed)?\b|\bmelt(?:ed|ing)\s+(?:plug|wire|cable|socket|charger)\b|\bexplo(?:de|ded|des|ding|sion|sions|sive)\b"),
    ("electric", r"\belectr\w*\s+shock\w*|\belectrocut\w*|\bshock(?:ed)?\s+(?:from|by)\b|\blive\s+wires?\b|\bexposed\s+wires?\b|"
                 r"\bgot\s+(?:a\s+)?shock\b|\b(?:socket|plug|outlet)\b[^.!?\n]{0,30}\b(?:shock|spark|smok|burn|melt)\w*"),
    ("drowning", r"\bdrown\w*|\b(?:under|face\s+down\s+in(?:\s+the)?)\s+(?:the\s+)?(?:water|pool|bath)\b|"
                 r"\bfell\s+in(?:to)?\s+(?:the\s+)?(?:pool|pond|river|canal|sea|lake|bath)\b"),
    ("poisoning", r"\bswallow\w*|\bpoison\w*|\bingest\w*|\bbleach\b|\bantifreeze\b|\boverdos\w*|\btoxic\b|"
                  r"\b(?:button|coin)[- ]?(?:cell|batter(?:y|ies))\b|"
                  r"\b(?:drank|drunk|drink\w*|ate|eaten|eat(?:s|ing)?|licked|lick(?:s|ing)?|chew\w*|bit\s+into|sucked|"
                  r"got\s+into|in\s+(?:his|her|their|my)\s+mouth)\b[^.!?\n]{0,50}\b" + _HARMFUL + r"\b|"
                  r"\b" + _HARMFUL + r"\b[^.!?\n]{0,40}\b(?:in\s+(?:his|her|their|my)\s+(?:mouth|eyes?)|swallow\w*|ate|eaten|drank)\b"),
    ("medicine-dosing", r"\b(?:paracetamol|acetaminophen|ibuprofen|calpol|nurofen|aspirin|tylenol|codeine|morphine|tramadol|"
                        r"antihistamines?|insulin|inhaler|epi-?pens?|antibiotics?|antidepressants?|sertraline|diazepam|"
                        r"medicines?|medications?|meds|prescriptions?)\b|\b(?:doses?|dosage|dosing|mg|milligrams?|ml\s+of)\b|"
                        r"\b(?<!dishwasher\s)(?:pills?|tablets?|capsules?)\b"),
    ("medical", r"\bchest\b[^.!?\n]{0,20}\b(?:pains?|tight\w*|pressure|hurts?)\b|\b(?:pain|tight\w*|pressure)\s+in\s+\w+\s+chest\b|"
                r"\bbreath\w*|\bwheez\w*|\bgasp\w*|\bchok\w*|\b(?:turn(?:ing|ed|s)?|gone|going|went)\s+(?:a\s+)?(?:funny\s+|bit\s+|very\s+)?(?:blue|grey|gray|purple|pale|white)\b|"
                r"\b(?:lips?|face|skin)\b[^.!?\n]{0,20}\b(?:blue|grey|gray|swell\w*|swollen)\b|\bswell\w*|\bswollen\b|"
                r"\bcollaps\w*|\bunconscious\w*|\bunresponsive\b|\bpassed\s+out\b|\bfaint\w*|\bblack(?:ed)?\s+out\b|"
                r"\b(?:won'?t|can'?t|cannot|not)\s+(?:wake|waking|move|moving|feel\s+(?:his|her|my)|stand)\b|\bfloppy\b|\blimp\b|"
                r"\bfell\b|\bfallen\b|\bfall(?:s|ing)?\s+(?:down|over|off|from)\b|\bhit\s+(?:his|her|my|their|the\s+back\s+of\s+\w+)\s+head\b|"
                r"\bhead\s+(?:injur\w*|wound|bump)\b|\bknocked\s+(?:out|unconscious)\b|\bconcuss\w*|"
                r"\bbleed\w*|\bblood\w*|\bwounds?\b|\binjur\w*|\bhurt\b|\bbroken\s+(?:bone|arm|leg|wrist|ankle|neck|back|hip)\b|"
                r"\bfractur\w*|\bdislocat\w*|\bburn(?:s|ed|t)?\b(?!\s+(?:cd|dvd|disc|calories|fat|rubber|out\b))|\bscald\w*|"
                r"\bheart\s+(?:attack|racing|pounding|stopped)\b|\bcardiac\b|\bstroke\b|\bseizur\w*|\bconvuls\w*|\bfits?\b(?=\s+(?:again|now|and))|"
                r"\banaphyla\w*|\ballerg\w*|\bhives\b|\brash\b|\bfevers?\b|\bhigh\s+temperature\b|\bvomit\w*|\bthrowing\s+up\b|"
                r"\bdiarrh\w*|\bdehydrat\w*|\bnumb(?:ness)?\b|\bparaly\w*|\bslurr\w*|\bdizz\w*|\bdelirious\b|\bsepsis\b|"
                r"\bstiff\s+neck\b|\bsymptoms?\b|\bpain(?:ful|s)?\b|\bmedical\b|\bfirst[- ]aid\b|\bcpr\b|\bdefib\w*|\bconcussion\b|"
                r"\bpregnan\w*|\bmiscarr\w*|\bcontractions\b|\bwaters\s+broke\b|\bsuffocat\w*|\bstrangl\w*|\bhang(?:ed|ing)\s+(?:him|her|my|them)sel\w*"),
    ("self-harm", r"\bsuicid\w*|\bkill\w*\s+(?:my|him|her|them|your)sel(?:f|ves)\b|\bend\s+(?:it\s+all|it|things|my\s+life|(?:my|his|her)\s+own\s+life)\b|"
                  r"\b(?:take|taking)\s+(?:my|his|her)\s+(?:own\s+)?life\b|\bself[- ]?harm\w*|\bhurt\w*\s+(?:my|him|her|them)sel(?:f|ves)\b|"
                  r"\bcut\w*\s+(?:my|him|her)sel(?:f|ves)\b|\bwant(?:s|ed)?\s+to\s+die\b|\b(?:don'?t|do\s+not|dont)\s+want\s+to\s+"
                  r"(?:live|be\s+alive|be\s+here|wake\s+up|exist)\b|\bno\s+(?:reason|point)\s+(?:to|in)\s+(?:live|living|going\s+on)\b|"
                  r"\bbetter\s+off\s+(?:dead|without\s+me)\b|\bcan'?t\s+go\s+on\b|\bnot\s+worth\s+living\b|\bgive\s+up\s+on\s+life\b|"
                  r"\bdisappear\s+forever\b|\bgoodbye\s+forever\b"),
    ("violence-abuse", r"\b(?:hits?|hitting|beats?|beating|beaten|punch\w*|kick(?:s|ed|ing)?|slap\w*|chok(?:es|ed|ing)|strangl\w*|"
                       r"shov\w*|push(?:es|ed)|grabb\w*|threaten\w*|hurts?|hurting|attack\w*|stab\w*|shot|shoots?|shooting|"
                       r"rap(?:es|ed|ing)|molest\w*|touch(?:es|ed))\s+" + _OBJ + r"|"
                       r"\b(?:abus\w*|assault\w*|violen\w*|domestic|stalk\w*|harass\w*|groom(?:ed|ing)\s+(?:my|our|a|the)\b|knife|knives|"
                       r"gun|guns|weapons?|intruder|burglar\w*|break[- ]?in|broke\s+in|police|kidnap\w*|trafficked|"
                       r"(?:scared|afraid|terrified)\s+of\s+(?:him|her|my|them)|unsafe|danger\w*)\b"),
    ("animal-bite", r"\b(?:bit|bites|bitten|mauled|stung)\s+(?:by\s+)?" + _OBJ + r"|"
                    r"\b(?:dog|cat|snake|spider|tick|wasp|bee|jellyfish|adder|fox|rat)\s+(?:bit|bite|bitten|sting|stung|attack\w*)\b"),
    ("child-safety", r"\b(?:missing|lost|can'?t\s+find|cannot\s+find)\s+(?:my|our|the)\s+(?:son|daughter|child|kid|toddler|baby|boy|girl)\b|"
                     r"\b(?:son|daughter|child|kid|toddler|baby)\s+(?:is\s+)?missing\b|\bshaken\s+baby\b|\bsids\b|\bcot\s+death\b"),
    # Common non-English terms (accents already folded).
    ("non-english", r"\b(?:huele\s+a\s+gas|olor\s+a\s+gas|fuga\s+de\s+gas|fuego|incendio|humo|veneno|envenen\w*|lejia|"
                    r"ahog\w*|sangr\w*|emergencia|ambulancia|dolor\s+(?:de|en\s+el)\s+pecho|no\s+puede\s+respirar|no\s+respira|"
                    r"suicid\w*|me\s+quiero\s+morir|bebio|se\s+trago|se\s+cayo|desmay\w*|inconsciente|me\s+pega|"
                    r"odeur\s+de\s+gaz|fuite\s+de\s+gaz|\bgaz\b|feu|incendie|fumee|poison|empoisonn\w*|eau\s+de\s+javel|javel|noy\w*|"
                    r"saign\w*|urgence\w*|douleur\s+thoracique|douleur\s+(?:a|dans)\s+la\s+poitrine|respire\s+(?:pas|plus)|"
                    r"me\s+tuer|envie\s+de\s+mourir|avale|evanoui\w*|inconscient\w*|il\s+me\s+frappe|"
                    r"gasgeruch|gasleck|riecht\s+nach\s+gas|feuer|rauch|vergift\w*|bleiche|chlorreiniger|ertrink\w*|"
                    r"ertrunken|blut\w*|notfall|notarzt|krankenwagen|rettungswagen|brustschmerz\w*|keine\s+luft|atmet\s+nicht|"
                    r"selbstmord|umbringen|verschluckt|bewusstlos|ohnmacht\w*|schlagt\s+mich|"
                    r"odore\s+di\s+gas|fuga\s+di\s+gas|fuoco|incendio|fumo|veleno|avvelen\w*|candeggina|annega\w*|sangue|emergenza|"
                    r"ambulanza|dolore\s+al\s+petto|non\s+respira|"
                    r"cheiro\s+a\s+gas|vazamento\s+de\s+gas|fogo|fumaca|lixivia|agua\s+sanitaria|afog\w*|emergencia|"
                    r"gaslucht|gaslek|rook|vergif\w*|bloed\w*|noodgeval|ambulance|borstpijn|ademt\s+niet|zelfmoord)\b"),
)
_COMPILED: tuple[tuple[str, re.Pattern[str]], ...] = tuple((d, re.compile(p)) for d, p in _DOMAINS)

_RESERVED = re.compile(
    r"\b(?:standards?|values?|boundaries|ratif(?:y|ied|ication))\b|\blevel\s*(?:5|five|6|six)\b|"
    r"\b(?:safety|safe(?:guard\w*)?|retention|privacy)\b|\bmemory\s+(?:retention|decisions?|policy|capture)\b"
)

# Single words whose one-edit misspellings still count ("swallowd", "unconcious", "ambulence", "breahting").
# Only long, distinctive words whose one-edit neighbours are not everyday words (so "cooking", "painted", "turning", "attached",
# "browning" and "spelling" are not caught by "choking", "fainted", "burning", "attacked", "drowning" and "swelling").
_FUZZY_WORDS = (
    "swallowed", "swallow", "swallowing", "poisoned", "poisoning", "overdose", "overdosed", "unconscious", "unresponsive",
    "collapsed", "collapse", "seizure", "seizures", "breathing", "breathe", "bleeding", "ambulance", "emergency", "hospital",
    "suicide", "suicidal", "allergic", "anaphylaxis", "anaphylactic", "electrocuted", "concussion", "vomiting", "paracetamol",
    "ibuprofen", "medicine", "medication", "monoxide", "assault", "assaulted", "stabbed", "detergent", "antifreeze", "bleach",
    "scalded", "injured", "swollen", "choked", "strangled", "selfharm",
)


def _deletes(word: str) -> set[str]:
    return {word[:i] + word[i + 1:] for i in range(len(word))}


@lru_cache(maxsize=1)
def _fuzzy_index() -> tuple[frozenset[str], frozenset[str]]:
    exact = frozenset(_FUZZY_WORDS)
    neighbourhood: set[str] = set()
    for word in _FUZZY_WORDS:
        if len(word) >= 6:
            neighbourhood |= _deletes(word)
    return exact, frozenset(neighbourhood)


def _fuzzy_hit(text: str) -> str | None:
    """A token within one edit (deletion, insertion, substitution or adjacent swap) of a key safety word, else None."""
    exact, neighbourhood = _fuzzy_index()
    for token in set(re.findall(r"[a-z]{4,}", text)):
        if token in exact:
            return token
        if len(token) < 6:
            continue
        if token in neighbourhood or (_deletes(token) & (exact | neighbourhood)):
            return token
    return None


def _non_latin_letters(text: str) -> bool:
    for ch in text:
        if ch.isalpha() and ord(ch) > 0x24F:  # beyond Latin Extended-B: a script this lexicon cannot assess
            try:
                if not unicodedata.name(ch).startswith("LATIN"):
                    return True
            except ValueError:
                return True
    return False


def assess(text: object, context: Iterable[object] = ()) -> dict[str, object]:
    """Why a turn is or is not positively benign: {'benign': bool, 'reasons': [...]} (reasons empty only when benign)."""
    parts = [str(text or "")] + [str(item) for item in context if item]
    raw = "\n".join(parts)
    reasons: list[str] = []
    if len(raw) > MAX_ASSESS_CHARS:
        return {"benign": False, "reasons": ["too-long-to-assess"]}
    norm = normalise(raw)
    for domain, pattern in _COMPILED:
        if pattern.search(norm):
            reasons.append(domain)
    if _RESERVED.search(norm):
        reasons.append("reserved-matter")
    hit = _fuzzy_hit(norm)
    if hit is not None:
        reasons.append(f"near-miss:{hit}")
    if _non_latin_letters(raw):
        reasons.append("unassessed-script")
    return {"benign": not reasons, "reasons": reasons}


def safety_matter(text: object, context: Iterable[object] = ()) -> str | None:
    """The first safety domain a turn touches (or a near-miss / unassessable marker), None when none does."""
    reasons = [r for r in assess(text, context)["reasons"] if r != "reserved-matter"]
    return str(reasons[0]) if reasons else None


def is_benign_turn(text: object, context: Iterable[object] = ()) -> bool:
    """True ONLY when the turn (and any context given) is positively benign. Any error also means 'not benign'."""
    try:
        return bool(assess(text, context)["benign"])
    except Exception:  # noqa: BLE001 - fail safe: an assessment failure withholds learned behaviour
        return False


def is_reserved_turn(text: object, context: Iterable[object] = ()) -> bool:
    """The negation of :func:`is_benign_turn`: learned style/routing is neither captured from nor applied to this turn."""
    return not is_benign_turn(text, context)
