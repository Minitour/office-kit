# Reel plan

Write this as `projects/<slug>/plan/PLAN.md` before code. It is the checklist
every later decision is tested against: if a shot does not serve the one-liner,
cut it. Long, specific plans produce the films people share; a vague plan
produces the default film (centred text on a gradient, everything fading in,
logo at the end).

```markdown
# <Reel title>

## Film in one line
<The idea and the turn, in one sentence. e.g. "Status meetings were never the
point: a wall of calendar blocks collapses into one line of shipped work, then
into the mark.">

## Audience and job
Who watches, where (launch post, landing hero, vertical feed), and the one
thing they must remember.

## Brand
Brand ID under `brands/`. Which palette roles lead (primary, secondary,
accent), which faces and weights, which mark from `brand/assets/`.

## References
- Look: a frame, film, or gallery to take palette, pacing, type, or texture
  from, and what not to take from it.
- Prior reels in this workspace to stay different from.

## Beat sheet (BPM <n>, beat = <s> s, duration <s> s)
| t (beats) | on screen | sound |
|---|---|---|
| 0-4 | hook: ... | ... |
| ... | a payoff every 3-5 s | ... |
| last 2-3 s | lockup: mark, name, tagline, url | resolve + chime |

## On-screen copy
Every line, verbatim. Where it goes huge and where it sits small.

## Formats
16:9 / 9:16 / 1:1, and what changes per format (stacking, type sizes, which
elements drop).

## Rules
- Only features that exist; list the ones you verified and where.
- No real third-party brands; invented UI for "the old way".
- No em dashes in copy.

## Delivery
What the user asked for: e.g. `renders/<slug>.mp4`,
`renders/<slug>-vertical.mp4`, a poster. Nothing is rendered until named.
```

## Example (filled, condensed)

**Film in one line.** A workspace your agents can actually use: each tool call
on the left visibly causes the change in the live document on the right.

**Audience.** Developers who already use coding agents; launch post, with a
vertical cut for professional feeds.

**Beat sheet** (120 BPM, 20 s): 0-3 s the old way (a plan stuck in a chat
window, pasted into `plan_v2_REAL.doc`) · 3-4 s headline "Stop pasting agent
output. Give it the doc." · 4-15 s split screen, one tool call per bar
(create, edit one phrase, a person's anchored comment, a reply, resolve) ·
15-17 s pull back across projects · 17-20 s lockup.

**Rules.** Every tool name and argument checked against the product's API
source. Any agent shown uses the product's own agent name, not a vendor's.
