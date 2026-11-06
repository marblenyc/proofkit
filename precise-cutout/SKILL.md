---
name: precise-cutout
description: >-
  Cut a person, product or figure out of a picture precisely and place it on a card or page colour with no box, no
  halo, no dark outline and no clipped shadow, then prove it on the real colour it will sit on. Use whenever you remove
  a background, make a transparent PNG or WebP, put a cut-out on a coloured card, add a glow or backlight behind a
  figure, or someone says an edge looks hazy, boxed, outlined, jagged or "low def", even if nobody says "cutout".
  ALWAYS reach for it before showing a cut-out, because a model sees its own cut-out on white or a checkerboard, where
  a backdrop-coloured fringe, a 2 px box edge and a sliced shadow are all invisible, and they all show on a dark card.
---

# Precise cutout

**STATUS: v1 (2026-11-06).** Built from one real job: a three-figure portrait cut for a client card on house
burgundy #4a0c18, rejected four times on 2026-11-05 before it passed. Every rule below is one of those rejections.

A cut-out has no background. It is a shape with soft edges, and it goes on whatever it is placed on. Almost every
failure here comes from forgetting that: shipping the picture with its old backdrop still in the fringe, or shipping
it inside a box.

## The two scripts

`scripts/cutout.py` makes the cut and places it. `scripts/cutout_check.py` proves it. Python 3 with numpy, scipy and
Pillow; `cut` also needs `pip install "rembg[cpu]" pymatting`.

```
python scripts/cutout.py cut source.png figure.png                      # heavy: run on a render server
python scripts/cutout.py place figure.png card.jpg --on "#4a0c18" --glow "#d4a253" --width 1200
python scripts/cutout_check.py check figure.png --on "#4a0c18" --on "#fffaf0" --sheet sheet.png
python scripts/cutout_check.py fix figure.png figure-fixed.webp --on "#4a0c18" --size 640
```

`cut` downloads two segmentation models (about 2 GB) and runs a matting solve at twice the source size. Run it on a
render server, not on someone's laptop.

## How the cut is made, and why each step is there

1. **Work at 2x.** Edges get sub-pixel smoothing at the working size and come back down with a premultiplied resize.
   A plain RGBA resize darkens the fringe.
2. **Two models, joined.** `birefnet-general` and `birefnet-massive`, union of the masks. Each one dropped a cape tip
   or a sleeve edge that the other kept.
3. **A narrow unknown band.** 5 px inside and 6 px outside the mask at 2x. A 16 px band left the brown backdrop
   half-transparent round every head and neck. The client saw it as haze.
4. **A closed-form matte, then cut the faint tail.** Alpha under about 0.10 is noise from the backdrop. Keeping it
   is what makes an edge look soft and dirty instead of soft and clean.
5. **Recolour the edge from inside.** Each soft edge pixel takes the colour of the nearest solid subject pixel, more
   strongly the more transparent it is. Foreground estimation alone left backdrop colour in the fringe. On a new
   colour that fringe is a visible ring.

## Placing it

- **The card colour is the exact house hex.** On 2026-11-05 a card came back with "some red burgundy" behind the
  figure and a slightly different burgundy round it. Rejected at once: "It's the house red burgundy." Take the hex
  from the site's CSS or the brand file, never by eye, and use the same hex for the card and the page behind it.
- **No box, ever.** A cut-out composited on a rectangle of a near colour, or flattened to JPEG and then placed on a
  card, shows its box. "There is no box. If you have a box there, you're doing it wrong." Place the RGBA directly,
  or composite onto the final card colour in one step with `place`.
- **A glow starts at the edge.** The first backlight began 8 px out from the figure. That bare band round every
  edge read as "a distinct, almost comical black line... I said a glow, not a silhouette." A backlight is brightest
  where it touches the figure. `place --glow` starts at the edge and fades.
- **Keep the glow close.** A 48 px falloff was "too extended". About 24 px on an 1800 px figure, with a faint wide
  second term, reads as light.
- **Dither dark gradients.** A gold-to-burgundy fade quantised straight to 8 bits bands, and the client called it
  "low def". `place` computes in float, adds half a level of dither, and writes JPEG at 4:4:4 (chroma subsampling
  smears a red edge on a dark card) or PNG.
- **WebP keeps the colour under transparent pixels only with `exact=True`.** The `fix` step does this.

## The proof

Run `cutout_check.py check` on every cut-out, once for every colour it will sit on. Check the bare cut-out, before
any glow: a glow baked into the RGBA sits right against the outline and is measured as a halo. It measures what you
cannot see on white:

| Check | Fails when | Why |
|---|---|---|
| alpha | no alpha channel | a flattened export shows a box on every card |
| clip | subject or shadow touches the frame | a shadow sliced at the edge; widen the canvas, never trim the shadow |
| crop edge | the frame border steps more than 2 of 255 on the card | the faint rim of a wide glow becomes a visible rectangle |
| halo | an edge pixel is 18 of 255 outside any mix of the subject, the card and black | backdrop left in the fringe; it names the fringe colour |
| halo not run (WARN) | the subject is too small or too faint for its edge to be judged | say so rather than print ok |
| specks | islands under 0.2% of the subject (WARN) | dust left from the old background |
| stair | more than 60% of the outline has no anti-aliasing (WARN) | jagged when scaled |

Exit 0 = PASS (WARNs allowed), 1 = a FAIL, 2 = bad input. `fix` decontaminates the edge (leaving shadow pixels
black), drops specks and crops a square that keeps the whole shadow, with an edge invisible on every `--on` colour
given to it. Give `fix` every card colour, not just one: a crop clean on burgundy can still show on cream. It
refuses a source that is already cut off at the frame, because padding it would hide the cut from the check, and it
writes only .png or .webp.

Why the halo check is a triangle: a clean soft edge on the card is some mix of the subject, the card and black (a
contact shadow). A fringe from the old background is brighter than that, or a hue none of them makes. A fringe that
is only darker reads the same as a shadow and is left to your eyes on the sheet.

**Then look.** The numbers do not replace eyes. Open the `--sheet` and zoom at 8x on the places a matte fails:
heads and hair, necks, the gaps between figures, hands, hems and anything thin. On 2026-11-05 the faults were
found by marking exactly those spots on the full-size image, not on the thumbnail.

## What this cannot do

- It cannot restore what the source does not have. A subject cut off at the source frame stays cut off.
- The halo check looks at the outline next to the solid subject. A soft shadow far from the subject is not judged.
- Hair against a busy backdrop still needs a look at 8x. The matte is good, not magic.
- A stepped, blocky outline is not measured. On the real job the robe hems came out in square steps where the
  source photo was blocky at the floor, in the approved cut as well as the new one. Only the 8x look at the hems
  catches it.
- It does not judge taste: whether the glow colour, the size or the placement is right is the owner's call.

## Proof it was tested

`evals/make_fixtures.py` builds six cut-outs with known defects (clean, halo, clipped shadow, specks, no alpha,
crop line). Results and the real-job run are in `evals/benchmark.md`.
