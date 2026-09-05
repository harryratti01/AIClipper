import math
import re


# ============================================================
# TEXT / POSITION HELPERS
# ============================================================

def clean_word(word):
    return word.lower().strip(".,!?;:\"'()[]{}")


def get_relative_position(candidate, word):
    return max(
        0.0,
        word["start"] - candidate["start"]
    )


# ============================================================
# POSITION WEIGHTS
# ============================================================

def opening_weight(position):
    """
    Questions and curiosity are most valuable near the opening.
    Weight falls smoothly as the signal occurs later.
    """
    return 1.0 + 2.0 * math.exp(-position / 6.0)


def engagement_weight(position):
    """
    Engagement matters throughout the clip,
    but earlier engagement receives an advantage.
    """
    return 1.0 + 1.3 * math.exp(-position / 10.0)


def emotion_weight(position):
    """
    Emotion remains useful throughout the clip,
    so its positional decay is slower.
    """
    return 1.0 + 0.8 * math.exp(-position / 15.0)


def number_weight(position):
    """
    Numbers can be meaningful throughout a clip,
    so only a modest early-position bonus is applied.
    """
    return 1.0 + 0.6 * math.exp(-position / 15.0)


def payoff_weight(position, duration):
    """
    Emotional or meaningful signals later in a clip
    may represent a payoff rather than a weak late signal.
    """
    if duration <= 0:
        return 1.0

    progress = position / duration

    if progress >= 0.65:
        return 1.5

    if progress >= 0.40:
        return 1.25

    return 1.0


# ============================================================
# CHUNK BUILDER
# ============================================================

def build_word_chunks(candidate, chunk_size=8):
    words = candidate["words"]
    chunks = []

    for index in range(len(words)):
        chunk_words = words[index:index + chunk_size]

        if not chunk_words:
            continue

        text = " ".join(
            clean_word(word["word"])
            for word in chunk_words
        )

        chunks.append({
            "text": text,
            "start": chunk_words[0]["start"],
            "end": chunk_words[-1]["end"],
            "index": index
        })

    return chunks


# ============================================================
# QUESTION SCORE
# ============================================================

