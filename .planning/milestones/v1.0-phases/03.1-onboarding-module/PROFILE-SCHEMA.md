# Promaia Personal Profile Schema
## The Authoritative Map of What Promaia Is Trying to Know

This document defines every field Promaia works to learn about a user, organized
by tier (how hard it is to get and how sensitive it is), with sources mapped to
each field. All sources feed the same `brain.profile` table.

**Sources:**
- `Q` — Direct question (question bank, onboarding interview)
- `G` — Gmail anthropologist (post-cleanup corpus analysis)
- `A` — Ambient capture (inferred from regular conversation)
- `P` — PC scan (git history, file structure, installed apps)
- `T` — Time / earned through relationship (never asked directly)

**Confidence defaults by source:**
- Declared (user said it): 0.9
- Confirmed (user validated inference): 0.95
- Inferred (observed): 0.5–0.7

---

## Tier 1 — Ask Directly, Day One
*Easy, low-stakes, immediate utility. No patience required.*

| Field | What It Tells Us | Source |
|---|---|---|
| `identity.preferred_name` | What to call them | Q |
| `identity.pronouns` | Respect and accuracy | Q |
| `identity.timezone` | When they're around, scheduling | Q |
| `identity.primary_device` | How they're interacting | Q, P |
| `identity.primary_use` | What they mainly want Promaia for right now | Q |
| `communication.verbosity` | Short answers or full reasoning | Q |
| `communication.preferred_tone` | Direct/blunt vs. diplomatic/gentle | Q |

**How Promaia uses this immediately:**
Adjusts how it addresses them, what time anchors it uses, how long its responses are,
and whether it leads with the answer or the reasoning.

---

## Tier 2 — Ask Early, Slightly More Personal
*Still declared. Asked in first few sessions. Unlocks real usefulness.*

| Field | What It Tells Us | Source |
|---|---|---|
| `context.role` | Job title or self-description | Q |
| `context.employer` | Company or "self-employed" | Q |
| `context.industry` | Domain expertise, vocabulary to use | Q |
| `context.active_projects` | What they're juggling right now | Q, G, A |
| `context.tech_stack` | Tools they use, language to use | Q, P |
| `identity.bio_blurb` | How they describe themselves | Q, G |
| `relationships.household` | Partner, kids, caregivers — life context | Q, G |
| `relationships.key_collaborators` | Who they work with regularly | Q, G |
| `communication.feedback_style` | How they like to receive pushback | Q |
| `communication.humor_type` | Dry, absurdist, warm, none | Q, A |
| `communication.emoji_tolerance` | Yes / no / situational | Q, A |

**How Promaia uses this:**
Knows what world they're operating in. Can reference projects by name, avoid
jargon mismatches, calibrate formality, know who "she" and "he" are when mentioned.

---

## Tier 3 — Observe and Infer, Confirm When Confident
*Mostly behavioral. Promaia watches and names what it sees.*

| Field | What It Tells Us | Source |
|---|---|---|
| `energy_patterns.chronotype` | Morning / night / flexible | G, A, P |
| `energy_patterns.peak_focus_hours` | When they do their best work | G, A |
| `energy_patterns.sprint_duration` | How long they focus before breaking | A, P |
| `energy_patterns.email_send_times` | Real activity rhythm (not self-reported) | G |
| `energy_patterns.energy_drains` | What depletes them | Q, A |
| `energy_patterns.energy_sources` | What refuels them | Q, A |
| `cognitive_style.decision_speed` | Fast/gut vs. slow/deliberate | A, G |
| `cognitive_style.information_density` | Wants all options vs. just a recommendation | A, Q |
| `cognitive_style.learning_style` | Reading, doing, watching, talking | Q, A |
| `cognitive_style.follow_through` | Follows up on own asks or sends and forgets | G, A |
| `communication.response_to_long_answers` | Reads thoroughly or skims | A |
| `communication.message_length_pattern` | Writes paragraphs or one-liners | G, A |
| `work_patterns.inbox_relationship` | Processes or avoids | G |
| `work_patterns.deep_work_preference` | Long blocks or short bursts | Q, A, P |
| `work_patterns.deadline_relationship` | Motivated / stressed / ignores | Q, A |
| `work_patterns.meeting_tolerance` | Welcomes or avoids | G, A |

**How Promaia uses this:**
Knows when to push and when to give space. Knows whether to give the short version
or the full reasoning. Knows what time of day to surface things that need attention.
Can say "you tend to do your best thinking in the morning — want to tackle this then?"

---

## Tier 4 — Earn Over Time, Deeper and More Personal
*Asked only when trust exists and moment is right. Never in a list.*

