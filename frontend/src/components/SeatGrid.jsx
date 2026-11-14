function groupByRow(seats) {
  const rows = new Map();
  for (const seat of seats) {
    if (!rows.has(seat.row_number)) rows.set(seat.row_number, []);
    rows.get(seat.row_number).push(seat);
  }
  return [...rows.entries()];
}

/**
 * The hall as a grid of seat buttons. `stateOf(seat)` names the seat's state,
 * which is also its CSS modifier: "free", "chosen" or "taken" on the visitor
 * pages. Seats in one of `disabledStates` cannot be clicked.
 */
function SeatGrid({ seats, stateOf, onToggle, disabledStates = ["taken"] }) {
  return (
    // A wide hall must stay scrollable to its first seat, hence the wrapper
    <div className="seatmap__scroll">
      <div className="seatmap__rows">
        {groupByRow(seats).map(([row, rowSeats]) => (
          <div className="seatmap__row" key={row}>
            <span className="seatmap__label">{row}</span>
            {rowSeats.map((seat) => {
              const state = stateOf(seat);
              return (
                <button
                  key={seat.id}
                  type="button"
                  className={`seat seat--${state}`}
                  disabled={disabledStates.includes(state)}
                  aria-pressed={state === "chosen"}
                  aria-label={`Row ${row}, seat ${seat.seat_number}, ${state}`}
                  onClick={() => onToggle(seat)}
                >
                  {seat.seat_number}
                </button>
              );
            })}
            <span className="seatmap__label">{row}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default SeatGrid;
