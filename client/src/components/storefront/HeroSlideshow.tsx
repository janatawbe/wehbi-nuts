import { motion, useReducedMotion } from 'framer-motion'
import { type MouseEvent, useEffect, useState } from 'react'
import pic1 from '../../assets/hero-slideshow/pic1.png'
import pic2 from '../../assets/hero-slideshow/pic2.png'
import pic3 from '../../assets/hero-slideshow/pic3.png'
import pic4 from '../../assets/hero-slideshow/pic4.png'

interface Slide {
  src: string
  /** Each photo keeps its own frame identity (a distinct organic radius)
   * as it moves through slots, so the collage reads as hand-placed
   * rather than four identical cards cycling through a template. */
  radius: string
}

const SLIDES: Slide[] = [
  { src: pic1, radius: '3rem 1.25rem 3rem 1.25rem' },
  { src: pic2, radius: '1.75rem 1.75rem 0.5rem 1.75rem' },
  { src: pic3, radius: '2.5rem' },
  { src: pic4, radius: '0.75rem 2.75rem 0.75rem 2.75rem' },
]

// Four roles in a living stack: one dominant photo up front, two smaller
// ones layered behind/beside it (a glimpse of what's coming next), and
// one fully offstage waiting its turn. Every rotation, each photo simply
// advances one role -- dominant becomes right, right becomes left, left
// retreats offstage, and offstage arrives as the new dominant. Framer
// Motion tweens each photo's own position/size/rotation between its old
// and new role, so the whole stack reads as one continuous reshuffle
// rather than a cut between static frames.
const ROLE_ORDER = ['dominant', 'right', 'left', 'offstage'] as const
type Role = (typeof ROLE_ORDER)[number]

const ROLE_STYLE: Record<
  Role,
  { top: string; left: string; width: string; height: string; rotate: number; zIndex: number; opacity: number; scale: number; boxShadow: string }
> = {
  dominant: {
    top: '4%',
    left: '2%',
    width: '64%',
    height: '80%',
    rotate: -3,
    zIndex: 40,
    opacity: 1,
    scale: 1,
    boxShadow: '0 30px 50px -18px rgba(64, 42, 26, 0.4)',
  },
  right: {
    top: '0%',
    left: '58%',
    width: '40%',
    height: '46%',
    rotate: 8,
    zIndex: 30,
    opacity: 1,
    scale: 1,
    boxShadow: '0 18px 30px -14px rgba(64, 42, 26, 0.3)',
  },
  left: {
    top: '56%',
    left: '0%',
    width: '36%',
    height: '42%',
    rotate: -9,
    zIndex: 20,
    opacity: 1,
    scale: 1,
    boxShadow: '0 18px 30px -14px rgba(64, 42, 26, 0.3)',
  },
  offstage: {
    top: '38%',
    left: '32%',
    width: '28%',
    height: '28%',
    rotate: 0,
    zIndex: 5,
    opacity: 0,
    scale: 0.82,
    boxShadow: 'none',
  },
}

const ROTATE_INTERVAL_MS = 4200
const MAX_TILT_DEGREES = 5

/** The hero's right-side visual: a living editorial collage of the 4
 * local photos, not a slideshow-in-a-frame. Three photos are always
 * visible at once -- one dominant, two smaller and layered behind it --
 * and every few seconds the whole stack reshuffles one step, so a new
 * photo glides into the dominant spot while the others settle back.
 * A very subtle desktop-only mouse tilt adds a touch of depth; both the
 * reshuffle and the tilt are skipped entirely for prefers-reduced-motion,
 * which simply leaves the (already visually complete) static collage in
 * place. */
export function HeroSlideshow() {
  const [activeIndex, setActiveIndex] = useState(0)
  const [tilt, setTilt] = useState({ rotateX: 0, rotateY: 0 })
  const prefersReducedMotion = useReducedMotion()

  useEffect(() => {
    if (prefersReducedMotion) return
    const timer = setInterval(() => {
      setActiveIndex((previous) => (previous + 1) % SLIDES.length)
    }, ROTATE_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [prefersReducedMotion])

  const handleMouseMove = (event: MouseEvent<HTMLDivElement>) => {
    if (prefersReducedMotion) return
    const rect = event.currentTarget.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) return
    const relativeX = (event.clientX - rect.left) / rect.width - 0.5
    const relativeY = (event.clientY - rect.top) / rect.height - 0.5
    setTilt({ rotateY: relativeX * MAX_TILT_DEGREES * 2, rotateX: relativeY * -MAX_TILT_DEGREES * 2 })
  }

  const resetTilt = () => setTilt({ rotateX: 0, rotateY: 0 })

  return (
    <div
      onMouseMove={handleMouseMove}
      onMouseLeave={resetTilt}
      className="relative h-[22rem] w-full [perspective:1400px] sm:h-[27rem] lg:h-[31rem]"
      role="img"
      aria-label="Photos of Wehbi Nuts roasted coffee, nuts, and spices"
    >
      <motion.div
        className="relative h-full w-full"
        style={{ transformStyle: 'preserve-3d' }}
        animate={{ rotateX: tilt.rotateX, rotateY: tilt.rotateY }}
        transition={{ type: 'spring', stiffness: 60, damping: 14 }}
      >
        {SLIDES.map((slide, index) => {
          const role = ROLE_ORDER[(index - activeIndex + SLIDES.length) % SLIDES.length]
          const style = ROLE_STYLE[role]
          return (
            <motion.div
              key={slide.src}
              data-slot={role}
              className="absolute overflow-hidden border-[3px] border-white"
              style={{ borderRadius: slide.radius }}
              animate={{
                top: style.top,
                left: style.left,
                width: style.width,
                height: style.height,
                rotate: style.rotate,
                zIndex: style.zIndex,
                opacity: style.opacity,
                scale: style.scale,
                boxShadow: style.boxShadow,
              }}
              transition={{ duration: prefersReducedMotion ? 0 : 0.9, ease: [0.22, 1, 0.36, 1] }}
            >
              <img src={slide.src} alt="" className="h-full w-full object-cover" />
            </motion.div>
          )
        })}
      </motion.div>

      {/* Small brand-color details tucked into the gaps around the
          photography -- never on top of it. */}
      <div
        className="pointer-events-none absolute -bottom-3 left-1 h-9 w-9 rounded-full bg-wehbi-gold-400 shadow-sm sm:h-12 sm:w-12"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute -top-3 right-8 h-11 w-11 rounded-full border-[3px] border-wehbi-red-400/70 sm:h-14 sm:w-14"
        aria-hidden="true"
      />
    </div>
  )
}