| Field | What It Tells Us | Source |
|---|---|---|
| `values_and_motivation.drivers` | What actually motivates them — deadlines, curiosity, competition, legacy | Q (late), A, T |
| `values_and_motivation.ambition` | What they're reaching for and why | Q (late), A |
| `values_and_motivation.values_hierarchy` | What they'd trade for what | Q (late), T |
| `values_and_motivation.purpose_statement` | The bigger thing underneath the work | Q (late), A |
| `values_and_motivation.who_they_do_it_for` | Family, themselves, legacy, proving something | A, T |
| `emotional_landscape.patience_level` | High tolerance for friction or low | A, G |
| `emotional_landscape.stress_response` | Fight / flight / freeze / fawn | Q (late), A |
| `emotional_landscape.known_triggers` | What reliably frustrates them | Q, A, G |
| `emotional_landscape.pride_points` | What they're proud of — reveals values | A, T |
| `emotional_landscape.humor_deployment` | When they use humor and what kind | A |
| `personality.desired_ai_personality` | What they want Promaia to be like with them | Q, A |
| `personality.pushback_tolerance` | Want to be challenged or supported | Q, A |
| `personality.touchy_topics` | Subjects to approach carefully or avoid | A, T |
| `relationships.people` | Named individuals, relationship type, what to remember | Q, G, A |

**How Promaia uses this:**
This is where it stops being a tool and starts being a relationship. Knows what
jokes land. Knows when not to be funny. Knows what buttons not to push. Knows what
Zack is actually trying to build and why it matters to him. Can say the right thing
at a hard moment instead of a technically correct thing.

---

## Tier 5 — Never Asked Directly, Inferred From Patterns Over Time
*Emerges from months of observation. Held with low confidence until confirmed.*

| Field | What It Tells Us | Source |
|---|---|---|
| `cognitive_style.locus_of_control` | Feels in control of outcomes vs. subject to them | T, A |
| `cognitive_style.need_for_closure` | Comfortable with ambiguity or needs resolution | T, A |
| `cognitive_style.risk_tolerance` | Moves fast and breaks things or measures twice | T, A |
| `cognitive_style.regulatory_focus` | Motivated by gaining vs. by not losing | T, A |
| `emotional_landscape.shame_sensitivity` | How they handle being wrong or exposed | T, A |
| `emotional_landscape.conflict_style` | Engages or avoids when things get hard | T, A |
| `emotional_landscape.emotional_baseline` | Generally even-keeled or more reactive | T, A |
| `emotional_landscape.trust_patterns` | How quickly they extend trust, what breaks it | T, A |
| `personality.self_efficacy` | How much they believe they can do hard things | T, A |
| `personality.identity_anchors` | How they think of themselves at the core | T, A |

**How Promaia uses this:**
The most nuanced calibration. Knows whether to frame things as opportunities or
risks depending on regulatory focus. Knows whether to be matter-of-fact or gentle
depending on shame sensitivity. Handles conflict around mistakes with the right
posture. This tier is never surfaced to the user as a field — it just changes how
Promaia shows up.

---

## Source-to-Field Map

### Question Bank covers:
Tier 1 fully. Tier 2 mostly. Select Tier 3 (energy drains, learning style,
deadline relationship, deep work). Select Tier 4 (stress response, known triggers,
desired AI personality, drivers). Never Tier 5.

### Gmail Anthropologist covers:
- Tier 2: active projects, key collaborators, household context, bio blurb
- Tier 3: chronotype (real send times), decision speed, follow-through, inbox relationship, message length
- Tier 4: patience level, known triggers, who they do it for (life texture signals)

### Ambient Capture covers:
Everything across all tiers, continuously, as signal emerges from conversation.
Highest volume source over time. Confidence starts at 0.5 (inferred), rises to
0.9 when user confirms.

### PC Scan covers:
- Tier 1: primary device
- Tier 2: tech stack, active projects (git repos)
- Tier 3: sprint duration (commit frequency), chronotype (commit timestamps), deep work preference

### Time / Relationship covers:
Tier 4 and 5 exclusively. These fields should not be rushed. If they appear
earlier it's because the user volunteered something meaningful — capture it,
hold it with appropriate confidence.

---

## Design Principles for This Schema

1. **Tiers are not a race.** The goal is not to fill all fields. It's to know
   the person well enough to be genuinely useful at each stage of the relationship.

2. **Every field changes something.** If knowing a field doesn't change how
   Promaia behaves, it shouldn't be in the schema.

3. **Inferences are always held lightly.** Source and confidence travel with
   every value. Promaia can be wrong and should be correctable.

4. **The profile is alive.** Fields decay in relevance over time. Active projects
   from six months ago aren't active. Chronotype shifts. Relationships change.
   Recency weighting matters.

5. **The user can always see and edit it.** Nothing inferred is hidden from them.
   Transparency builds trust. "Here's what I think I know about you" is a
   feature, not an exposure.

6. **Personality fields are the payoff.** `desired_ai_personality`,
   `humor_type`, `pushback_tolerance`, `touchy_topics` — these are what make
   the difference between a tool that helps and a presence that fits.
