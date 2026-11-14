import { useCallback, useEffect, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';

import { hallService, movieService, showtimeService } from '../services/api';

/** Loads what an admin manages - the movies, halls and showtimes of their
    cinema - for the whole operator area: again after every change, and
    whenever `reloadKey` changes. All pages read the same copy, so a count on
    the overview never disagrees with the list behind it. */
export function useProgrammeLoader(reloadKey) {
  const [lists, setLists] = useState(null);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    const [movies, halls, showtimes] = await Promise.all([
      movieService.list(),
      hallService.list(),
      showtimeService.list(),
    ]);
    setLists({ movies, halls, showtimes });
    setError(null);
  }, []);

  // the old copy stays on screen until the new one is there
  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, [refresh, reloadKey]);

  const programme = useMemo(
    () =>
      lists && {
        ...lists,
        movieById: new Map(lists.movies.map((movie) => [movie.id, movie])),
        hallById: new Map(lists.halls.map((hall) => [hall.id, hall])),
        showtimeById: new Map(lists.showtimes.map((showtime) => [showtime.id, showtime])),
      },
    [lists],
  );

  return { programme, error, refresh };
}

/** For the pages inside AdminLayout: `programme` (never null there) and
    `refresh`, to call after a change. */
export const useProgramme = () => useOutletContext();
