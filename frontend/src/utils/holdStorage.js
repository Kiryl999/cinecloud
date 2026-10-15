/* The hold token is the guest's only claim to the reserved seats. Keeping it
   in sessionStorage lets the checkout survive a reload of the tab. Storage can
   be unavailable (private mode, blocked site data) - the hold then simply does
   not survive a reload, and runs out on its own. */

const key = (showtimeId) => `cinecloud.hold.${showtimeId}`;

export function loadHold(showtimeId) {
  try {
    const hold = JSON.parse(sessionStorage.getItem(key(showtimeId)));
    return hold && hold.deadline > Date.now() ? hold : null;
  } catch {
    return null;
  }
}

export function saveHold(showtimeId, hold) {
  try {
    sessionStorage.setItem(key(showtimeId), JSON.stringify(hold));
  } catch {
    // see above: the checkout still works, it just will not survive a reload
  }
}

export function clearHold(showtimeId) {
  try {
    sessionStorage.removeItem(key(showtimeId));
  } catch {
    // nothing stored, nothing to clear
  }
}
