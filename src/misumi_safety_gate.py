"""Belt-and-braces safety BLOCK for learned adaptation in Misumi (round-5 repair, redesigned in round 6, 2026-10-16).

Learned behaviour (an approved persona style such as "keep answers brief", or a learned routing overlay such as "send kitchen
questions to Jin") is a convenience; on an emergency it can do harm. Round 6 places the PRIMARY protection where recognition is
strongest - in the model-facing style text itself: every learned style block carries a fixed carve-out (``STYLE_CARVE_OUT`` in
``src.misumi_persona_state``) telling the model that the preferences never apply to urgent, safety, medical, legal, financial
or emotional-distress matters or whenever the person seems in difficulty. Learned routing cannot rely on the model, so it is
advisory (see ``RoutingAdaptationStore.apply_learned_overlays``).

This module is the SECONDARY layer: a precision-first lexicon that BLOCKS learned style, learned routing, capture and offers
when a turn plainly matches an emergency phrasing. It deliberately does not try to be complete: a keyword list cannot be both
complete and precise, and every broad keyword over-blocks ordinary household turns ("the toast is burnt", "bleed a radiator",
"hit me with a fun fact"). Patterns are exact words/phrases, verb + person/substance combinations and a small typo tolerance
for long emergency terms only. Measured rates on held-out sets are reported in the PR, not claimed here.

``is_benign_turn`` is False when ANY of these holds (the whole turn is scanned, never a prefix):

* an emergency phrasing matches (emergency services, collapse and unresponsiveness, breathing and choking, colour change,
  chest pain, bleeding, falls and head injury, burns and scalds, poisoning and ingestion, medicine overdoses and dosing, gas/CO,
  fire/smoke, electricity, drowning, self-harm and suicidal phrasing including common slang, violence and abuse with a person,
  animal bites, missing children; plus common Spanish, French, German, Italian, Portuguese and Dutch terms);
* a long emergency term appears with a small typo ("unconcious", "chocking", "ambulence");
* a reserved governance matter is named (ratification, Level 5/6, household values/standards/boundaries, privacy, memory
  retention);
* the turn contains letters outside the Latin script, or is too long to assess.

HONEST LIMITS: this is a lexicon, i.e. a mitigation. It misses natural paraphrases (that is why the model-facing carve-out is
primary) and flags some harmless turns (that only withholds learned style/routing on that turn). A model-based or
trained-classifier gate is FUTURE WORK.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

MAX_ASSESS_CHARS = 200_000  # beyond this a turn is simply not assessed as benign (fail-safe, bounded cost)

_TYPOGRAPHIC = str.maketrans({"’": "'", "‘": "'", "‛": "'", "ʼ": "'", "“": '"', "”": '"',
                              "„": '"', "–": "-", "—": "-", " ": " ", " ": "\n", " ": "\n"})


def normalise(text: object) -> str:
    """Lower-case, typographic quotes folded, accents removed ('lejía' -> 'lejia', 'Küche' -> 'kuche'), 'ß' -> 'ss'."""
    folded = unicodedata.normalize("NFKD", str(text or "").translate(_TYPOGRAPHIC))
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return folded.replace("ß", "ss").lower()


_LEET = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})
# Three or more single letters in a row, separated by spaces or punctuation ("g a s", "f.i.t", "c-h-o-k-i-n-g").
_SEP = r"[^a-z0-9]+"  # ANY run of other characters between two letters ("g+a+s", "g=a=s", "g!a!s", "g/a/s")
_SPACED_RUN = re.compile(rf"(?<![a-z0-9])[a-z0-9](?:{_SEP}[a-z0-9]){{2,}}(?![a-z0-9])")
# Short chunks ("fi re", "ga s", "a fi t"): two or more tokens of at most two characters. A stem counts here only when it begins and
# ends at a token boundary, so "if i re-send" does not read as "fire" but "fi re" does.
_CHUNK_RUN = re.compile(rf"(?<![a-z0-9])[a-z0-9]{{1,2}}(?:{_SEP}[a-z0-9]{{1,2}})+(?![a-z0-9])")
# Stems checked inside a spaced-out run (after the letters are joined).
_RUN_STEMS = (
    "gas", "fire", "fit", "999", "911", "112", "111", "sos", "help", "ambulance", "bleed", "blood", "chok", "breath", "unconscious",
    "overdos", "suicid", "poison", "burn", "scald", "drown", "collaps", "seizure", "stroke", "faint", "hurt", "kill", "die",
    "dead", "pain", "smoke", "shock", "swallow", "knife", "gun", "attack", "abuse", "unresponsive", "heartattack", "cprs",
)
# Long, distinctive stems are also looked for in the whole text with every separator removed, on token boundaries ("cho king").
_LONG_STEMS = (
    "ambulance", "unconscious", "overdose", "suicide", "drowning", "bleeding", "choking", "collapsed", "seizure", "poisoning",
    "poisoned", "anaphyl", "heartattack", "strangle", "stabbed", "unresponsive", "notbreathing", "cantbreathe", "999", "911",
)


def _collapse(match: "re.Match[str]", mode: int) -> str:
    letters = re.findall(r"[a-z0-9]", match.group())
    if mode == 1 and len(letters) > 3 and letters[0] in "ai":
        return f"{letters[0]} {''.join(letters[1:])}"  # keep a leading article/pronoun apart: "a f i t" -> "a fit"
    return "".join(letters)


def _obfuscation_variants(text: str) -> tuple[str, ...]:
    """Bounded extra readings for common disguises; the ordinary reading is kept by the caller for precision."""
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    forms = []
    for mode in (0, 1):
        form = _SPACED_RUN.sub(lambda match, mode=mode: _collapse(match, mode), text)
        form = re.sub(r"(?<!\w)[a-z0-9@$]+(?!\w)", lambda match: match.group().translate(_LEET)
                      if re.search(r"[a-z]", match.group()) else match.group(), form)
        forms.append(re.sub(r"([a-z])\1{2,}", r"\1\1", form))
    return tuple(dict.fromkeys(forms))


def _obfuscation_variant(text: str) -> str:
    return _obfuscation_variants(text)[0]


def _spaced_hazard(text: str) -> str | None:
    """The hazard stem hidden by spacing or punctuation, if any: inside a run of single characters (any stem), inside a run of
    short chunks (a stem on token boundaries), or - for the long distinctive stems - anywhere once all separators are removed."""
    for match in _SPACED_RUN.finditer(text):
        raw = "".join(re.findall(r"[a-z0-9]", match.group()))
        for variant in (raw, raw.translate(_LEET)):
            for stem in _RUN_STEMS:
                if stem in variant:
                    return stem
    for match in _CHUNK_RUN.finditer(text):
        tokens = re.findall(r"[a-z0-9]+", match.group())
        bounds, total = {0}, 0
        for token in tokens:
            total += len(token)
            bounds.add(total)
        raw = "".join(tokens)
        for variant in (raw, raw.translate(_LEET)):
            for stem in _RUN_STEMS:
                at = variant.find(stem)
                while at != -1:
                    if at in bounds and at + len(stem) in bounds:
                        return stem
                    at = variant.find(stem, at + 1)
    tokens = re.findall(r"[a-z0-9]+", text)
    despaced = "".join(tokens)
    if not any(stem in despaced for stem in _LONG_STEMS):
        return None
    bounds, total = {0}, 0
    for token in tokens:
        total += len(token)
        bounds.add(total)
    for stem in _LONG_STEMS:  # a stem must begin AND end on token boundaries: "tech ok in g" is not "choking"
        at = despaced.find(stem)
        while at != -1:
            if at in bounds and at + len(stem) in bounds:
                return stem
            at = despaced.find(stem, at + 1)
    return None


# Everyday idioms that share words with emergencies; removed before matching (precision).
_IDIOMS = re.compile(
    r"\b(?:light(?:ing)?|lit|start(?:ing|ed)?|build(?:ing)?|stok(?:e|ing)|make|made|log)\s+(?:the\s+|a\s+|up\s+the\s+)?fire\b|"
    r"\bfire\s+(?:up|off|away|pit|place|side|wood|works?|fighters?\s+(?:game|toy))\b|\bfireplace\b|\bfirewood\b|"
    r"\bbleed(?:ing)?\s+(?:the\s+|a\s+|my\s+)?(?:radiators?|brakes?|system|pipes?|heating|valve)\b|"
    r"\bburnt\s+(?:ends?|toast|sugar|butter|orange|umber|offering)\b|\b(?:toast|cake|rice|pan|dinner|bacon)\s+(?:is|was|got)\s+burnt\b|"
    r"\bsafety\s+(?:pins?|glasses|goggles|net|belt|razor|gate|catch|car)\b|\bpain\s+(?:au|aux)\s+\w+|"
    r"\bfell\s+(?:behind|asleep|apart|in\s+love|through\s+the\s+cracks|for\s+it|short)\b|"
    r"\bhit\s+me\s+(?:up|with)\b|\bshoot\s+me\s+(?:a|an|the)\b|\bkill(?:ing)?\s+(?:time|it)\b|"
    r"\bdying\s+(?:to|for)\b|\bto\s+die\s+for\b|\bcracking\s+up\b|\bblown\s+away\b|\bdead\s+(?:tired|good|easy)\b"
)

_WHO = (r"(?:my|our|his|her|their|the|a)\s+(?:\w+\s+)?(?:son|daughter|baby|toddler|child|kid|boy|girl|dad|father|mum|mom|mother|"
        r"husband|wife|partner|grandad|granddad|grandpa|grandma|nan|gran|brother|sister|friend|mate|neighbou?r|stepdad|stepmum|"
        r"boyfriend|girlfriend|ex|uncle|aunt)|\b(?:he|she|they|someone|somebody|i|we)\b")
_HARMFUL = (r"(?:bleach|cleaner|cleaning\s+(?:product|stuff|spray)|detergent|chemicals?|pods?|capsules?|tablets?|pills?|medicine|"
            r"meds|batter(?:y|ies)|magnets?|antifreeze|white\s+spirit|weed\s?killer|rat\s+poison|slug\s+pellets|dishwasher\s+\w+|"
            r"washing\s+(?:up\s+)?(?:liquid|powder)|laundry\s+\w+|e-?liquid|lighter\s+fluid|petrol|drain\s+cleaner|"
            r"stuff\s+(?:under|from)\s+the\s+sink|something\s+from\s+under\s+the\s+sink)")
_OBJ = r"(?:me|us|him|her|them|my\s+\w+|our\s+\w+|the\s+(?:kids?|children|baby))\b"
_ASSAULT = (r"(?:hits?|hitting|beats?|beating|beaten|punch(?:es|ed|ing)?|kick(?:s|ed|ing)|slap(?:s|ped|ping)|chok(?:es|ed|ing)|"
            r"strangl\w*|throttl\w*|shov(?:es|ed|ing)|push(?:es|ed)|grabb(?:ed|ing)|threaten(?:s|ed|ing)?|hurts?|hurting|hurt|"
            r"attack(?:s|ed|ing)|stab(?:s|bed|bing)|shot|rap(?:es|ed|ing)|molest\w*|touch(?:es|ed|ing))")

_DOMAINS: tuple[tuple[str, str], ...] = (
    ("emergency", r"\b(?:emergenc(?:y|ies)|ambulance|paramedics?|999|911|112|a\s*&\s*e|poison\s+control|nhs\s+111|"
                  r"call\s+(?:an?\s+)?(?:ambulance|999|911|doctor|the\s+police))\b|\bhelp\s+(?:me|us)\s*(?:!|please|quick|now)"),
    ("collapse", r"\bcollaps\w*|\bkeeled\s+over\b|\bunconscious\w*|\bunresponsive\b|\bpassed\s+out\b|\bfaint(?:ed|ing)\b|"
                 r"\bblack(?:ed)?\s+out\b|\b(?:is|was|he'?s|she'?s|they'?re)\s*(?:n'?t|\s+not)\s+(?:moving|responding|breathing|waking)\b|"
                 r"\b(?:won'?t|can'?t|cannot)\s+(?:wake\s+(?:him|her|them)|wake\s+up|be\s+woken)\b|\bnot\s+waking\s+up\b"),
    ("breathing", r"\b(?:can'?t|cannot|can\s+not|struggl\w*\s+to|unable\s+to)\s+breath\w*|\bnot\s+breathing\b|\bstopped\s+breathing\b|"
                  r"\bshort(?:ness)?\s+of\s+breath\b|\bchok(?:e|ed|es|ing)\b|\bturn(?:ing|ed|s)?\s+(?:blue|grey|gray|purple)\b|"
                  r"\b(?:gone|going|went)\s+(?:a\s+)?(?:funny\s+|bit\s+)?(?:blue|grey|gray|purple)\b|"
                  r"\blips?\s+(?:are|is|look|looks|have\s+gone)\s+(?:blue|grey|gray)\b|\bthroat\s+(?:is\s+)?(?:closing|swelling)\b|"
                  r"\b(?:lips?|tongue|throat|face|eyes?)\s+(?:(?:are|is|has|have|keeps?)\s+)?(?:swelling|swollen|swelled)\b|\bstiff\s+neck\b"),
    ("cardiac-stroke", r"\bchest\s+(?:pains?|tight\w*|pressure)\b|\b(?:pain|tight\w*|pressure)\s+in\s+(?:my|his|her|their)\s+chest\b|"
                       r"\bheart\s+attack\b|\bcardiac\s+arrest\b|\bstroke\b(?!\s+(?:the|a|my|his|her|its|of\s+luck|of\s+genius))|"
                       r"\bseizures?\b|\bconvuls\w*|\bhaving\s+a\s+fit\b|\bana(?:ph|f)(?:y|i)la(?:x|ct)\w*|\ballergic\s+reaction\b"),
    ("bleeding-injury", r"\b(?:is|are|keeps?|won'?t\s+stop|started|still|been)\s+bleeding\b|\bbleeding\s+(?:a\s+lot|heavily|badly|from|everywhere)\b|"
                        r"\b(?:lots?|loads)\s+of\s+blood\b|\bblood\s+(?:everywhere|pouring|gushing)\b|\b(?:coughing|vomiting)\s+(?:up\s+)?blood\b|"
                        r"\b(?:fell|fallen|falls|fall)\s+(?:down|off|over|from|out\s+of|through|into|onto)\b|"
                        r"\b(?:hit|banged|bumped|smashed)\s+(?:his|her|my|their)\s+head\b|\bhead\s+injur\w*|\bconcuss\w*|"
                        r"\bbroken\s+(?:bone|arm|leg|wrist|ankle|neck|back|hip)\b|\b(?:burn(?:ed|t|s)?|scald(?:ed|s)?)\s+(?:my|his|her|their|him|herself|himself|myself)\b|"
                        r"\bscald(?:ed|ing)\b|\bsevere\s+burns?\b|\b(?:severe|terrible|crushing|agonising|excruciating|unbearable)\s+pain\b"),
    ("poisoning", r"\bswallow(?:ed|s|ing)\b|\bpoison(?:ed|ing|ous)\b|\bpoisen\w*|\bingest(?:ed|ing)\b|\bbleach\b|\bantifreeze\b|\boverdos\w*|"
                  r"\b(?:button|coin)[- ]?(?:cell|batter(?:y|ies))\b|"
                  r"\b(?:drank|drunk|drink(?:s|ing)?|ate|eaten|licked|chewed|sucked|got\s+into|has\s+had|had\s+some)\b[^.!?\n]{0,50}"
                  r"\b" + _HARMFUL + r"|\b(?:too\s+many|too\s+much|double\s+dose|extra\s+dose|whole\s+(?:packet|bottle|box))\b[^.!?\n]{0,30}"
                  r"\b(?:pills|tablets|paracetamol|ibuprofen|calpol|insulin|medicine|meds|of\s+(?:his|her|my)\s+\w+)"),
    ("medicine-dosing", r"\b(?:paracetamol|acetaminophen|ibuprofen|calpol|nurofen|aspirin|tylenol|codeine|morphine|tramadol|insulin|"
                        r"epi-?pens?|antidepressants?)\b|\b(?:how\s+much|what\s+dose)\b[^.!?\n]{0,30}\b(?:give|take|medicine|syrup)\b"),
    ("medical-matter", r"\b(?:medications?|medicines?|prescriptions?|dos(?:e|es|age|ing)|allerg(?:y|ies|ic)|first[- ]aid|medical|"
                       r"symptoms?|diagnos\w*)\b"),
    ("gas-co", r"\bgas\w*\s+(?:leak\w*|smell\w*|escap\w*|hiss\w*)|\b(?:smell\w*|stink\w*|whiff|reek\w*)\b[^.!?\n]{0,30}\bgas\b|"
               r"\bgas\b[^.!?\n]{0,30}\b(?:smell\w*|stink\w*|whiff|leak\w*)|\bleak\w*\s+gas\b|\bcarbon\s+monoxide\b|"
               r"\bco\s+(?:alarm|detector|poisoning|leak)\b|\brotten\s+eggs?\b"),
    ("fire-smoke", r"\b(?:on|caught|catch(?:es|ing)?)\s+fire\b|\bfire\s+(?:in\s+the|spreading|alarm|brigade|engine|service)\b|"
                   r"\b(?:house|kitchen|chimney|electrical|chip\s+pan|grease|oven)\s+fire\b|\bflames?\b|\bablaze\b|\balight\b|"
                   r"\bchip\s+pan\b[^.!?\n]{0,30}\b(?:gone\s+up|went\s+up|caught|flames|alight)\b|"
                   r"\b(?:pan|pot|oven|toaster|hob|grill|something|it)\s+(?:is|was|'s)\s+(?:burning|smoking)\b|"
                   r"\bsmoke\s+(?:alarm|detector|coming|everywhere|pouring|from)\b|\b(?:full\s+of|filling\s+(?:up\s+)?with|thick)\s+smoke\b|"
                   r"\bsmoking\s+(?:socket|plug|oven|pan|wire|appliance|charger|heater)\b|\bburning\s+smell\b|"
                   r"\bsmell\w*\s+(?:of\s+)?(?:burning|smoke)\b|\bexplo(?:ded|sion)\b|\bsparks?\s+(?:coming|flying|from)\b|\bsparking\b"),
    ("electric", r"\belectr\w*\s+shock\w*|\belectrocut\w*|\bzapp(?:ed|ing)\b|\bshock(?:ed)?\s+(?:from|off|by)\s+(?:the|a)\b|"
                 r"\bgot\s+(?:a\s+)?(?:bad\s+|nasty\s+)?shock\b|\blive\s+wires?\b|\bexposed\s+wires?\b|"
                 r"\b(?:socket|plug|outlet|switch|heater|charger)\b[^.!?\n]{0,30}\b(?:shock|spark|smok|melt|zap)\w*"),
    ("drowning", r"\bdrown\w*|\bface\s+down\s+in\s+(?:the\s+)?(?:water|pond|pool|bath|river)\b|"
                 r"\b(?:fell|fallen)\s+(?:in|into|through)\s+(?:the\s+)?(?:pool|pond|river|canal|sea|lake|ice|water)\b|"
                 r"\bunder\s+(?:the\s+)?water\s+(?:too\s+long|and)\b"),
    ("self-harm", r"\bsuicid\w*|\bunalive\b|\b(?:kms|kys)\b|\bkill\w*\s+(?:my|him|her|them|your)sel(?:f|ves)\b|"
                  r"\bend(?:ing)?\s+(?:it\s+all|my\s+life|(?:my|his|her)\s+own\s+life|things|it)\b(?!\s+(?:here|there|now|with|for|on))|"
                  r"\b(?:take|taking)\s+(?:my|his|her)\s+(?:own\s+)?life\b|\bself[- ]?harm\w*|\bhurt\w*\s+(?:my|him|her|them)sel(?:f|ves)\b|"
                  r"\bcut(?:ting)?\s+(?:my|him|her)sel(?:f|ves)\b|\bwant(?:s|ed)?\s+to\s+die\b|\b(?:don'?t|do\s+not|dont)\s+want\s+to\s+"
                  r"(?:live|be\s+alive|be\s+here|wake\s+up|exist)\b|\bno\s+(?:reason|point)\s+(?:to|in)\s+(?:live|living|going\s+on)\b|"
                  r"\bbetter\s+off\s+(?:dead|without\s+me)\b|\bcan'?t\s+go\s+on\b|\bnot\s+worth\s+living\b"),
    ("violence-abuse", r"(?:" + _WHO + r")\s+(?:\w+\s+){0,3}?" + _ASSAULT + r"\s+" + _OBJ + r"|"
                       r"\btouch(?:es|ed|ing)\s+me\b|\bcom(?:es|ing)\s+into\s+my\s+room\s+at\s+night\b|"
                       r"\b(?:domestic\s+(?:abuse|violence)|abus(?:ed|ing|ive|er)|assault(?:ed|ing)?|rap(?:e|ed)|molest\w*|stalk(?:ing|er|ed)|"
                       r"strangl\w*|throttl\w*|intruder|burglar\w*|break(?:ing)?\s+in(?:to)?|broke\s+in(?:to)?)\b|"
                       r"\b(?:scared|afraid|terrified|frightened)\s+(?:of\s+)?(?:him|her|my\s+\w+|them)\b|"
                       r"\b(?:with|has|pulled|holding)\s+a\s+(?:knife|gun|weapon)\b|\bstabbed\b|\bthreaten(?:s|ed|ing)\s+(?:to|me|us)\b"),
    ("animal-bite", r"\b(?:bit|bites|bitten|mauled|stung)\s+(?:by\s+)?" + _OBJ + r"|\bbitten\s+by\b|"
                    r"\b(?:dog|cat|snake|spider|tick|wasp|bee|jellyfish|adder|fox|rat)\s+(?:bit|bite|bitten|sting|stung|attack\w*)\b"),
    ("child-safety", r"\b(?:missing|lost|can'?t\s+find|cannot\s+find)\s+(?:my|our|the)\s+(?:son|daughter|child|kid|toddler|baby|boy|girl)\b|"
                     r"\b(?:son|daughter|child|kid|toddler|baby)\s+(?:is\s+|has\s+gone\s+)?missing\b|\bshaken\s+baby\b"),
    ("non-english", r"\b(?:huele\s+a\s+gas|olor\s+a\s+gas|fuga\s+de\s+gas|incendio|humo|veneno|envenen\w*|lejia|ahog\w*|sangr\w*|"
                    r"emergencia|ambulancia|dolor\s+(?:de|en\s+el)\s+pecho|no\s+puede\s+respirar|no\s+respira|me\s+quiero\s+morir|"
                    r"bebio|se\s+trago|desmay\w*|inconsciente|"
                    r"odeur\s+de\s+gaz|fuite\s+de\s+gaz|incendie|fumee|empoisonn\w*|eau\s+de\s+javel|javel|noy(?:e|ade|er)\w*|saign\w*|"
                    r"urgences?|douleur\s+thoracique|douleur\s+(?:a|dans)\s+la\s+poitrine|respire\s+(?:pas|plus)|me\s+tuer|"
                    r"envie\s+de\s+mourir|evanoui\w*|inconscient\w*|il\s+me\s+frappe|"
                    r"gasgeruch|gasleck|riecht\s+nach\s+gas|feuer|rauch|vergift\w*|bleiche|ertrink\w*|ertrunken|notfall|notarzt|"
                    r"krankenwagen|rettungswagen|brustschmerz\w*|keine\s+luft|atmet\s+nicht|selbstmord|umbringen|verschluckt|"
                    r"bewusstlos|ohnmacht\w*|"
                    r"odore\s+di\s+gas|fuga\s+di\s+gas|veleno|avvelen\w*|candeggina|ingerit[oa]|ingoiat[oa]|detersiv[oi]|annega\w*|"
                    r"emergenza|ambulanza|dolore\s+al\s+petto|non\s+respira|"
                    r"cheiro\s+a\s+gas|vazamento\s+de\s+gas|fumaca|lixivia|agua\s+sanitaria|afog\w*|"
                    r"ruik\s+gas|gaslucht|gaslek|vergif\w*|noodgeval|borstpijn|ademt\s+niet|zelfmoord)\b"),
)
_COMPILED: tuple[tuple[str, re.Pattern[str]], ...] = tuple((d, re.compile(p)) for d, p in _DOMAINS)

# Reserved governance matters: phrase-level, so "put these values in a spreadsheet" or "safety pins" are not reserved.
_RESERVED = re.compile(
    r"\bratif(?:y|ied|ication)\b|\blevel\s*(?:5|five|6|six)\b|"
    r"\b(?:household|family|house|our|my|core|shared|personal|seed[- ]order)\s+(?:\w+\s+)?(?:values?|standards?|boundar(?:y|ies)|rules?)\b|"
    r"\b(?:privacy|data\s+retention|retention\s+(?:policy|mode|period))\b|\bmemory\s+(?:retention|decisions?|policy|capture)\b|"
    r"\bsafety\s+(?:advice|concern|issue|plan|risk|information|warning)s?\b"
)

# Typo tolerance only for LONG emergency terms, and graded: insertion/deletion (>= 7 letters), adjacent swap (>= 8),
# substitution (>= 9). So "chocking" -> choking and "unconcious" -> unconscious match, but "cooked" (6) never matches "choked",
# "cooking" never matches "choking" (a substitution on a 7-letter word), and "overdone" never matches "overdose".
_FUZZY_TERMS = (
    "swallowed", "swallowing", "poisoned", "poisoning", "overdose", "overdosed", "unconscious", "unresponsive", "collapsed",
    "seizure", "breathing", "ambulance", "emergency", "suicide", "suicidal", "anaphylaxis", "anaphylactic", "electrocuted",
    "choking", "strangled", "throttled", "carbon monoxide",
)


def _near(token: str, term: str) -> bool:
    lt, lw = len(token), len(term)
    if lw < 7 or token == term:
        return token == term
    if abs(lt - lw) == 1:
        short, long_ = (token, term) if lt < lw else (term, token)
        return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))
    if lt != lw:
        return False
    diffs = [i for i in range(lt) if token[i] != term[i]]
    if len(diffs) == 2 and lw >= 8 and diffs[1] == diffs[0] + 1 \
            and token[diffs[0]] == term[diffs[1]] and token[diffs[1]] == term[diffs[0]]:
        return True
    return len(diffs) == 1 and lw >= 9


def _fuzzy_hit(text: str) -> str | None:
    tokens = set(re.findall(r"[a-z]{6,}", text))
    for term in _FUZZY_TERMS:
        if " " in term:
            continue
        for token in tokens:
            if abs(len(token) - len(term)) <= 1 and token != term and _near(token, term):
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
    """Why a turn is or is not benign: {'benign': bool, 'reasons': [...]} (reasons empty only when benign).

    ``context`` is only for text that IS the user's own words (for example an earlier part of the same turn). Interface or
    device context must not be passed here: a reserved word in it would block every turn.
    """
    parts = [str(text or "")] + [str(item) for item in context if item]
    raw = "\n".join(parts)
    if len(raw) > MAX_ASSESS_CHARS:
        return {"benign": False, "reasons": ["too-long-to-assess"]}
    norm = normalise(raw)
    forms = tuple(dict.fromkeys((_IDIOMS.sub(" ", form) for form in (norm, *_obfuscation_variants(norm)))))
    reasons = [domain for domain, pattern in _COMPILED if any(pattern.search(form) for form in forms)]
    hidden = _spaced_hazard(norm)
    if hidden is not None:
        reasons.append(f"obfuscated:{hidden}")
    if any(_RESERVED.search(form) for form in forms):
        reasons.append("reserved-matter")
    hit = next((hit for form in forms if (hit := _fuzzy_hit(form)) is not None), None)
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
    """True ONLY when no block pattern matches. Any error also means 'not benign'."""
    try:
        return bool(assess(text, context)["benign"])
    except Exception:  # noqa: BLE001 - fail safe: an assessment failure withholds learned behaviour
        return False


def is_reserved_turn(text: object, context: Iterable[object] = ()) -> bool:
    """The negation of :func:`is_benign_turn`: learned style/routing is neither captured from nor applied to this turn."""
    return not is_benign_turn(text, context)


# ---------------------------------------------------------------- round 7: a RECALL-FIRST gate for learned ROUTING only
#
# Withholding a learned route costs almost nothing (the deterministic base route still answers), while following a learned cue
# on a missed emergency can hand the lead to the wrong persona. So learned routing is withheld on any turn that mentions a
# hazard, an injury or medical matter, urgency or distress, a substance, violence, a vehicle, someone missing or trapped - or a
# person together with a body part. Heavy over-blocking is accepted here and ONLY here (style uses the precision block above
# plus the model-facing carve-out). Measured rates on held-out sets are reported in the PR.
_R_PERSON = (r"\b(?:my|our|his|her|their|the|a)\s+(?:\w+\s+)?(?:son|daughter|baby|babies|toddler|child|children|kids?|boy|girl|"
             r"dad|father|mum|mom|mother|husband|wife|partner|grand\w+|nan|gran|brother|sister|friend|mate|flatmate|neighbou?r|"
             r"step\w+|boyfriend|girlfriend|ex|uncle|aunt|nephew|niece|cousin|teen\w*|man|woman|someone|dog|cat)\b|"
             r"\b(?:he|she|they|someone|somebody|everyone|i'?m|i\s+am|i\s+feel|i\s+can'?t|i'?ve|me|his|her|their|your)\b")
_R_BODY = (r"\b(?:head|neck|chest|arms?|legs?|hands?|fingers?|thumbs?|foot|feet|toes?|face|eyes?|mouth|throat|tongue|lips?|"
           r"stomach|belly|tummy|back|skin|bones?|ankles?|wrists?|hips?|knees?|heart|lungs?|brain|soft\s+spot|vision|teeth|nose|ears?)\b")
_R_HAZARD = (
    r"\b(?:hurt\w*|pain(?:s|ful|fully|killers?)?|ache[sd]?|aching|injur\w*|bleed\w*|blood\w*|burn\w*|burnt|scald\w*|swell\w*|swollen|bruis\w*|broke\w*|"
    r"fractur\w*|sprain\w*|wounds?|rash\w*|fever\w*|temperature|vomit\w*|sick|faint\w*|dizz\w*|collaps\w*|unconscious\w*|"
    r"wake|waking|chok\w*|breath\w*|wheez\w*|asthma|allerg\w*|seizur\w*|fits?|stroke|attack\w*|shock\w*|poison\w*|swallow\w*|"
    r"overdos\w*|pills?|tablets?|medic\w*|meds|dose\w*|dosage|calpol|paracetamol|ibuprofen|inhaler|insulin|pregnan\w*|labour|"
    r"fell|fall\w*|trip\w*|slipp?\w*|floor|limp|floppy|blue|grey|gray|purple|pale|confus\w*|slurr\w*|numb\w*|blurr\w*|"
    r"help|urgent\w*|emergenc\w*|quick(?:ly)?|asap|999|911|112|111|ambulance|hospital|a\s*&\s*e|doctor|gp|nurse|police|"
    r"dying|die|died|dead|death|kill\w*|suicid\w*|panic\w*|scared|terrified|afraid|frighten\w*|cope|coping|alone|hopeless|"
    r"worthless|better\s+without\s+me|end\s+(?:it|everything|things)|bleach|cleaner|chemical\w*|detergent|batter(?:y|ies)|magnets?|"
    r"lamp\s+oil|hot\s+oil|white\s+spirit|antifreeze|gas|smoke\w*|smoulder\w*|smold\w*|fire|flames?|alight|spark\w*|melt\w*|"
    r"explod\w*|explosion|hiss\w*|leak\w*|electr\w*|wires?|cables?|sockets?|plugs?|extension\s+lead|lighter|boiling|scalding|"
    r"hit|beat\w*|punch\w*|kick\w*|slap\w*|stab\w*|threat\w*|violen\w*|abus\w*|assault\w*|shout\w*|threw|throw\w*|weapon\w*|"
    r"gun|follow\w*|stalk\w*|blackmail\w*|bull(?:y|ied|ying)|grabb\w*|push\w*|car|cars|bike|road|traffic|crash\w*|"
    r"missing|lost|trapped|stuck|locked\s+in|caught\s+in|drown\w*|water|pond|pool|bath|drunk|drank|drink\w*|ate|eaten|"
    r"party|taken\s+something|cut\s+(?:open|deep|badly|(?:him|her|my|them|your)sel\w*|his|her|my|their)|"
    r"gasp\w*|fitting|foam\w*|roar\w*|(?:not|isn'?t|stopped|won'?t\s+stop)\s+(?:crying|responding|moving|waking)|"
    r"respond\w*|unrespons\w*|(?:worst|terrible|sudden|thunderclap)\s+(?:ever\s+)?headache|headache|"
    r"lying\s+(?:on|in|there|still|face)|rolled\s+off|roll\w*\s+off|seiz\w*|convuls\w*|fit\b)\b"
)
_R_PERSON_RE, _R_BODY_RE, _R_HAZARD_RE = (re.compile(p) for p in (_R_PERSON, _R_BODY, _R_HAZARD))


def routing_risk(text: object) -> list[str]:
    """Why a learned ROUTE must be withheld on this turn ([] only when no risk signal is present). Recall-first by design."""
    try:
        norm = normalise(text)
        if len(norm) > MAX_ASSESS_CHARS:
            return ["too-long-to-assess"]
        reasons = []
        forms = tuple(dict.fromkeys((norm, *_obfuscation_variants(norm))))
        hidden = _spaced_hazard(norm)
        if hidden is not None:
            reasons.append(f"obfuscated:{hidden}")
        hazard = next((match for form in forms if (match := _R_HAZARD_RE.search(form)) is not None), None)
        if hazard:
            reasons.append(f"hazard:{hazard.group(0)}")
        if any(_R_PERSON_RE.search(form) and _R_BODY_RE.search(form) for form in forms):
            reasons.append("person+body")
        if not is_benign_turn(text):
            reasons.append("safety-block")
        return reasons
    except Exception:  # noqa: BLE001 - fail safe: an assessment failure withholds the learned route
        return ["assessment-failed"]


def withhold_learned_route(text: object) -> bool:
    """True when a learned routing overlay must not be applied to this turn (the base route answers instead)."""
    return bool(routing_risk(text))
