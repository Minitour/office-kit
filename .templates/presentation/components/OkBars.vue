<script setup lang="ts">
/**
 * OkBars — a grouped bar chart as inline SVG, themed by the brand.
 *
 * Carries the literal numbers from a results table instead of a pasted PNG,
 * so the chart re-themes with the brand and stays legible when exported.
 * Fills are the CSS classes `.ok-s0` … `.ok-s3` (primary, accent, secondary,
 * muted) from styles/brand.css; nothing here names a colour.
 *
 *   <OkBars
 *     :groups="[{ label: 'Baseline', values: [42, 38] }, { label: 'Ours', values: [67, 61] }]"
 *     :series="['Accuracy', 'Recall']"
 *     unit="%" :reference="50" reference-label="Target"
 *   />
 *
 * `errors` on a group draws ± error bars; `horizontal` flips the axes;
 * `max` fixes the scale so two charts compare.
 */
import { computed } from 'vue'

interface Group {
  label: string
  values: number[]
  errors?: number[]
}

const props = withDefaults(
  defineProps<{
    groups: Group[]
    series?: string[]
    horizontal?: boolean
    max?: number
    reference?: number
    referenceLabel?: string
    unit?: string
    decimals?: number
    height?: number
    ariaLabel?: string
  }>(),
  {
    series: () => [],
    horizontal: false,
    unit: '',
    decimals: 0,
    height: 300,
    ariaLabel: 'Bar chart',
  },
)

const width = 800
const pad = { top: 26, right: 28, bottom: 40, left: 60 }
const labelGutter = computed(() => (props.horizontal ? 132 : 0))

const seriesCount = computed(() =>
  Math.max(1, ...props.groups.map((g) => g.values.length)),
)

const top = computed(() => {
  const highs = props.groups.flatMap((g) =>
    g.values.map((v, i) => v + (g.errors?.[i] ?? 0)),
  )
  const m = props.max ?? Math.max(0, ...highs, props.reference ?? 0)
  return m > 0 ? m * 1.1 : 1
})

const plotW = computed(() => width - pad.left - pad.right - labelGutter.value)
const plotH = computed(() => props.height - pad.top - pad.bottom)

const fmt = (v: number) => `${v.toFixed(props.decimals)}${props.unit}`

interface Bar {
  x: number
  y: number
  w: number
  h: number
  cls: string
  value: number
  lx: number
  ly: number
  anchor: string
  err?: { x1: number; y1: number; x2: number; y2: number }
}

const bars = computed<Bar[]>(() => {
  const out: Bar[] = []
  const n = props.groups.length || 1
  const slot = (props.horizontal ? plotH.value : plotW.value) / n
  const inner = slot * 0.72
  const bw = inner / seriesCount.value
  props.groups.forEach((g, gi) => {
    g.values.forEach((v, si) => {
      const cls = `ok-s${Math.min(si, 3)}`
      const err = g.errors?.[si] ?? 0
      const start = gi * slot + (slot - inner) / 2 + si * bw
      if (props.horizontal) {
        const x0 = pad.left + labelGutter.value
        const len = (v / top.value) * plotW.value
        const y = pad.top + start
        const bar: Bar = {
          x: x0, y, w: len, h: bw - 2, cls, value: v,
          lx: x0 + len + 6, ly: y + (bw - 2) / 2 + 4, anchor: 'start',
        }
        if (err) {
          const e = (err / top.value) * plotW.value
          bar.err = { x1: x0 + len - e, y1: y + (bw - 2) / 2, x2: x0 + len + e, y2: y + (bw - 2) / 2 }
        }
        out.push(bar)
      } else {
        const h = (v / top.value) * plotH.value
        const x = pad.left + start
        const y = pad.top + plotH.value - h
        const bar: Bar = {
          x, y, w: bw - 2, h, cls, value: v,
          lx: x + (bw - 2) / 2, ly: y - 6, anchor: 'middle',
        }
        if (err) {
          const e = (err / top.value) * plotH.value
          bar.err = { x1: x + (bw - 2) / 2, y1: y - e, x2: x + (bw - 2) / 2, y2: y + e }
        }
        out.push(bar)
      }
    })
  })
  return out
})

const groupLabels = computed(() => {
  const n = props.groups.length || 1
  const slot = (props.horizontal ? plotH.value : plotW.value) / n
  return props.groups.map((g, gi) =>
    props.horizontal
      ? { text: g.label, x: pad.left + labelGutter.value - 10, y: pad.top + gi * slot + slot / 2 + 4, anchor: 'end' }
      : { text: g.label, x: pad.left + gi * slot + slot / 2, y: props.height - pad.bottom + 20, anchor: 'middle' },
  )
})

const referenceLine = computed(() => {
  if (props.reference == null) return null
  if (props.horizontal) {
    const x = pad.left + labelGutter.value + (props.reference / top.value) * plotW.value
    return { x1: x, y1: pad.top - 6, x2: x, y2: pad.top + plotH.value, lx: x + 6, ly: pad.top - 8 }
  }
  const y = pad.top + plotH.value - (props.reference / top.value) * plotH.value
  return { x1: pad.left, y1: y, x2: width - pad.right, y2: y, lx: width - pad.right, ly: y - 6 }
})

const axis = computed(() =>
  props.horizontal
    ? { x1: pad.left + labelGutter.value, y1: pad.top - 4, x2: pad.left + labelGutter.value, y2: pad.top + plotH.value }
    : { x1: pad.left, y1: pad.top + plotH.value, x2: width - pad.right, y2: pad.top + plotH.value },
)
</script>

<template>
  <figure class="ok-bars" role="img" :aria-label="ariaLabel">
    <svg :viewBox="`0 0 ${width} ${height}`" preserveAspectRatio="xMidYMid meet">
      <line class="ok-bars-axis" :x1="axis.x1" :y1="axis.y1" :x2="axis.x2" :y2="axis.y2" />
      <template v-for="(bar, i) in bars" :key="i">
        <rect :class="bar.cls" :x="bar.x" :y="bar.y" :width="bar.w" :height="bar.h" rx="3" />
        <line
          v-if="bar.err"
          class="ok-bars-error"
          :x1="bar.err.x1" :y1="bar.err.y1" :x2="bar.err.x2" :y2="bar.err.y2"
        />
        <text class="ok-bars-value" :x="bar.lx" :y="bar.ly" :text-anchor="bar.anchor">
          {{ fmt(bar.value) }}
        </text>
      </template>
      <text
        v-for="(label, i) in groupLabels"
        :key="`g${i}`"
        class="ok-bars-label"
        :x="label.x" :y="label.y" :text-anchor="label.anchor"
      >
        {{ label.text }}
      </text>
      <template v-if="referenceLine">
        <line
          class="ok-bars-reference"
          :x1="referenceLine.x1" :y1="referenceLine.y1" :x2="referenceLine.x2" :y2="referenceLine.y2"
        />
        <text
          v-if="referenceLabel"
          class="ok-bars-reference-label"
          :x="referenceLine.lx" :y="referenceLine.ly"
          :text-anchor="horizontal ? 'start' : 'end'"
        >
          {{ referenceLabel }} {{ fmt(reference as number) }}
        </text>
      </template>
    </svg>
    <figcaption v-if="series.length > 1" class="ok-bars-legend">
      <span v-for="(name, i) in series" :key="name">
        <i :class="`ok-s${Math.min(i, 3)}`" aria-hidden="true" />{{ name }}
      </span>
    </figcaption>
  </figure>
</template>