def question_score(candidate):
    """
    Question V2.2

    Context-aware question scoring.

    Evaluates:
    - Question starter/type
    - Information-gap strength
    - Interesting concepts
    - Question depth/completeness
    - Generic/routine question penalties
    - Position inside the clip
    - Quality-based score ceilings

    Only the strongest question in the clip contributes.
    """

    words = candidate.get("words", [])

    if not words:
        return 0.0

    # ========================================================
    # NORMALIZATION
    # ========================================================

    def normalize_token(value):
        value = str(value).lower().strip()

        value = re.sub(
            r"[^a-z0-9'-]+",
            "",
            value
        )

        return value.strip()

    # ========================================================
    # QUESTION STARTER STRENGTH
    # ========================================================

    starter_strength = {
        # Explanation / reasoning
        "why": 1.50,
        "how": 1.35,

        # Open-ended
        "what": 1.10,
        "which": 0.90,
        "who": 0.75,

        # Often factual
        "when": 0.50,
        "where": 0.45,

        # Possibility / consequence
        "could": 0.90,
        "would": 0.90,
        "should": 0.90,
        "can": 0.75,

        # Yes / no style
        "did": 0.60,
        "does": 0.55,
        "do": 0.55,
        "have": 0.60,
        "has": 0.55,
        "is": 0.45,
        "are": 0.45,
        "was": 0.45,
        "were": 0.45
    }

    # ========================================================
    # HIGH-VALUE QUESTION PATTERNS
    # ========================================================

    strong_patterns = {
        "what if": 1.20,
        "what would happen": 1.10,
        "what happens if": 1.10,

        "why do you think": 1.00,
        "why does": 0.90,
        "why do": 0.90,
        "why did": 0.85,
        "why is": 0.85,

        "how would": 0.90,
        "how can": 0.85,
        "how did": 0.75,
        "how does": 0.75,
        "how do": 0.70,

        "what made": 0.85,
        "what changed": 0.90,
        "what happened": 0.80,

        "what do you think": 0.65,
        "do you think": 0.55,

        "have you ever": 0.65,
        "did you ever": 0.60
    }

    # ========================================================
    # INTERESTING CONCEPTS
    # ========================================================

    interesting_concepts = {
        "ai",
        "future",
        "change",
        "changed",
        "problem",
        "problems",
        "challenge",
        "challenges",
        "risk",
        "danger",
        "failure",
        "fail",
        "failed",
        "success",
        "successful",
        "money",
        "truth",
        "secret",
        "fear",
        "death",
        "life",
        "technology",
        "believe",
        "think",
        "happen",
        "happens",
        "happened",
        "possible",
        "impossible",
        "biggest",
        "best",
        "worst",
        "important"
    }

    # ========================================================
    # ROUTINE / LOW-VALUE QUESTIONS
    # ========================================================

    routine_patterns = {
        "what time",
        "what year",
        "what date",
        "what is your name",
        "whats your name",
        "where are you from",
        "where were you born",
        "how old are you"
    }

    # ========================================================
    # GENERIC QUESTIONS
    # ========================================================

    generic_patterns = {
        "what do you think",
        "do you think",
        "what about",
        "how about",
        "what happened",
        "what do you mean"
    }

    # ========================================================
    # FIND EXPLICIT QUESTIONS
    # ========================================================

    questions = []

    sentence_start = 0

    for index, word in enumerate(words):

        raw = str(
            word.get("word", "")
        ).strip()

        if not raw:
            continue

        if raw.endswith("?"):

            question_words = words[
                sentence_start:index + 1
            ]

            if question_words:
                questions.append(
                    question_words
                )

            sentence_start = index + 1

        elif raw.endswith((".", "!")):
            sentence_start = index + 1

    # ========================================================
    # BACKUP QUESTION DETECTION
    # ========================================================
    #
    # Whisper can occasionally miss "?". If no explicit
    # question exists, inspect the opening ~8 seconds.
    # ========================================================

    if not questions:

        opening_words = []

        for word in words:

            position = (
                word["start"]
                - candidate["start"]
            )

            if position > 8.0:
                break

            opening_words.append(word)

        cleaned_opening = [
            normalize_token(
                word.get("word", "")
            )
            for word in opening_words
        ]

        cleaned_opening = [
            word
            for word in cleaned_opening
            if word
        ]

        opening_text = " ".join(
            cleaned_opening
        ).strip()

        backup_starters = (
            "why ",
            "how ",
            "what ",
            "which ",
            "who ",
            "could ",
            "would ",
            "should ",
            "can ",
            "do ",
            "does ",
            "did ",
            "have ",
            "has ",
            "is ",
            "are "
        )

        if opening_text.startswith(
            backup_starters
        ):
            questions.append(
                opening_words
            )

    if not questions:
        return 0.0

    # ========================================================
    # SCORE QUESTIONS
    # ========================================================

    best_question_score = 0.0

    seen_questions = set()

    for question_words in questions:

        cleaned_words = [
            normalize_token(
                word.get("word", "")
            )
            for word in question_words
        ]

        cleaned_words = [
            word
            for word in cleaned_words
            if word
        ]

        if not cleaned_words:
            continue

        question_text = " ".join(
            cleaned_words
        ).strip()

        # ----------------------------------------------------
        # DUPLICATE CONTROL
        # ----------------------------------------------------

        if question_text in seen_questions:
            continue

        seen_questions.add(
            question_text
        )

        first_word = cleaned_words[0]

        position = max(
            0.0,
            question_words[0]["start"]
            - candidate["start"]
        )

        # ====================================================
        # 1. STARTER QUALITY
        # ====================================================

        base = starter_strength.get(
            first_word,
            0.30
        )

        strength = base

        # ====================================================
        # 2. INFORMATION-GAP PATTERN
        # ====================================================

        best_pattern = None
        pattern_bonus = 0.0

        for pattern, bonus in (
            strong_patterns.items()
        ):

            if (
                question_text.startswith(pattern)
                or pattern in question_text
            ):

                if bonus > pattern_bonus:

                    pattern_bonus = bonus
                    best_pattern = pattern

        strength += pattern_bonus

        # ====================================================
        # 3. INTERESTING CONCEPTS
        # ====================================================

        concept_matches = {
            word
            for word in cleaned_words
            if word in interesting_concepts
        }

        concept_bonus = min(
            0.60,
            len(concept_matches) * 0.20
        )

        strength += concept_bonus

        # ====================================================
        # 4. QUESTION DEPTH / COMPLETENESS
        # ====================================================

        word_count = len(
            cleaned_words
        )

        # Very short questions are normally conversational,
        # not strong standalone short-form hooks.

        if word_count <= 3:
            strength *= 0.45

        elif word_count <= 5:
            strength *= 0.65

        elif word_count <= 7:
            strength *= 0.85

        elif word_count >= 10:
            # Longer questions can contain useful context,
            # but don't give them a huge automatic bonus.
            strength += 0.10

        # ====================================================
        # 5. GENERIC QUESTION PENALTY
        # ====================================================

        generic_question = False

        for pattern in generic_patterns:

            # Only penalize when the entire question is
            # essentially the generic phrase.
            #
            # "What do you think?"
            #       -> generic
            #
            # "What do you think is the biggest AI risk?"
            #       -> not automatically generic

            if question_text == pattern:

                strength *= 0.55

                generic_question = True

                break

        # ====================================================
        # 6. ROUTINE QUESTION PENALTY
        # ====================================================

        routine = False

        for pattern in routine_patterns:

            if question_text.startswith(
                pattern
            ):

                strength *= 0.35

                routine = True

                break

        # ====================================================
        # 7. POSITION WEIGHT
        # ====================================================

        positional = opening_weight(
            position
        )

        value = (
            strength
            * positional
        )

        # ====================================================
        # 8. QUALITY EVIDENCE
        # ====================================================
        #
        # A question must earn the right to reach the
        # highest score tier.
        # ====================================================

        quality_evidence = 0

        # WHY/HOW questions tend to request explanation,
        # reasoning, causality, or process.

        if first_word in {
            "why",
            "how"
        }:
            quality_evidence += 1

        # Strong information-gap structures.

        if best_pattern in {
            "what if",
            "what would happen",
            "what happens if",

            "why do you think",
            "why does",
            "why do",
            "why did",
            "why is",

            "how would",
            "how can"
        }:
            quality_evidence += 1

        # Meaningful subject matter.

        if len(concept_matches) >= 1:
            quality_evidence += 1

        # Enough context to stand alone.

        if word_count >= 7:
            quality_evidence += 1

        # ====================================================
        # 9. QUALITY-BASED SCORE CEILING
        # ====================================================

        if generic_question:

            # Generic conversational question.
            ceiling = 2.20

        elif routine:

            # Logistical / factual questions shouldn't
            # dominate highlight selection.
            ceiling = 1.80

        elif quality_evidence <= 1:

            # Valid question but limited hook strength.
            ceiling = 2.80

        elif quality_evidence == 2:

            # Good question.
            ceiling = 3.40

        else:

            # Strong question with multiple independent
            # quality signals.
            ceiling = 4.00

        value = min(
            value,
            ceiling
        )

        # ====================================================
        # DEBUG
        # ====================================================

        print(
            f'QUESTION MATCH: "{question_text}" | '
            f'position={position:.2f}s | '
            f'starter={first_word} | '
            f'base={base:.2f} | '
            f'pattern={best_pattern or "none"} | '
            f'pattern_bonus={pattern_bonus:.2f} | '
            f'concepts={sorted(concept_matches)} | '
            f'concept_bonus={concept_bonus:.2f} | '
            f'words={word_count} | '
            f'generic={generic_question} | '
            f'routine={routine} | '
            f'quality={quality_evidence} | '
            f'ceiling={ceiling:.2f} | '
            f'value=+{value:.2f}'
        )

        # ====================================================
        # ONLY STRONGEST QUESTION COUNTS
        # ====================================================

        best_question_score = max(
            best_question_score,
            value
        )

    return round(
        best_question_score,
        2
    )

# ============================================================
# EMOTION SCORE
# ============================================================

