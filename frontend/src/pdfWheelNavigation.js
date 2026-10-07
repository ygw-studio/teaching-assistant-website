export function createPdfWheelHandler({ viewport, getState, changePage, now = () => performance.now() }) {
  let distance = 0
  let direction = 0
  let lastEventAt = -Infinity
  let locked = false
  let nextAllowedAt = -Infinity

  return (event) => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || !event.deltaY || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return
    const state = getState()
    if (!state?.totalPages || state.error || !event.cancelable) return

    const time = now()
    if (time - lastEventAt >= 180) {
      distance = 0
      locked = false
    }
    lastEventAt = time
    if (state.busy || locked) {
      event.preventDefault()
      return
    }

    const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? viewport.clientHeight : 1)
    const nextDirection = Math.sign(delta)
    const maxScroll = Math.max(0, viewport.scrollHeight - viewport.clientHeight)
    const canScroll = nextDirection > 0 ? viewport.scrollTop < maxScroll - 1 : viewport.scrollTop > 1
    if (canScroll) {
      event.preventDefault()
      viewport.scrollTop = Math.max(0, Math.min(maxScroll, viewport.scrollTop + delta))
      distance = 0
      return
    }

    const nextPage = state.page + nextDirection
    if (nextPage < 1 || nextPage > state.totalPages) {
      distance = 0
      return
    }
    event.preventDefault()
    if (time < nextAllowedAt) return
    if (direction !== nextDirection) distance = 0
    direction = nextDirection
    distance += Math.abs(delta)
    if (distance < 40) return

    // A touchpad's inertial tail belongs to the same gesture, not another page turn.
    locked = true
    nextAllowedAt = time + 300
    distance = 0
    changePage(nextPage, direction)
  }
}
