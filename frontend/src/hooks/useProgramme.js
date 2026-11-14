import { useCallback, useEffect, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';

import { hallService, movieService, showtimeService } from '../services/api';

/** Loads what an admin manages - the movies, halls and showtimes of their
    cinema - once for the whole operator area, and again after every change.
    All pages read the same copy, so a count on the overview never disagrees
    with the list behind it. */
export function useProgrammeLoader() {
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

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, [refresh]);

  const programme = useMemo(
    () =>
      lists && {
        ...lists,
        movieById: new Map(lists.movies.map((movie) => [movie.id, movie])),
        hallById: new Map(lists.halls.map((hall) => [hall.id, hall])),
      },
    [lists],
  );

  return { programme, error, refresh };
}

/** For the pages inside AdminLayout: `programme` (never null there) and
    `refresh`, to call after a change. */
export const useProgramme = () => useOutletContext();