def emotion_score(candidate):
    emotion_strength = {
        # Positive emotion
        "amazing": 1.3,
        "incredible": 1.5,
        "unbelievable": 1.5,
        "awesome": 1.3,
        "wonderful": 1.3,
        "exciting": 1.3,
        "excited": 1.3,
        "proud": 1.2,
        "love": 1.2,
        "loved": 1.2,

        # Negative / intense emotion
        "hate": 1.3,
        "hated": 1.3,
        "terrible": 1.3,
        "horrible": 1.4,
        "worst": 1.4,
        "scared": 1.3,
        "afraid": 1.3,
        "fear": 1.3,
        "angry": 1.3,
        "furious": 1.5,
        "heartbroken": 1.5,
        "painful": 1.3,
        "failed": 1.2,
        "failure": 1.2,
        "destroyed": 1.4,

        # Aspirational / struggle
        "dream": 1.0,
        "dreams": 1.0,
        "struggle": 1.1,
        "struggling": 1.1,

        # Surprise / intensity
        "shocking": 1.5,
        "shocked": 1.4,
        "surprised": 1.3,
        "surprising": 1.3,
        "insane": 1.4,
        "crazy": 1.2,
        "wow": 1.2
    }

    if not candidate.get("words"):
        return 0.0

    score = 0.0

    duration = max(
        0.01,
        candidate["end"] - candidate["start"]
    )

    matches = 0
    used_words = set()

    for word in candidate["words"]:
        # Convert safely even if Whisper gives us
        # unexpected spacing/punctuation.
        raw_word = str(
            word.get("word", "")
        ).lower().strip()

        cleaned = re.sub(
            r"[^a-z0-9'-]",
            "",
            raw_word
        )

        if not cleaned:
            continue

        if cleaned not in emotion_strength:
            continue

        # Don't let repeating the exact same emotional
        # word inflate the score endlessly.
        if cleaned in used_words:
            continue

        used_words.add(cleaned)

        position = max(
            0.0,
            word["start"] - candidate["start"]
        )

        strength = emotion_strength[cleaned]

        positional = emotion_weight(position)

        payoff = payoff_weight(
            position,
            duration
        )

        value = (
            strength
            * positional
            * payoff
        )

        score += value
        matches += 1

        print(
            f"EMOTION MATCH: "
            f"{cleaned} | "
            f"position={position:.2f}s | "
            f"value=+{value:.2f}"
        )

        if matches >= 4:
            break

    return round(score, 2)


# ============================================================
# CURIOSITY SCORE
# ============================================================

