---
name: motion-proof
description: >-
  Prove a narrated video, walkthrough, screen recording or animated explainer shows each thing at the moment the voice
  names it, with no dead air, no late first word, no blank or unpainted picture and no capture stutter. Use whenever
  you cut video to a voiceover, sync shots or pans to narration, record a website walkthrough, retime a voice track,
  mix music under speech, or someone says the words "don't match the scenes", "there's a delay" or "it's choppy", even
  if nobody says "verify". ALWAYS reach for it before showing or shipping a narrated video, because a model checks a
  video from a few stills, and stills cannot show timing: a shot that lands two seconds late, a cut keyed to the wrong
  "now", a six second hole in the voice and a capture running at half speed all look fine frame by frame.
---

# Motion proof

**STATUS: v1 (2026-11-06).** Built from one real job: a client website walkthrough in a cloned voice, plus a
30-day plan video, both rejected on 2026-11-05 before they passed. Each rule below is one of those rejections.

A video is right when the picture and the voice agree in time. Nothing you can see in a single frame proves that.

## Build it so it can be proven

1. **Get word timestamps first.** The voice engine's alignment, or Whisper with word timestamps. Every cut, pan and
   reveal is keyed to the word that names it, never to a guessed second or to the scene's start. Cutting each scene
   at its start was why "all of the words don't match up with the scenes."
2. **Key a cue to one occurrence.** "Now" was said three times in one scene. The cut keyed to the first match and
   the boutique shot landed a sentence early. Name the occurrence, or key to a word that is said once ("feels").
3. **Land just before the word.** A pan that eases in over about a second and arrives 0.3 to 1.0 s before the word
   reads as the picture answering the voice. Arriving after the word reads as late.
4. **Trim the voice, not the picture.** An unwanted sign-off at the end ("love ya") is cut from the voice at its
   word time and the picture is retimed to the new length.
5. **Show the narration text before recording it.** A re-recorded line costs a render. The owner wanted to see and
   edit the line first.
6. **Record by seeking, not screencasting.** A live screencast drops frames under load, so pans stutter. Drive a
   timeline as a pure function of time and capture frame by frame.
7. **Wait for paint before capture.** Lazy images captured blank, and a footer captured as a plain band because the
   theme set `content-visibility: auto`, which skips painting off-screen sections. Wait for every image to finish
   loading and override `content-visibility` to `visible` in the capture. A real phone rendered the footer fine.
8. **Nothing covers the subject while it is named.** A door panel stayed on screen over the room while the voice
   described the room. Fade the cover out as the story moves into what is behind it.

## The proof

```
python scripts/motion_check.py words narration.json                 # list words with times; repeated words marked
python scripts/motion_check.py check video.mp4 --words narration.json --cues cues.json --sheet sheet.jpg
```

`cues.json` lists what should change and when: `[{"word": "summer", "scene": 4, "n": 1, "shot": "summer collection"}]`.
Needs ffmpeg, ffprobe, numpy and Pillow. Every time comes from the frames' own timestamps, so a variable frame rate
or an audio track longer than the picture does not shift the cues. The words file can be a plain list, Whisper JSON
with word timestamps, or a scene file; `words` shows how it was read. A cue's `scene` needs the scene file.

| Check | Fails when | Seen |
|---|---|---|
| late cue | the picture is still when its word is said and only changes after it (within 4 s) | the boutique shot 1.76 s after "feels", 2026-11-05 |
| held cue (WARN) | nothing moves near the word and the picture has held since earlier | may already show the right thing: look |
| ambiguous cue | the cue word is said more than once in scope and the cue gives no `n` | "now" three times, 2026-11-05 |
| first word | the voice starts later than 2 s in (words and audio) | the plan video's opening, 2026-11-05 |
| dead air | a silence longer than 3 s inside the narration (words and audio) | "a delay in the speaking, 6 seconds" |
| overrun | the narration runs past the end of the picture (not the file: audio can run longer) | |
| black (WARN) | any black frame mid-video, checked frame by frame, unless it is a deliberate dip | a 3-frame flash |
| blank band (WARN) | a plain band over 35% of the height | the unpainted footer, 2026-11-05 |
| stutter (WARN) | over 15% of frames during motion repeat the one before; it says the real frame rate | screencast capture |

It also prints the last eight words, so a trailing line nobody wanted is in front of you.

**Music hides gaps from the audio check.** Under a music bed, silence detection finds nothing. The script says so.
Pass `--words`, or check the voice track before the mix. The word check sees the gaps either way.

**Then look at the sheet.** Each tile is the frame just after a cue word, labelled with the word and the offset.
The script proves the picture moved at the right moment. Only eyes can say it moved to the right thing.

## What this cannot do

- A 24 fps source in a 30 fps file repeats every fourth frame. The stutter WARN is right that the motion judders,
  but the cure is to render at the file's rate, not to recapture.
- It cannot tell what a shot shows. A cut that lands on time on the wrong picture passes the cue check.
- A blank band can be design. That is why it is a WARN, with the frame on the sheet.
- Word timing is only as good as the alignment that made it. The windows (2 s before, 0.5 s after) leave room for that.
- It does not judge taste: music choice, pacing and voice are the owner's call.

## Proof it was tested

`evals/make_fixtures.py` builds seven short videos with known defects (good, late shot, ambiguous cue, dead air,
late first word, blank band, stutter). Results and the real-job runs are in `evals/benchmark.md`.
