import { useEffect, useReducer, useState } from "react";
import { api, isAbortError } from "./api/client";
import type { RaceSummary } from "./api/types";
import { Layout } from "./components/Layout";
import { BACKEND_DOWN, Banner, NO_RACES, notAnalyzedText, PanelMessage } from "./components/Messages";
import { StatusBar } from "./components/StatusBar";
import { useLapData } from "./hooks/useLapData";
import { usePlayback, useReplayKeys } from "./hooks/useReplayControls";
import { initialReplay, replayReducer } from "./state/replay";

type RacesLoad = { status: "loading" } | { status: "error" } | { status: "ok"; races: RaceSummary[] };

export default function App() {
  const [racesLoad, setRacesLoad] = useState<RacesLoad>({ status: "loading" });
  const [replay, dispatch] = useReducer(replayReducer, initialReplay);

  useEffect(() => {
    if (racesLoad.status !== "loading") return;
    const controller = new AbortController();
    api.races(controller.signal).then(
      (races) => {
        setRacesLoad({ status: "ok", races });
        if (races.length > 0) {
          dispatch({ type: "selectRace", raceId: races[0].race_id, totalLaps: races[0].total_laps });
        }
      },
      (err: unknown) => {
        if (!isAbortError(err)) setRacesLoad({ status: "error" });
      },
    );
    return () => controller.abort();
  }, [racesLoad.status]);

  const [lapReload, setLapReload] = useState(0);
  const lapData = useLapData(replay.raceId, replay.lap, lapReload);
  const data = lapData.data;
  const rendered = data !== null && data.raceId === replay.raceId && data.lap === replay.lap;

  useEffect(() => {
    if (lapData.error && replay.playing) dispatch({ type: "stop" });
  }, [lapData.error, replay.playing]);

  usePlayback(replay, rendered, dispatch);
  useReplayKeys(dispatch);

  const races = racesLoad.status === "ok" ? racesLoad.races : [];

  let banner = null;
  if (racesLoad.status === "error") {
    banner = <Banner text={BACKEND_DOWN} onRetry={() => setRacesLoad({ status: "loading" })} />;
  } else if (racesLoad.status === "ok" && races.length === 0) {
    banner = <Banner text={NO_RACES} />;
  } else if (lapData.error) {
    banner = (
      <Banner
        text={`Could not load lap ${replay.lap}: ${lapData.error.message}`}
        onRetry={() => setLapReload((n) => n + 1)}
      />
    );
  }

  const intelligence =
    data && !data.events.analyzed ? <PanelMessage text={notAnalyzedText(data.raceId)} /> : null;

  return (
    <Layout
      shownRaceId={data?.raceId}
      shownLap={data?.lap}
      banner={banner}
      statusBar={
        <StatusBar races={races} replay={replay} dispatch={dispatch} trackStatus={data?.state.track_status} />
      }
      intelligence={intelligence}
    />
  );
}