def curiosity_score(candidate):
    """
    Curiosity V2

    Measures whether a clip creates a genuine information gap.

    Evaluates:
    - Reveal / mystery language
    - Unexpected change or contradiction
    - Consequence / anticipation language
    - Unresolved setup
    - Position inside the clip
    - Phrase specificity
    - Duplicate control
    - Generic phrase penalties
    - Quality-based score ceilings

    Only the strongest curiosity signals contribute heavily.
    Repeated versions of the same idea receive reduced value.
    """

    words = candidate.get("words", [])

    if not words:
        return 0.0

    # ========================================================
    # NORMALIZATION
    # ========================================================

    def normalize_token(value):
        value = str(value).lower().strip()

        value = re.sub(
            r"[^a-z0-9'-]+",
            "",
            value
        )

        # Normalize common contractions so phrase matching
        # works reliably with Whisper output.
        contractions = {
            "whats": "what",
            "what's": "what",
            "heres": "here",
            "here's": "here",
            "thats": "that",
            "that's": "that",
            "youll": "you",
            "you'll": "you",
            "wont": "will",
            "won't": "will",
            "cant": "can",
            "can't": "can"
        }

        return contractions.get(
            value,
            value
        )

    # ========================================================
    # BUILD NORMALIZED WORD DATA
    # ========================================================

    normalized = []

    for word in words:

        token = normalize_token(
            word.get("word", "")
        )

        if not token:
            continue

        normalized.append({
            "word": token,
            "start": word.get(
                "start",
                candidate["start"]
            )
        })

    if not normalized:
        return 0.0

    tokens = [
        item["word"]
        for item in normalized
    ]

    full_text = " ".join(tokens)

    # ========================================================
    # CURIOSITY SIGNAL LIBRARY
    # ========================================================
    #
    # Values represent semantic strength BEFORE position
    # weighting and quality gating.
    # ========================================================

    curiosity_patterns = {

        # ----------------------------------------------------
        # TIER 1 — STRONG INFORMATION GAP / REVEAL
        # ----------------------------------------------------

        "but what happened next": (
            2.20,
            "reveal"
        ),

        "what happened next": (
            2.10,
            "reveal"
        ),

        "you won't believe": (
            2.10,
            "reveal"
        ),

        "you would never guess": (
            2.00,
            "reveal"
        ),

        "nobody expected": (
            1.95,
            "surprise"
        ),

        "no one expected": (
            1.95,
            "surprise"
        ),

        "the surprising part": (
            1.90,
            "reveal"
        ),

        "the crazy part": (
            1.75,
            "reveal"
        ),

        "here's the secret": (
            1.90,
            "secret"
        ),

        "the secret is": (
            1.80,
            "secret"
        ),

        "what nobody tells you": (
            2.00,
            "hidden_information"
        ),

        "what people don't realize": (
            1.90,
            "hidden_information"
        ),

        "most people don't know": (
            1.85,
            "hidden_information"
        ),

        "what most people miss": (
            1.90,
            "hidden_information"
        ),

        # ----------------------------------------------------
        # TIER 2 — CONTRADICTION / EXPECTATION BREAK
        # ----------------------------------------------------

        "but actually": (
            1.55,
            "contradiction"
        ),

        "but the reality": (
            1.65,
            "contradiction"
        ),

        "the reality is": (
            1.45,
            "contradiction"
        ),

        "the truth is": (
            1.50,
            "contradiction"
        ),

        "turns out": (
            1.65,
            "reveal"
        ),

        "it turns out": (
            1.70,
            "reveal"
        ),

        "instead": (
            0.75,
            "contrast"
        ),

        "however": (
            0.70,
            "contrast"
        ),

        # ----------------------------------------------------
        # TIER 3 — CHANGE / CONSEQUENCE / ANTICIPATION
        # ----------------------------------------------------

        "everything changed": (
            1.70,
            "change"
        ),

        "that changed everything": (
            1.85,
            "change"
        ),

        "things changed": (
            1.20,
            "change"
        ),

        "then something happened": (
            1.65,
            "anticipation"
        ),

        "and then": (
            0.75,
            "anticipation"
        ),

        "until": (
            0.85,
            "anticipation"
        ),

        "eventually": (
            0.70,
            "anticipation"
        ),

        "the result": (
            1.00,
            "consequence"
        ),

        "the result was": (
            1.20,
            "consequence"
        ),

        "because of that": (
            0.95,
            "consequence"
        ),

        "which means": (
            1.00,
            "consequence"
        ),

        "that means": (
            0.90,
            "consequence"
        ),

        # ----------------------------------------------------
        # TIER 4 — DISCOVERY / REALIZATION
        # ----------------------------------------------------

        "i realized": (
            1.25,
            "realization"
        ),

        "we realized": (
            1.25,
            "realization"
        ),

        "i discovered": (
            1.35,
            "discovery"
        ),

        "we discovered": (
            1.35,
            "discovery"
        ),

        "i found out": (
            1.35,
            "discovery"
        ),

        "we found out": (
            1.35,
            "discovery"
        ),

        "i learned": (
            1.00,
            "realization"
        ),

        "we learned": (
            1.00,
            "realization"
        ),

        # ----------------------------------------------------
        # TIER 5 — WEAKER CURIOSITY LANGUAGE
        # ----------------------------------------------------

        "interesting thing": (
            0.85,
            "generic"
        ),

        "interesting part": (
            0.95,
            "generic"
        ),

        "the thing is": (
            0.55,
            "generic"
        ),

        "imagine": (
            0.90,
            "possibility"
        ),

        "imagine if": (
            1.25,
            "possibility"
        )
    }

    # ========================================================
    # GENERIC SIGNALS
    # ========================================================
    #
    # These can create curiosity, but by themselves should
    # never reach the highest tier.
    # ========================================================

    generic_patterns = {
        "and then",
        "eventually",
        "however",
        "instead",
        "the thing is",
        "interesting thing",
        "interesting part"
    }

    # ========================================================
    # STRONG CURIOSITY TYPES
    # ========================================================

    strong_types = {
        "reveal",
        "secret",
        "hidden_information",
        "surprise",
        "contradiction",
        "change",
        "discovery"
    }

    # ========================================================
    # FIND ALL PATTERN MATCHES
    # ========================================================

    matches = []

    # Longest phrases first.
    sorted_patterns = sorted(
        curiosity_patterns.items(),
        key=lambda item: len(
            item[0].split()
        ),
        reverse=True
    )

    used_ranges = []

    for pattern, (
        base_strength,
        signal_type
    ) in sorted_patterns:

        pattern_tokens = pattern.split()

        pattern_length = len(
            pattern_tokens
        )

        if pattern_length == 0:
            continue

        for index in range(
            0,
            len(tokens)
            - pattern_length
            + 1
        ):

            candidate_tokens = tokens[
                index:index + pattern_length
            ]

            if candidate_tokens != pattern_tokens:
                continue

            start_index = index

            end_index = (
                index
                + pattern_length
                - 1
            )

            # -----------------------------------------------
            # OVERLAP CONTROL
            # -----------------------------------------------
            #
            # If:
            #
            # "what happened next"
            #
            # matches, don't separately reward:
            #
            # "happened next"
            #
            # or other overlapping shorter patterns.
            # -----------------------------------------------

            overlaps = False

            for used_start, used_end in used_ranges:

                if not (
                    end_index < used_start
                    or start_index > used_end
                ):
                    overlaps = True
                    break

            if overlaps:
                continue

            used_ranges.append(
                (
                    start_index,
                    end_index
                )
            )

            absolute_start = normalized[
                start_index
            ]["start"]

            position = max(
                0.0,
                absolute_start
                - candidate["start"]
            )

            matches.append({
                "pattern": pattern,
                "type": signal_type,
                "base": base_strength,
                "position": position,
                "start_index": start_index,
                "end_index": end_index
            })

    if not matches:
        return 0.0

    # ========================================================
    # SCORE MATCHES
    # ========================================================

    scored_matches = []

    seen_semantic_signals = set()

    for match in matches:

        pattern = match["pattern"]
        signal_type = match["type"]
        base = match["base"]
        position = match["position"]

        # ====================================================
        # 1. POSITION WEIGHT
        # ====================================================

        positional = opening_weight(
            position
        )

        value = (
            base
            * positional
        )

        # ====================================================
        # 2. GENERIC SIGNAL PENALTY
        # ====================================================

        generic = (
            pattern in generic_patterns
            or signal_type == "generic"
        )

        if generic:
            value *= 0.65

        # ====================================================
        # 3. SEMANTIC REPETITION CONTROL
        # ====================================================
        #
        # Different phrases expressing the SAME curiosity
        # mechanism shouldn't repeatedly receive full value.
        #
        # Example:
        #
        # "turns out..."
        # "the truth is..."
        # "but actually..."
        #
        # can all be variants of the same reveal.
        # ====================================================

        semantic_key = signal_type

        repeated_type = (
            semantic_key
            in seen_semantic_signals
        )

        if repeated_type:
            value *= 0.35

        else:
            seen_semantic_signals.add(
                semantic_key
            )

        # ====================================================
        # 4. QUALITY EVIDENCE
        # ====================================================

        quality_evidence = 0

        # Strong semantic mechanism.
        if signal_type in strong_types:
            quality_evidence += 1

        # Multi-word phrase gives more context than a
        # standalone trigger word.
        phrase_word_count = len(
            pattern.split()
        )

        if phrase_word_count >= 2:
            quality_evidence += 1

        # Longer, more specific phrases provide stronger
        # evidence of a genuine information gap.
        if phrase_word_count >= 3:
            quality_evidence += 1

        # Early curiosity is much more useful for retention.
        if position <= 8.0:
            quality_evidence += 1

        # ====================================================
        # 5. QUALITY-BASED CEILING
        # ====================================================

        if generic:

            ceiling = 1.50

        elif quality_evidence <= 1:

            ceiling = 1.80

        elif quality_evidence == 2:

            ceiling = 2.40

        elif quality_evidence == 3:

            ceiling = 3.10

        else:

            ceiling = 3.60

        value = min(
            value,
            ceiling
        )

        scored_matches.append({
            "pattern": pattern,
            "type": signal_type,
            "position": position,
            "base": base,
            "generic": generic,
            "repeated": repeated_type,
            "quality": quality_evidence,
            "ceiling": ceiling,
            "value": value
        })

    # ========================================================
    # SORT BY VALUE
    # ========================================================

    scored_matches.sort(
        key=lambda item: item["value"],
        reverse=True
    )

    # ========================================================
    # COMBINE SIGNALS
    # ========================================================
    #
    # Strongest curiosity signal gets full value.
    #
    # Second DISTINCT signal can reinforce it, but receives
    # only partial credit.
    #
    # This prevents a clip containing five curiosity phrases
    # from farming enormous scores.
    # ========================================================

    strongest = scored_matches[0]

    total_score = strongest["value"]

    if len(scored_matches) >= 2:

        second = scored_matches[1]

        # Only meaningful secondary evidence contributes.
        if second["value"] >= 0.60:
            total_score += (
                second["value"]
                * 0.35
            )

    # ========================================================
    # FINAL CATEGORY CEILING
    # ========================================================

    total_score = min(
        total_score,
        4.0
    )

    # ========================================================
    # DEBUG OUTPUT
    # ========================================================

    for match in scored_matches:

        print(
            f'CURIOSITY MATCH: '
            f'"{match["pattern"]}" | '
            f'type={match["type"]} | '
            f'position={match["position"]:.2f}s | '
            f'base={match["base"]:.2f} | '
            f'generic={match["generic"]} | '
            f'repeated={match["repeated"]} | '
            f'quality={match["quality"]} | '
            f'ceiling={match["ceiling"]:.2f} | '
            f'value=+{match["value"]:.2f}'
        )

    print(
        f'CURIOSITY TOTAL: '
        f'{total_score:.2f}'
    )

    return round(
        total_score,
        2
    )


