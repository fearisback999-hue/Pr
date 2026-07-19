# Making the most accurate AI videos with ONE creator — research notes

Verified 2026-07-19 by live web research. These findings drive the creator bible
(docs/persona/CREATOR.md), the persona parser (`tt_engine/creative/persona.py`),
and the naturalism-v2 prompt layer. Platforms move — re-verify before big spends.

## 1. Identity: train the Soul ID right, once

Higgsfield's Soul ID trains a persistent digital identity that survives style,
lighting, angle, and prompt changes. The training set is the whole game:

- **20–25 photos is the sweet spot** — too few OR too many degrades the lock.
- Consistent, even lighting; **no sunglasses, hats, heavy shadows, or cropped
  faces**.
- **Varied angles, expressions, and distances** so the model learns a full face,
  not one pose.
- **At least one full-height photo** — body proportions come from it.
- Training takes ~3–5 minutes; connect the Soul ID before generating and hold it
  across the whole batch.

For a fully synthetic persona: generate ONE approved keyframe first, then build
the 20–25-photo training set from that face (angles/expressions/distances), so
the Soul ID is trained on a single consistent human who never existed.

## 2. Workflow: keyframe-first beats text-to-video (the #1 anti-drift lever)

The single biggest consistency improvement reported across tools:

1. Generate a STILL keyframe (image model + Soul ID + master description + the
   batch's one outfit, in one of the persona's rooms).
2. Approve it against the bible (mole, teeth, hair, outfit, jewelry).
3. **Animate the approved keyframe** (image-to-video) — the model is constrained
   by the input image instead of re-inventing the character.
4. Feed approved frames back as context for the next clip (sequential
   generation) so the model matches what exists rather than starting fresh.
5. Fix stubborn single-frame drift in post (face-swap/edit the keyframe) rather
   than re-rolling the whole clip.

## 3. Prompt discipline: master description, same order, every time

- Open EVERY prompt with the same **master character description, verbatim** —
  then scene, then style, in the same order each generation.
- **Itemize outfits exactly** and repeat the wording ("oversized cream knit
  sweater, gold hoops…"). Outfit drift is the #2 consistency failure; vague
  wardrobe words invite it.
- Keep a **forbidden-variations list** (marks, teeth, hair, tattoos) in the
  casting block — state what must never change.
- Use negative prompts against the drift set (changing jewelry, morphing logos,
  extra fingers).

## 4. Realism: override the model's defaults explicitly

(Validates the engine's naturalism-v2 layer — independent sources converge on
the same craft.)

- Models default to glossy/studio output; you must say **"no studio lighting",
  "natural skin texture and pores"** or you get plastic.
- Prompt natural imperfections: handheld shake, casual framing, uneven
  exposure, lived-in clutter — **a few, not all at once**.
- Real UGC audio = ambient room tone + phone-mic speech; **no swelling music,
  no stock-voiceover polish, no motion graphics**.
- Phone-style anchors: "realistic phone video", "casual", "slightly imperfect
  framing", vertical 9:16.

## 5. Voice: pin it like the face

- Use **one voice identity forever** — same voice across every video is the
  stated best practice for creator-style content.
- Seedance 2.0 (Higgsfield's video model) generates **native audio + lip-sync
  in one pass** and accepts up to 3 reference audio clips (≤15s each): feed the
  persona's ONE canonical voice clip every generation — the audio equivalent of
  the Soul ID.
- If cloning a voice (e.g. ElevenLabs PVC): 30+ minutes of varied, clean,
  same-mic speech; then reuse that voice ID everywhere.

## 6. The bible itself

- A written character bible is the reference for every generation and caption:
  visual identity (+ forbidden variations), voice/vocabulary, backstory/values,
  signature wardrobe, recurring locations. **~2 pages; 1 page is too thin.**
- Keep a **turnaround/character sheet** (front, 3/4, side, full-body, neutral
  background, identical lighting) and a **wardrobe sheet** (same pose, outfits
  rotating) as visual anchors next to the written bible.
- Caption test: if the persona's captions could belong to any account, the
  persona is too thin — iterate the bible until they could only be hers.

## 7. The line that doesn't move

The persona is openly an AI creator: every post carries the AIGC label, and she
never presents fabricated outcome footage as proof (the label discloses the
method, not that a depicted result happened). Craft and honesty are compatible —
that's the whole engine's thesis.

## Sources

- https://higgsfield.ai/blog/sould-id-best-character-consistency
- https://higgsfield.ai/blog/Soul-ID-AI-Character-Consistency
- https://higgsfield.ai/blog/how-to-turn-photo-into-consistent-ai-persona-creator
- https://scribehow.com/page/Higgsfield_Soul_ID_The_Best_Tool_for_AI_Character_Consistency_in_2026__i1nfbuF-TcalH-r-LeNQgg
- https://digitalzoomstudio.net/2026/03/train-a-consistent-character-in-higgsfield-soul/
- https://higgsfield.ai/blog/generating-with-seedance-2-0
- https://higgsfield.ai/seedance/2.0
- https://ugccopilot.ai/blog/seedance-2-native-audio-generation-guide/
- https://kling.ai/blog/ai-character-consistency-guide
- https://www.elser.ai/blog/best-character-consistency-prompts-for-ai-video
- https://www.neolemon.com/blog/how-to-create-consistent-characters-in-ai-videos-complete-guide/
- https://geo.higgsfield.ai/task/blog/best-way-maintain-character-face-body-ai-video-clips
- https://mateostarcevicfilipovic.medium.com/the-one-prompt-that-makes-ai-ugc-ads-stop-looking-plastic-copy-it-below-55b0a4fccdc3
- https://medium.com/no-time/how-to-create-ugc-style-ads-with-ai-that-dont-look-like-ai-complete-workflow-e8f01344dcba
- https://www.usenotch.ai/blog/how-to-create-ai-ugc-ads
- https://hypefy.ai/blog/how-to-create-an-ai-influencer
- https://sozee.ai/resources/build-consistent-ai-influencer-2026/
- https://www.freeaivideohub.com/character-sheets
- https://martini.art/en/blog/ai-influencer-production-workflow
- https://elevenlabs.io/blog/7-of-the-best-ai-voices-for-tiktok-and-instagram-content
- https://www.frankx.ai/blog/ultimate-elevenlabs-workflow-2026
