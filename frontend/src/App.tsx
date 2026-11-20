import { useEffect, useMemo, useReducer, useState } from "react";
import { api, isAbortError } from "./api/client";
import type { RaceSummary } from "./api/types";
import { EventTimeline } from "./components/EventTimeline";
import { FocusPanel } from "./components/FocusPanel";
import { IntelligencePanel } from "./components/IntelligencePanel";
import { LapChart } from "./components/LapChart";
import { Layout } from "./components/Layout";
import { BACKEND_DOWN, Banner, NO_RACES, notAnalyzedText, PanelMessage } from "./components/Messages";
import { StatusBar } from "./components/StatusBar";
import { TimingList } from "./components/TimingList";
import { useFocusDriver } from "./hooks/useFocusDriver";
import { useLapData } from "./hooks/useLapData";
import { usePlayback, useReplayKeys } from "./hooks/useReplayControls";
import { useWrapped } from "./hooks/useWrapped";
import { WrappedOverlay } from "./components/wrapped/WrappedOverlay";
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
  const [focusCode, setFocusCode] = useFocusDriver(data);

  useEffect(() => {
    if (lapData.error && replay.playing) dispatch({ type: "stop" });
  }, [lapData.error, replay.playing]);

  const wrapped = useWrapped(replay.raceId);
  const atFinalLap = rendered && data !== null && data.lap === replay.totalLaps;

  usePlayback(replay, rendered, dispatch);
  useReplayKeys(dispatch, wrapped.state.status === "closed");

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

  const timing = data && (
    <TimingList
      lap={data.lap}
      drivers={data.state.drivers}
      laps={data.laps}
      predictions={data.predictions.drivers}
      positions={data.positions.drivers}
      focusCode={focusCode}
      onFocus={setFocusCode}
    />
  );

  const focus = data && focusCode && (
    <FocusPanel key={data.raceId} data={data} focusCode={focusCode} playing={replay.playing} />
  );

  const chart = data && (
    <LapChart lap={data.lap} drivers={data.state.drivers} laps={data.laps} focusCode={focusCode} />
  );

  const focusColor = data?.state.drivers.find((d) => d.code === focusCode)?.team_color ?? null;
  const teamColors = useMemo(
    () => Object.fromEntries((data?.state.drivers ?? []).map((d) => [d.code, d.team_color])),
    [data?.state.drivers],
  );

  const timeline = data && data.events.analyzed && (
    <EventTimeline
      lap={data.lap}
      totalLaps={replay.totalLaps}
      events={data.events.events}
      focusCode={focusCode}
      focusColor={focusColor}
      onJump={(lap) => {
        dispatch({ type: "stop" });
        dispatch({ type: "setLap", lap });
      }}
    />
  );

  let intelligence = null;
  if (data && !data.events.analyzed) {
    intelligence = <PanelMessage text={notAnalyzedText(data.raceId)} />;
  } else if (data) {
    intelligence = (
      <IntelligencePanel
        key={data.raceId}
        raceId={data.raceId}
        events={data.events.events}
        focusCode={focusCode}
        focusColor={focusColor}
      />
    );
  }

  return (
    <>
      <Layout
        shownRaceId={data?.raceId}
        shownLap={data?.lap}
        banner={banner}
        statusBar={
          <StatusBar
            races={races}
            replay={replay}
            dispatch={dispatch}
            trackStatus={data?.state.track_status}
            wrappedLocked={!atFinalLap || !focusCode}
            onOpenWrapped={() => {
              if (data && focusCode && atFinalLap) {
                dispatch({ type: "stop" });
                wrapped.open(data.raceId, data.lap, focusCode);
              }
            }}
          />
        }
        timing={timing}
        focus={focus}
        chart={chart}
        timeline={timeline}
        intelligence={intelligence}
      />
      <WrappedOverlay state={wrapped.state} onClose={wrapped.close} teamColors={teamColors} />
    </>
  );
}
