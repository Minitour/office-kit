// Minimal Dough-safe pattern — no CDN banks, no piano, no nested backticks.
setcpm(140 / 4)

$: s("bd*4").gain(0.9)

$: s("~ ~ sd ~").gain(0.65)

$: s("hh*8").gain(0.28)

$: note("<a1 ~ [a1 g1] a1>")
  .s("sine")
  .lpf(200)
  .shape(0.45)
  .decay(0.35)
  .sustain(0.12)
  .gain(0.8)

$: n("[0 0 3 0 5 3 0 -2]*2")
  .scale("A5:phrygian")
  .s("triangle")
  .decay(0.16)
  .sustain(0)
  .gain(0.5)
