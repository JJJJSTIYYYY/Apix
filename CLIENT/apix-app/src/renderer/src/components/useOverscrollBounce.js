import { onMounted, onBeforeUnmount } from 'vue'

/* ------------------------
   useOverscrollBounce
------------------------- */
export function useOverscrollBounce(
  getWrapEl,
  scrollInnerRef,
  options = {}
) {
  /* ------------------------
     Config
  ------------------------- */
  const MAX_BOUNCE = options.maxBounce ?? 30
  const DAMPING = options.damping ?? 0.35
  const SPRING_K = options.springK ?? 400
  const SPRING_C = options.springC ?? 20
  const BOUNCE_IDLE_MS = options.idleMs ?? 40

  // absorb touchpad wheel inertia after forced bounce-back
  const FORCE_RELEASE_DELAY = options.forceReleaseDelay ?? 1

  /* ------------------------
     Physics state
  ------------------------- */
  let currentY = 0       // rendered offset
  let targetY = 0        // target offset driven by wheel
  let velocity = 0       // spring velocity

  let rafId = null
  let lastT = 0
  let idleTimer = null
  let forceReleaseTimer = null

  // reached MAX_BOUNCE -> force bounce-back, ignore wheel
  let forceReleasing = false
  let lastScrollDir = 0 // -1 up, 1 down

  console.log("Bounce animation prepared.")

  /* ------------------------
     Utils
  ------------------------- */
  function getScrollDir(deltaY) {
    if (deltaY > 0) return 1
    if (deltaY < 0) return -1
    return 0
  }

  /* ------------------------
     Rubber-band clamp
  ------------------------- */
  function rubberClamp(y) {
    const s = MAX_BOUNCE * 2
    if (y > 0) {
      return (s * y) / (s + y)
    } else if (y < 0) {
      const x = -y
      return -(s * x) / (s + x)
    }
    return 0
  }

  /* ------------------------
     Apply transform
  ------------------------- */
  function applyTransform(y) {
    const el = scrollInnerRef.value
    if (!el) return

    el.style.willChange = 'transform'
    el.style.transform = `translate3d(0, ${y.toFixed(2)}px, 0)`
  }

  /* ------------------------
     Spring RAF loop
  ------------------------- */
  function startAnim() {
    if (rafId !== null) return

    lastT = performance.now()

    function step(t) {
      const dt = Math.min(32, t - lastT) / 1000
      lastT = t

      // spring: a = -k(x - target) - c*v
      const a =
        -SPRING_K * (currentY - targetY) -
        SPRING_C * velocity

      velocity += a * dt
      currentY += velocity * dt

      applyTransform(currentY)

      const done =
        Math.abs(currentY - targetY) < 0.15 &&
        Math.abs(velocity) < 5

      if (done) {
        currentY = targetY
        velocity = 0
        applyTransform(currentY)

        // delay unlock to absorb touchpad inertia
        clearTimeout(forceReleaseTimer)
        forceReleaseTimer = setTimeout(() => {
          forceReleasing = false
          forceReleaseTimer = null
        }, FORCE_RELEASE_DELAY)

        rafId = null
        return
      }

      rafId = requestAnimationFrame(step)
    }

    rafId = requestAnimationFrame(step)
  }

  /* ------------------------
     Wheel idle -> return to 0
  ------------------------- */
  function scheduleReturnToZero() {
    if (idleTimer !== null) clearTimeout(idleTimer)

    idleTimer = setTimeout(() => {
      targetY = 0
      console.log("Bounce animation start.")
      startAnim()
    }, BOUNCE_IDLE_MS)
  }

  /* ------------------------
     Wheel handler
  ------------------------- */
  function onWheel(e) {
    const wrap = getWrapEl()
    if (!wrap) return

    const dir = getScrollDir(e.deltaY)

    // if user scrolls in opposite direction, unlock immediately
    if (forceReleasing && dir !== 0 && dir !== lastScrollDir) {
      clearTimeout(forceReleaseTimer)
      forceReleaseTimer = null
      forceReleasing = false
    }

    lastScrollDir = dir

    const atTop = wrap.scrollTop <= 0
    const atBottom =
      wrap.scrollTop + wrap.clientHeight >= wrap.scrollHeight - 1

    const isOverscroll =
      (atTop && e.deltaY < 0) ||
      (atBottom && e.deltaY > 0)

    // not overscroll -> reset transform
    if (!isOverscroll) {
      if (targetY !== 0 || currentY !== 0) {
        targetY = 0
        console.log("Bounce animation start.")
        startAnim()
      }
      return
    }

    // ignore wheel during forced bounce-back
    if (forceReleasing) {
      e.preventDefault()
      return
    }

    e.preventDefault()

    // update target offset
    targetY += -e.deltaY * DAMPING
    targetY = rubberClamp(targetY)

    // reach MAX_BOUNCE -> immediate bounce-back
    if (Math.abs(targetY) >= MAX_BOUNCE * 0.98) {
      forceReleasing = true
      targetY = 0
      console.log("Bounce animation start.")
      startAnim()
      return
    }

    console.log("Bounce animation start.")
    startAnim()
    scheduleReturnToZero()
  }

  /* ------------------------
     Lifecycle
  ------------------------- */
  onMounted(() => {
    const wrap = getWrapEl()
    if (!wrap) return
    console.log("Bounce animation get container.")
    wrap.addEventListener('wheel', onWheel, { passive: false })
  })

  onBeforeUnmount(() => {
    const wrap = getWrapEl()
    if (wrap) wrap.removeEventListener('wheel', onWheel)

    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    if (idleTimer !== null) {
      clearTimeout(idleTimer)
      idleTimer = null
    }
    if (forceReleaseTimer !== null) {
      clearTimeout(forceReleaseTimer)
      forceReleaseTimer = null
    }
  })
}