# ============================================================
# ENGAGEMENT SCORE
# ============================================================

def engaging_score(candidate):
    engagement_patterns = {
        "important": 1.2,
        "most important": 1.5,
        "biggest": 1.3,
        "greatest": 1.3,
        "best": 1.2,
        "worst": 1.3,
        "never": 1.2,
        "always": 1.0,
        "problem": 1.1,
        "solution": 1.1,
        "you need to": 1.2,
        "you have to": 1.2,
        "you should": 1.1,
        "most people": 1.3,
        "everyone": 1.1,
        "nobody": 1.2,
        "the problem is": 1.4,
        "the thing is": 1.2,
        "but actually": 1.3,
        "but the truth": 1.5,
        "instead": 1.0
    }

    chunks = build_word_chunks(
        candidate,
        chunk_size=8
    )

    score = 0.0
    matches = 0

    used_patterns = set()

    for chunk in chunks:
        position = (
            chunk["start"]
            - candidate["start"]
        )

        for pattern, strength in engagement_patterns.items():
            if pattern not in chunk["text"]:
                continue

            if pattern in used_patterns:
                continue

            value = (
                strength
                * engagement_weight(position)
            )

            score += value

            used_patterns.add(pattern)
            matches += 1

            if matches >= 3:
                break

        if matches >= 3:
            break

    return round(score, 2)


# ============================================================
# NUMBER SCORE
# ============================================================

