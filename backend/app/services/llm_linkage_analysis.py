"""LLM-Powered Case Linkage Analysis with File-Based Cache"""
import os, re, json, logging, time as _time
from typing import Optional
from datetime import date as date_type

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    load_dotenv(_env_path)
except ImportError: pass

logger = logging.getLogger(__name__)


class LLMResultCache:
    """File-based cache for LLM analysis results. Keyed on sorted case pair."""

    def __init__(self):
        self._cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
        self._cache_path = os.path.join(self._cache_dir, "llm_cache.json")
        self._cache = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self._cache_path):
                with open(self._cache_path, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
                logger.info("LLM cache loaded: %d pairs", len(self._cache))
            else: self._cache = {}
        except: self._cache = {}

    def _save(self):
        os.makedirs(self._cache_dir, exist_ok=True)
        with open(self._cache_path, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, indent=2, default=str)

    @staticmethod
    def _pair_key(a, b):
        pair = sorted([a.strip(), b.strip()])
        return pair[0] + "||" + pair[1]

    def get(self, a, b):
        key = self._pair_key(a, b)
        if key in self._cache:
            result = dict(self._cache[key])
            result["from_cache"] = True
            logger.info("LLM cache HIT: %s <-> %s", a, b)
            return result
        logger.info("LLM cache MISS: %s <-> %s", a, b)
        return None

    def put(self, a, b, result):
        key = self._pair_key(a, b)
        result["cached_at"] = _time.time()
        result["from_cache"] = False
        self._cache[key] = result
        self._save()

    def clear(self):
        self._cache = {}
        self._save()
        logger.info("LLM cache cleared")

    @property
    def size(self): return len(self._cache)

    @property
    def cache_path(self): return self._cache_path


llm_cache = LLMResultCache()


def clear_llm_cache():
    llm_cache.clear()


def get_cache_stats():
    return {"cached_pairs": llm_cache.size, "cache_file": llm_cache.cache_path}


SIMILARITY_MAP = {"none": 0.0, "weak": 0.33, "moderate": 0.66, "strong": 1.0}

ANALYSIS_PROMPT = """You are analyzing two Indian police case narratives to determine if they show genuine behavioral evidence of being committed by the same offender (serial pattern), as an investigative lead-generation aid -- NOT a determination of guilt.

CASE A ({case_number_a}):
{narrative_text_a}

CASE B ({case_number_b}):
{narrative_text_b}

Analyze whether these cases show genuine behavioral linkage. Do NOT flag surface-level word overlap as meaningful -- only flag it if the SAME WORD is describing the SAME KIND of behavior in comparable context.

Specifically assess:
1. SIGNATURE BEHAVIOR: genuinely similar psychologically-distinctive behaviors
2. MODUS OPERANDI: genuinely comparable approach/control/execution method
3. VICTIMOLOGY: genuinely similar victim profile/selection pattern
4. FALSE-POSITIVE CHECK: explicitly list surface similarities you are NOT counting as meaningful, and why

Return ONLY valid JSON:
{"linkage_score": <0-100>, "signature_similarity": "<none|weak|moderate|strong>", "mo_similarity": "<none|weak|moderate|strong>", "victimology_similarity": "<none|weak|moderate|strong>", "genuine_shared_behaviors": ["<behavior>"], "false_positive_words_ignored": ["<word + reason>"], "reasoning": "<2-3 sentence explanation>"}"""


PRE_FILTER_MAX_MONTHS = 18


def _parse_llm_json(raw):
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                candidate = match.group()
                opens = candidate.count("{") - candidate.count("}")
                closes = candidate.count("[") - candidate.count("]")
                candidate += "]" * max(0, closes) + "}" * max(0, opens)
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass
        try:
            score_match = re.search(r'"linkage_score"\s*:\s*(\d+)', text)
            if score_match:
                return {
                    "linkage_score": int(score_match.group(1)),
                    "signature_similarity": "none",
                    "mo_similarity": "none",
                    "victimology_similarity": "none",
                    "genuine_shared_behaviors": [],
                    "false_positive_words_ignored": [],
                    "reasoning": "(partial parse from truncated response)",
                }
        except Exception:
            pass
        logger.warning("Failed to parse LLM JSON: %s", text[:300])
        return None


def _validate_result(result):
    required = ["linkage_score", "signature_similarity", "mo_similarity",
                "victimology_similarity", "genuine_shared_behaviors",
                "false_positive_words_ignored", "reasoning"]
    for k in required:
        if k not in result:
            result[k] = 0 if k == "linkage_score" else [] if "words" in k or "behav" in k else "none" if "sim" in k else ""
    result["linkage_score"] = max(0, min(100, int(result.get("linkage_score", 0))))
    for f in ["signature_similarity", "mo_similarity", "victimology_similarity"]:
        v = result.get(f, "none").lower()
        result[f] = v if v in SIMILARITY_MAP else "none"
    if not isinstance(result.get("genuine_shared_behaviors"), list):
        result["genuine_shared_behaviors"] = []
    if not isinstance(result.get("false_positive_words_ignored"), list):
        result["false_positive_words_ignored"] = []
    return result


def _call_groq(prompt):
    """Call Groq API (Llama 3.1) - fastest, most generous free tier."""
    try:
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            return None
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=2048,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error("Groq API error: %s", e)
        return None


def _call_gemini(prompt):
    """Call Google Gemini API (fallback)."""
    try:
        from google import genai
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        if not api_key:
            return None
        client = genai.Client(api_key=api_key)
        chat = client.chats.create(
            model="gemini-3.6-flash",
            config=genai.types.GenerateContentConfig(temperature=0, max_output_tokens=2048),
        )
        return chat.send_message(prompt).text
    except Exception as e:
        logger.error("Gemini API error: %s", e)
        return None


def _call_llm(prompt):
    """Try providers in order: Groq (fastest) -> Gemini -> None."""
    raw = _call_groq(prompt)
    if raw:
        return raw, "groq"
    raw = _call_gemini(prompt)
    if raw:
        return raw, "gemini"
    return None, None
class ContextualHeuristicAnalyzer:
    SIG = {
        'object_placement': [
            (r'placed\s+(neatly|deliberately|carefully|gently)', 'deliberate'),
            (r'key\s+(?:found|placed|resting)\s+(?:on|beside|near|next to)', 'key_placement'),
            (r'(?:brass|metal)\s+key', 'brass_key'),
            (r'deliberately\s+(?:placed|left|positioned)', 'deliberate'),
        ],
        'dead_frequency': [
            (r'dead\s+frequency', 'dead_freq'),
            (r'tuned\s+to.*(?:dead|static|off[- ]air)', 'tuned_dead'),
            (r'radio.*(?:on|tuned|playing)', 'radio_on'),
            (r'(?:static|dead\s+air)', 'static'),
        ],
        'trophy_taking': [
            (r'missing\s+(?:item|object|thing|belonging)', 'missing_item'),
            (r'(?:took|taken|removed|stolen|missing)\s+(?:a\s+)?(?:item|mug|badge|folder|key)', 'took_item'),
        ],
        'victim_vulnerability': [
            (r'(?:found|found\s+dead)\s+(?:alone|by\s+herself|by\s+himself)', 'found_alone'),
            (r'(?:working|alone)\s+(?:at|in|during|after)\s+(?:night|late|evening)', 'working_late'),
            (r'no\s+(?:indication|evidence)\s+(?:of\s+)?(?:struggle|fighting|defense)', 'no_struggle'),
            (r'(?:doors?|entry)\s+were?\s+unlocked', 'unlocked'),
        ],
        'occupational_targeting': [
            (r'(?:radio|frequency|broadcast|station|transmission)', 'radio'),
            (r'(?:archive|archivist|records?|filing|catalog)', 'archive'),
            (r'(?:key|lock|security|access|locksmith)', 'locksmith'),
        ],
        'escalation': [
            (r'(?:interval|gap|period|spacing).*(?:increasing|growing|longer)', 'escalating'),
        ],
    }

    CTX = {
        'object_placement': ['body', 'victim', 'scene', 'near', 'beside'],
        'dead_frequency': ['radio', 'frequency', 'station', 'transmission', 'tuned'],
        'trophy_taking': ['missing', 'took', 'removed', 'gap', 'pegboard'],
        'victim_vulnerability': ['alone', 'late', 'night', 'unlocked', 'no struggle'],
        'occupational_targeting': ['radio', 'locksmith', 'archivist', 'frequency'],
        'escalation': ['interval', 'days', 'since', 'prior', 'escalat'],
    }

    MO = {
        'entry': [(r'unlocked|no\s+(?:forced\s+)?entry', 'unlocked_entry'), (r'forced\s+entry|broken', 'forced_entry')],
        'targeting': [(r'alone', 'alone'), (r'(?:late|night|evening)', 'vulnerable_hours'), (r'(?:isolated|rural|detached|secluded)', 'isolated')],
        'weapon': [(r'(?:rope|cord|wire|strap)', 'ligature'), (r'(?:knife|blade|sharp)', 'edged'), (r'(?:blunt|force|impact)', 'blunt_force')],
    }

    def analyze_context(self, text_a, text_b, case_a, case_b):
        tl_a, tl_b = text_a.lower(), text_b.lower()
        sig = {}
        for st, patterns in self.SIG.items():
            ma, mb = [], []
            ctx_kw = self.CTX.get(st, [])
            for pat, label in patterns:
                m = re.search(pat, tl_a)
                if m:
                    window = tl_a[max(0, m.start()-100):m.end()+100]
                    if any(k in window for k in ctx_kw):
                        ma.append(label)
                m = re.search(pat, tl_b)
                if m:
                    window = tl_b[max(0, m.start()-100):m.end()+100]
                    if any(k in window for k in ctx_kw):
                        mb.append(label)
            if ma and mb:
                sig[st] = len(set(ma) & set(mb)) / max(len(set(ma) | set(mb)), 1)
            else:
                sig[st] = 0.0
        mo = {}
        for mt, patterns in self.MO.items():
            ma, mb = [], []
            for pat, label in patterns:
                if re.search(pat, tl_a): ma.append(label)
                if re.search(pat, tl_b): mb.append(label)
            if ma and mb:
                mo[mt] = len(set(ma) & set(mb)) / max(len(set(ma) | set(mb)), 1)
            else:
                mo[mt] = 0.0
        sig_s = sum(sig.values()) / max(len(sig), 1)
        mo_s = sum(mo.values()) / max(len(mo), 1)
        genuine = ['Both cases show %s' % st.replace('_', ' ') for st in sig if sig[st] > 0]
        fps = []
        crime = {'body','victim','scene','found','death','killed','murder','crime','evidence','police','officer','case','investigation','suspect'}
        wa = set(re.findall(r'[a-z]{4,}', tl_a))
        wb = set(re.findall(r'[a-z]{4,}', tl_b))
        for w in list((wa & wb) - crime)[:5]:
            fps.append("'%s' -- surface overlap" % w)
        base = sig_s * 0.45 + mo_s * 0.30
        bonus = 0.10 if sum(1 for s in [sig_s, mo_s] if s > 0) >= 2 else 0.0
        ls = int(min(100, (base + bonus) * 100))
        def tl(s):
            if s >= 0.66: return 'strong'
            elif s >= 0.33: return 'moderate'
            elif s > 0: return 'weak'
            return 'none'
        rp = []
        if sig_s > 0.3: rp.append('Strong signature overlap (%.0f%%)' % (sig_s * 100))
        elif sig_s > 0: rp.append('Moderate signature overlap (%.0f%%)' % (sig_s * 100))
        else: rp.append('No meaningful signature overlap')
        if mo_s > 0.3: rp.append('Comparable MO (%.0f%%)' % (mo_s * 100))
        elif mo_s > 0: rp.append('Some MO similarities (%.0f%%)' % (mo_s * 100))
        if fps: rp.append('Rejected %d surface matches' % len(fps))
        return {
            'linkage_score': ls, 'signature_similarity': tl(sig_s), 'mo_similarity': tl(mo_s),
            'victimology_similarity': 'none', 'genuine_shared_behaviors': genuine[:5],
            'false_positive_words_ignored': fps[:5],
            'reasoning': '. '.join(rp) + '.' if rp else 'No significant behavioral overlap.',
        }


def llm_case_pair_analysis(text_a, case_number_a, text_b, case_number_b):
    cached = llm_cache.get(case_number_a, case_number_b)
    if cached:
        return cached
    api_key = os.environ.get('GROQ_API_KEY', '') or os.environ.get('GOOGLE_API_KEY', '')
    if api_key:
        prompt = ANALYSIS_PROMPT.replace('{case_number_a}', case_number_a).replace('{narrative_text_a}', text_a[:8000]).replace('{case_number_b}', case_number_b).replace('{narrative_text_b}', text_b[:8000])
        raw, provider = _call_llm(prompt)
        if raw:
            result = _parse_llm_json(raw)
            if result:
                result['backend'] = provider or 'llm'
                validated = _validate_result(result)
                llm_cache.put(case_number_a, case_number_b, validated)
                return validated
        logger.warning('LLM failed, using heuristic')
    analyzer = ContextualHeuristicAnalyzer()
    result = analyzer.analyze_context(text_a, text_b, case_number_a, case_number_b)
    result['backend'] = 'heuristic' if not api_key else 'llm_fallback'
    llm_cache.put(case_number_a, case_number_b, result)
    return result


def pre_filter_pairs(case_data, max_months=PRE_FILTER_MAX_MONTHS):
    n = len(case_data)
    if n < 2:
        return []
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            a, b = case_data[i], case_data[j]
            if not a.get('text') or len(a['text'].strip()) < 50:
                continue
            if not b.get('text') or len(b['text'].strip()) < 50:
                continue
            if a.get('date_str') and b.get('date_str'):
                try:
                    da = date_type.fromisoformat(a['date_str'])
                    db = date_type.fromisoformat(b['date_str'])
                    if abs((da - db).days) / 30 > max_months:
                        continue
                except (ValueError, TypeError):
                    pass
            pairs.append((i, j))
    return pairs