def number_score(candidate):
    """
    Context-aware number scoring.

    Goals:
    - Do NOT reward every number equally.
    - Strong statistics should matter more than ordinary numbers.
    - Percentages, money, multipliers and large quantities are valuable.
    - Ages, years and dates are useful but weaker.
    - Repeated numbers/claims should not farm points.
    """

    if not candidate.get("words"):
        return 0.0

    words = candidate["words"]

    score = 0.0
    matches = 0

    # Prevent repeated numeric ideas from repeatedly scoring.
    used_number_keys = set()

    number_words = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "hundred": 100,
        "thousand": 1000,
        "million": 1000000,
        "billion": 1000000000,
        "trillion": 1000000000000
    }

    weak_context = {
        "chapter",
        "episode",
        "page",
        "section",
        "part"
    }

    # --------------------------------------------------------
    # Helper: safely normalize nearby words
    # --------------------------------------------------------

    def normalized_word(index):
        if index < 0 or index >= len(words):
            return ""

        return re.sub(
            r"[^a-z0-9$%x.-]",
            "",
            str(words[index].get("word", "")).lower()
        )

    # --------------------------------------------------------
    # Examine each word
    # --------------------------------------------------------

    for index, word in enumerate(words):
        raw = str(
            word.get("word", "")
        ).lower().strip()

        cleaned = re.sub(
            r"[^a-z0-9$%x.,-]",
            "",
            raw
        )

        if not cleaned:
            continue

        numeric_cleaned = (
            cleaned
            .replace("$", "")
            .replace("%", "")
            .replace(",", "")
        )

        numeric_value = None

        # Numeric form:
        # 13, 1980, 92%, $500, 2.5
        try:
            numeric_value = float(
                numeric_cleaned
            )

        except ValueError:
            pass

        # Written number:
        # five, million, etc.
        if (
            numeric_value is None
            and cleaned in number_words
        ):
            numeric_value = number_words[
                cleaned
            ]

        if numeric_value is None:
            continue

        previous_1 = normalized_word(
            index - 1
        )

        previous_2 = normalized_word(
            index - 2
        )

        next_1 = normalized_word(
            index + 1
        )

        next_2 = normalized_word(
            index + 2
        )

        context_words = {
            previous_2,
            previous_1,
            next_1,
            next_2
        }

        # Ignore structural numbering.
        if context_words & weak_context:
            continue

        # ====================================================
        # CLASSIFY THE NUMBER
        # ====================================================

        number_type = "ordinary"

        strength = 0.35

        # ----------------------------------------------------
        # PERCENTAGE
        # ----------------------------------------------------

        if "%" in cleaned:
            number_type = "percentage"
            strength = 1.60

        elif next_1 in {
            "percent",
            "percentage"
        }:
            number_type = "percentage"
            strength = 1.60

        # ----------------------------------------------------
        # MONEY
        # ----------------------------------------------------

        elif (
            "$" in cleaned
            or previous_1 in {
                "$",
                "dollar",
                "dollars"
            }
            or next_1 in {
                "dollar",
                "dollars"
            }
        ):
            number_type = "money"
            strength = 1.50

        # ----------------------------------------------------
        # MULTIPLIER
        # ----------------------------------------------------

        elif (
            cleaned.endswith("x")
            or next_1 in {
                "times",
                "faster",
                "higher",
                "bigger",
                "more"
            }
        ):
            number_type = "multiplier"
            strength = 1.40

        # ----------------------------------------------------
        # TIMEFRAME
        #
        # "five years"
        # "three months"
        # ----------------------------------------------------

        elif next_1 in {
            "year",
            "years",
            "month",
            "months",
            "week",
            "weeks",
            "day",
            "days",
            "hour",
            "hours"
        }:
            number_type = "timeframe"
            strength = 0.80

        # ----------------------------------------------------
        # AGE
        #
        # "age 13"
        # "13 years old"
        # ----------------------------------------------------

        elif (
            previous_1 == "age"
            or (
                next_1 in {
                    "year",
                    "years"
                }
                and next_2 == "old"
            )
        ):
            number_type = "age"
            strength = 0.55

        # ----------------------------------------------------
        # HISTORICAL YEAR / DATE
        #
        # Roughly 1800–2099
        # ----------------------------------------------------

        elif (
            numeric_value >= 1800
            and numeric_value <= 2099
        ):
            number_type = "year"
            strength = 0.55

        # ----------------------------------------------------
        # LARGE QUANTITY
        # ----------------------------------------------------

        elif numeric_value >= 1000000:
            number_type = "large_quantity"
            strength = 1.20

        elif numeric_value >= 1000:
            number_type = "large_quantity"
            strength = 0.90

        # ====================================================
        # CREATE A DEDUPLICATION KEY
        # ====================================================

        # Example:
        #
        # "five years" appears twice
        #
        # Both become:
        #
        # ("timeframe", 5, "years")
        #
        # so only the first one receives full credit.

        if number_type == "timeframe":
            number_key = (
                number_type,
                numeric_value,
                next_1
            )

        elif number_type == "percentage":
            number_key = (
                number_type,
                numeric_value
            )

        elif number_type == "money":
            number_key = (
                number_type,
                numeric_value
            )

        else:
            number_key = (
                number_type,
                numeric_value
            )

        if number_key in used_number_keys:
            print(
                f"NUMBER DUPLICATE SKIPPED: "
                f"{cleaned} "
                f"({number_type})"
            )

            continue

        used_number_keys.add(
            number_key
        )

        # ====================================================
        # POSITION WEIGHT
        # ====================================================

        position = max(
            0.0,
            word["start"]
            - candidate["start"]
        )

        positional = number_weight(
            position
        )

        value = (
            strength
            * positional
        )

        score += value
        matches += 1

        print(
            f"NUMBER MATCH: "
            f"{cleaned} | "
            f"type={number_type} | "
            f"position={position:.2f}s | "
            f"value=+{value:.2f}"
        )

        # Don't allow a clip full of numbers
        # to dominate every other signal.
        if matches >= 4:
            break

    return round(score, 2)


# ============================================================
# HOOK SCORE
# ============================================================

def hook_score(candidate):
    if not candidate["words"]:
        return 0

    opening_limit = 8.0

    opening_words = [
        word
        for word in candidate["words"]
        if (
            word["start"]
            - candidate["start"]
        ) <= opening_limit
    ]

    if not opening_words:
        return 0

    opening_text = " ".join(
        word["word"].strip()
        for word in opening_words
    )

    opening_lower = opening_text.lower()

    hook = 0.0

    # A real question in the opening creates a hook.
    if "?" in opening_text:
        hook += 1.5

    strong_opening_patterns = {
        "imagine": 1.3,
        "picture this": 1.4,
        "here's the thing": 1.3,
        "here is the thing": 1.3,
        "here's why": 1.5,
        "here is why": 1.5,
        "the truth is": 1.5,
        "the secret is": 1.5,
        "the problem is": 1.3,
        "most people": 1.3,
        "nobody tells you": 1.6,
        "what if": 1.4,
        "when i": 1.1,
        "i remember": 1.1,
        "the first time": 1.2
    }

    best_pattern = 0.0

    for pattern, strength in strong_opening_patterns.items():
        if pattern in opening_lower:
            best_pattern = max(
                best_pattern,
                strength
            )

    hook += best_pattern

    emotional_words = {
        "amazing",
        "incredible",
        "insane",
        "shocking",
        "unbelievable",
        "worst",
        "best",
        "hate",
        "love",
        "scared",
        "afraid",
        "furious",
        "heartbroken",
        "dream",
        "struggle"
    }

    early_emotion = 0

    for word in opening_words:
        if clean_word(word["word"]) in emotional_words:
            early_emotion += 1

    if early_emotion:
        hook += min(
            1.2,
            early_emotion * 0.6
        )

    # Combination bonus.
    if hook >= 2.5:
        hook += 0.5

    return round(hook, 2)


# ============================================================
# TOTAL CANDIDATE SCORE
# ============================================================

def score_candidate(candidate):
    scores = {
        "engagement": engaging_score(candidate),
        "question": question_score(candidate),
        "emotion": emotion_score(candidate),
        "curiosity": curiosity_score(candidate),
        "numbers": number_score(candidate),
        "hook": hook_score(candidate)
    }

    total_score = round(
        sum(scores.values()),
        2
    )

    return total_score, scores


# ============================================================
# CANDIDATE GENERATION
# ============================================================

def generate_candidates(transcript):
    candidates = []

    if not transcript:
        return candidates

    video_end = transcript[-1]["end"]

    window_size = 30
    step_size = 15

    window_start = 0

    while window_start < video_end:
        window_end = min(
            window_start + window_size,
            video_end
        )

        current_segments = []
        current_words = []

        for segment in transcript:
            if (
                segment["start"] < window_end
                and segment["end"] > window_start
            ):
                current_segments.append(segment)

                for word in segment["words"]:
                    if (
                        word["start"] >= window_start
                        and word["end"] <= window_end
                    ):
                        current_words.append(word)

        if current_words:
            candidate_text = " ".join(
                word["word"].strip()
                for word in current_words
            )

            candidates.append({
                "start": float(window_start),
                "end": float(window_end),
                "segments": current_segments,
                "words": current_words,
                "text": candidate_text
            })

        window_start += step_size

    return candidates


# ============================================================
# SCORE ALL CANDIDATES
# ============================================================

def evaluate_candidates(candidates):
    scored_candidates = []

    for candidate in candidates:
        score, score_breakdown = score_candidate(
            candidate
        )

        scored_candidate = {
            **candidate,
            "score": score,
            "score_breakdown": score_breakdown
        }

        scored_candidates.append(
            scored_candidate
        )

        print(
            f"\nWindow: "
            f"{candidate['start']:.2f}s - "
            f"{candidate['end']:.2f}s"
        )

        print(f"Score: {score:.2f}")

        print("Score Breakdown:")

        for category, points in score_breakdown.items():
            print(
                f"  {category}: +{points:.2f}"
            )

        print(candidate["text"])
        print("-" * 50)

    return scored_candidates


# ============================================================
# SELECT BEST CANDIDATE
# ============================================================

def select_best_candidate(candidates):
    if not candidates:
        return None

    best_candidate = max(
        candidates,
        key=lambda candidate: (
            candidate["score"],
            candidate["score_breakdown"]["hook"],
            candidate["score_breakdown"]["question"],
            candidate["score_breakdown"]["curiosity"],
            candidate["score_breakdown"]["emotion"],
            candidate["score_breakdown"]["engagement"],
            candidate["score_breakdown"]["numbers"],
            -candidate["start"]
        )
    )

    return best_candidate


# ============================================================
# SENTENCE BOUNDARY ADJUSTMENT
# ============================================================

def adjust_to_sentence_boundaries(
    candidate,
    transcript,
    start_padding=0.15,
    end_padding=0.4
):
    original_start = candidate["start"]
    original_end = candidate["end"]

    all_words = []

    for segment in transcript:
        for word in segment["words"]:
            all_words.append(word)

    sentence_endings = []

    for index, word in enumerate(all_words):
        if word["word"].strip().endswith(
            (".", "?", "!")
        ):
            sentence_endings.append(index)

    adjusted_start = original_start
    adjusted_end = original_end

    # --------------------------------------------------------
    # FIND END BOUNDARY
    # --------------------------------------------------------

    previous_end_index = None
    next_end_index = None

    for index in sentence_endings:
        word_end = all_words[index]["end"]

        if word_end <= original_end:
            previous_end_index = index

        if word_end >= original_end:
            next_end_index = index
            break

    previous_distance = float("inf")
    next_distance = float("inf")

    if previous_end_index is not None:
        previous_distance = (
            original_end
            - all_words[previous_end_index]["end"]
        )

    if next_end_index is not None:
        next_distance = (
            all_words[next_end_index]["end"]
            - original_end
        )

    if (
        previous_end_index is not None
        and previous_distance <= next_distance
    ):
        adjusted_end = (
            all_words[previous_end_index]["end"]
            + end_padding
        )

    elif next_end_index is not None:
        adjusted_end = (
            all_words[next_end_index]["end"]
            + end_padding
        )

    # --------------------------------------------------------
    # FIND START BOUNDARY
    # --------------------------------------------------------

    if original_start <= 0:
        adjusted_start = 0

    else:
        previous_start_index = None
        next_start_index = None

        for index in sentence_endings:
            word_end = all_words[index]["end"]

            if word_end <= original_start:
                previous_start_index = index

            if word_end >= original_start:
                next_start_index = index
                break

        previous_start_distance = float("inf")
        next_start_distance = float("inf")

        if previous_start_index is not None:
            previous_start_distance = (
                original_start
                - all_words[previous_start_index]["end"]
            )

        if next_start_index is not None:
            next_start_distance = (
                all_words[next_start_index]["end"]
                - original_start
            )

        chosen_start_boundary = None

        if (
            previous_start_index is not None
            and previous_start_distance
            <= next_start_distance
        ):
            chosen_start_boundary = (
                previous_start_index
            )

        elif next_start_index is not None:
            chosen_start_boundary = (
                next_start_index
            )

        if chosen_start_boundary is not None:
            next_word_index = (
                chosen_start_boundary + 1
            )

            if next_word_index < len(all_words):
                adjusted_start = max(
                    0,
                    all_words[
                        next_word_index
                    ]["start"]
                    - start_padding
                )

    # --------------------------------------------------------
    # SAFETY LIMITS
    # --------------------------------------------------------

    video_end = transcript[-1]["end"]

    adjusted_start = max(
        0,
        adjusted_start
    )

    adjusted_end = min(
        adjusted_end,
        video_end
    )

    if adjusted_end <= adjusted_start:
        adjusted_start = original_start
        adjusted_end = original_end

    # --------------------------------------------------------
    # REBUILD FINAL WORD LIST
    # --------------------------------------------------------

    final_words = []

    for word in all_words:
        if (
            word["start"] >= adjusted_start
            and word["end"] <= adjusted_end
        ):
            final_words.append(word)

    candidate["start"] = adjusted_start
    candidate["end"] = adjusted_end
    candidate["words"] = final_words

    candidate["text"] = " ".join(
        word["word"].strip()
        for word in final_words
    )

    # --------------------------------------------------------
    # DEBUG OUTPUT
    # --------------------------------------------------------

    print("\nBOUNDARY DEBUG")

    print(
        f"Original start: {original_start:.2f}"
    )

    print(
        f"Original end: {original_end:.2f}"
    )

    if previous_end_index is not None:
        print(
            "Previous end punctuation:",
            f"{all_words[previous_end_index]['end']:.2f}s"
        )

    if next_end_index is not None:
        print(
            "Next end punctuation:",
            f"{all_words[next_end_index]['end']:.2f}s"
        )

    print(
        f"Previous distance: "
        f"{previous_distance:.2f}s"
    )

    print(
        f"Next distance: "
        f"{next_distance:.2f}s"
    )

    print(
        f"Adjusted start: "
        f"{adjusted_start:.2f}"
    )

    print(
        f"Adjusted end: "
        f"{adjusted_end:.2f}"
    )

    return candidate


# ============================================================
# MAIN HIGHLIGHT FINDER
# ============================================================

def find_highlights(transcript):
    # ========================================================
    # 1. GENERATE RAW 30-SECOND CANDIDATES
    # ========================================================

    candidates = generate_candidates(transcript)

    if not candidates:
        print("No highlight candidates found.")
        return None

    # ========================================================
    # 2. INITIAL SCORING
    # ========================================================

    scored_candidates = evaluate_candidates(
        candidates
    )

    # ========================================================
    # 3. TAKE PROMISING CANDIDATES
    # ========================================================
    #
    # We don't need to boundary-adjust every weak candidate
    # in a long podcast.
    #
    # Take the top candidates from the initial scoring,
    # then evaluate their real final versions.
    # ========================================================

    shortlist_size = min(
        10,
        len(scored_candidates)
    )

    shortlisted = sorted(
        scored_candidates,
        key=lambda candidate: candidate["score"],
        reverse=True
    )[:shortlist_size]

    print(
        f"\nEvaluating top "
        f"{len(shortlisted)} candidates "
        f"after sentence-boundary adjustment..."
    )

    # ========================================================
    # 4. ADJUST + RE-SCORE EACH SHORTLISTED CANDIDATE
    # ========================================================

    final_candidates = []

    for rank, candidate in enumerate(
        shortlisted,
        start=1
    ):
        # Make a copy because boundary adjustment mutates
        # start/end/words/text.
        adjusted_candidate = {
            **candidate,
            "segments": list(
                candidate.get("segments", [])
            ),
            "words": list(
                candidate.get("words", [])
            ),
            "score_breakdown": dict(
                candidate.get(
                    "score_breakdown",
                    {}
                )
            )
        }

        original_start = candidate["start"]
        original_end = candidate["end"]
        original_score = candidate["score"]

        print("\n" + "=" * 60)

        print(
            f"SHORTLIST CANDIDATE #{rank}"
        )

        print(
            f"Original window: "
            f"{original_start:.2f}s - "
            f"{original_end:.2f}s"
        )

        print(
            f"Initial score: "
            f"{original_score:.2f}"
        )

        # ----------------------------------------------------
        # Adjust candidate to natural sentence boundaries
        # ----------------------------------------------------

        adjusted_candidate = (
            adjust_to_sentence_boundaries(
                adjusted_candidate,
                transcript
            )
        )

        # ----------------------------------------------------
        # Re-score ACTUAL adjusted clip
        # ----------------------------------------------------

        final_score, final_breakdown = (
            score_candidate(
                adjusted_candidate
            )
        )

        adjusted_candidate[
            "score"
        ] = final_score

        adjusted_candidate[
            "score_breakdown"
        ] = final_breakdown

        # Keep original information for debugging.
        adjusted_candidate[
            "original_start"
        ] = original_start

        adjusted_candidate[
            "original_end"
        ] = original_end

        adjusted_candidate[
            "original_score"
        ] = original_score

        print(
            f"\nFinal window: "
            f"{adjusted_candidate['start']:.2f}s - "
            f"{adjusted_candidate['end']:.2f}s"
        )

        print(
            f"Final score: "
            f"{final_score:.2f}"
        )

        print(
            f"Score change: "
            f"{final_score - original_score:+.2f}"
        )

        print("Final breakdown:")

        for category, points in (
            final_breakdown.items()
        ):
            print(
                f"  {category}: "
                f"+{points:.2f}"
            )

        final_candidates.append(
            adjusted_candidate
        )

    # ========================================================
    # 5. SELECT WINNER USING FINAL SCORES
    # ========================================================

    best_candidate = max(
        final_candidates,
        key=lambda candidate: (
            candidate["score"],

            candidate[
                "score_breakdown"
            ]["hook"],

            candidate[
                "score_breakdown"
            ]["question"],

            candidate[
                "score_breakdown"
            ]["curiosity"],

            candidate[
                "score_breakdown"
            ]["emotion"],

            candidate[
                "score_breakdown"
            ]["engagement"],

            candidate[
                "score_breakdown"
            ]["numbers"],

            -candidate["start"]
        )
    )

    # ========================================================
    # 6. SHOW FINAL RANKING
    # ========================================================

    ranked_finalists = sorted(
        final_candidates,
        key=lambda candidate: (
            candidate["score"],
            candidate[
                "score_breakdown"
            ]["hook"],
            candidate[
                "score_breakdown"
            ]["question"],
            candidate[
                "score_breakdown"
            ]["curiosity"],
            candidate[
                "score_breakdown"
            ]["emotion"],
            candidate[
                "score_breakdown"
            ]["engagement"],
            candidate[
                "score_breakdown"
            ]["numbers"]
        ),
        reverse=True
    )

    print("\n" + "=" * 60)

    print("FINAL SHORTLIST RANKING")

    print("=" * 60)

    for rank, candidate in enumerate(
        ranked_finalists,
        start=1
    ):
        print(
            f"\n#{rank} | "
            f"{candidate['start']:.2f}s - "
            f"{candidate['end']:.2f}s | "
            f"Score: {candidate['score']:.2f}"
        )

        print(
            "   "
            f"Hook {candidate['score_breakdown']['hook']:.2f} | "
            f"Question {candidate['score_breakdown']['question']:.2f} | "
            f"Curiosity {candidate['score_breakdown']['curiosity']:.2f} | "
            f"Emotion {candidate['score_breakdown']['emotion']:.2f} | "
            f"Engagement {candidate['score_breakdown']['engagement']:.2f} | "
            f"Numbers {candidate['score_breakdown']['numbers']:.2f}"
        )

    # ========================================================
    # 7. FINAL WINNER
    # ========================================================

    print("\n" + "=" * 60)

    print("BEST HIGHLIGHT")

    print("=" * 60)

    print(
        f"Start: "
        f"{best_candidate['start']:.2f}s"
    )

    print(
        f"End: "
        f"{best_candidate['end']:.2f}s"
    )

    print(
        f"Score: "
        f"{best_candidate['score']:.2f}"
    )

    print(
        "\nWhy this highlight was selected:"
    )

    for category, points in (
        best_candidate[
            "score_breakdown"
        ].items()
    ):
        print(
            f"  {category}: "
            f"+{points:.2f}"
        )

    print("\nHighlight Text:")

    print(
        best_candidate["text"]
    )

    return best_candidate