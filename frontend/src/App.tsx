import { type ReactNode, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { clearRequestCache } from "./api/requestCache";
import { api, isAbortError } from "./api/client";
import type { RaceSummary } from "./api/types";
import { EventTimeline } from "./components/EventTimeline";
import { FocusPanel } from "./components/FocusPanel";
import { IntelligencePanel } from "./components/IntelligencePanel";
import { LapChart } from "./components/LapChart";
import { Board, type WidgetView } from "./components/Board";
import { SettingsSheet } from "./components/SettingsSheet";
import { BACKEND_DOWN, Banner, NO_RACES, notAnalyzedText, PanelMessage } from "./components/Messages";
import { StatusBar } from "./components/StatusBar";
import { TimingList } from "./components/TimingList";
import { useFocusDriver } from "./hooks/useFocusDriver";
import { useLapData } from "./hooks/useLapData";
import { usePredictionHistory } from "./hooks/usePredictionHistory";
import { usePlayback, useReplayKeys } from "./hooks/useReplayControls";
import { useWrapped } from "./hooks/useWrapped";
import { WrappedOverlay } from "./components/wrapped/WrappedOverlay";
import { initialReplay, replayReducer } from "./state/replay";
import { addWidget, type Board as BoardModel, updateSettings, type WidgetInstance } from "./canvas/board";
import { REGISTRY } from "./canvas/registry";
import { DriverPicker, missingDriverText } from "./components/DriverPicker";
import { EventTypeChips, NO_MATCHING_EVENTS, shownTypes } from "./components/EventTypeChips";
import { AddWidget } from "./components/AddWidget";
import { Notice } from "./components/Menu";
import { activeBoard, type BoardsState } from "./canvas/store";
import { useBoards } from "./hooks/useBoards";
import { BoardMenu } from "./components/BoardMenu";
import { useBoardFiles } from "./components/BoardFiles";
import { Guide, useGuide } from "./components/Guide";
import { menuButton } from "./components/Menu";

type RacesLoad = { status: "loading" } | { status: "error" } | { status: "ok"; races: RaceSummary[] };

interface AppProps {
  /** Boards at start (tests); the dashboard starts on BATTLE. */
  initialBoards?: BoardsState;
}

export default function App({ initialBoards: startBoards }: AppProps = {}) {
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
  const [settingsOpen, setSettingsOpen] = useState(false);
  const {
    state: boards,
    dispatch: dispatchBoards,
    storageNotice,
    dismissStorageNotice,
    notice,
    setNotice,
  } = useBoards(startBoards);
  const board = activeBoard(boards);
  const guide = useGuide();
  const boardFiles = useBoardFiles({
    board,
    onImport: (imported) => dispatchBoards({ type: "add", board: imported }),
    onMessage: setNotice,
  });
  const setBoard = (update: BoardModel | ((b: BoardModel) => BoardModel)) => dispatchBoards({ type: "update", update });
  // Shared widget responses belong to one race and one served model.
  const cacheScope = useRef<string | null>(null);
  const scope = `${replay.raceId}#${lapReload}`;
  if (cacheScope.current !== scope) {
    cacheScope.current = scope;
    clearRequestCache();
  }
  const lapData = useLapData(replay.raceId, replay.lap, lapReload);
  const data = lapData.data;
  const rendered = data !== null && data.raceId === replay.raceId && data.lap === replay.lap;
  const [focusCode, setFocusCode] = useFocusDriver(data);
  // Predicted-lap lines for the chart: only laps before the shown lap are requested.
  const predicted = usePredictionHistory(data?.raceId ?? null, data?.lap ?? null, lapReload);

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

  const focusPanel = (code: string | null) =>
    data && code && <FocusPanel key={data.raceId} data={data} focusCode={code} playing={replay.playing} />;

  const lapChart = (code: string | null) =>
    data && (
      <LapChart lap={data.lap} drivers={data.state.drivers} laps={data.laps} predicted={predicted} focusCode={code} />
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

  const intelligence = (types: string[] | undefined) => {
    if (data && !data.events.analyzed) return <PanelMessage text={notAnalyzedText(data.raceId)} />;
    if (!data) return null;
    const shown = shownTypes(types);
    return (
      <IntelligencePanel
        key={data.raceId}
        raceId={data.raceId}
        events={types ? data.events.events.filter((e) => shown.includes(e.type)) : data.events.events}
        emptyText={types ? NO_MATCHING_EVENTS : undefined}
        commentaryModel={data.events.commentary_model}
        focusCode={focusCode}
        focusColor={focusColor}
      />
    );
  };

  const raceDrivers = data?.state.drivers ?? [];

  /** A driver widget's own driver: its pinned code when that driver is in the race, else the focus driver. */
  const widgetDriver = (widget: WidgetInstance): { code: string | null; missing: string | null } => {
    const pinned = widget.settings.driver ?? null;
    if (pinned === null || !data) return { code: focusCode, missing: null };
    if (raceDrivers.some((d) => d.code === pinned)) return { code: pinned, missing: null };
    return { code: focusCode, missing: pinned };
  };

  const driverView = (widget: WidgetInstance, panel: (code: string | null) => ReactNode): WidgetView => {
    const { code, missing } = widgetDriver(widget);
    return {
      subtitle: code ?? undefined,
      controls: (
        <DriverPicker
          widgetTitle={REGISTRY[widget.type].title}
          value={widget.settings.driver ?? null}
          focusCode={focusCode}
          drivers={raceDrivers}
          onChange={(driver) => setBoard((b) => updateSettings(b, widget.id, { driver }))}
        />
      ),
      body: (
        <>
          {missing && (
            <p data-testid="driver-missing" className="px-3 pt-2 text-xs text-flag-yellow">
              {missingDriverText(missing)}
            </p>
          )}
          {panel(code)}
        </>
      ),
    };
  };

  const renderWidget = (widget: WidgetInstance): WidgetView => {
    switch (widget.type) {
      case "timing":
        return { body: timing };
      case "events":
        return {
          controls: (
            <EventTypeChips
              types={widget.settings.types}
              onChange={(types) => setBoard((b) => updateSettings(b, widget.id, { types }))}
            />
          ),
          body: intelligence(widget.settings.types),
        };
      case "driver":
        return driverView(widget, focusPanel);
      case "lapchart":
        return driverView(widget, lapChart);
      case "timeline":
        return { body: timeline };
    }
  };

  return (
    <>
      <div
        data-testid="layout"
        data-race={data?.raceId ?? ""}
        data-lap={data?.lap ?? ""}
        className="flex min-h-full flex-col gap-2 bg-zinc-950 p-2 font-mono text-zinc-100"
      >
        <header data-testid="status-bar" className="rounded-md border border-zinc-800 bg-card px-3 py-2">
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
            onOpenSettings={() => {
              dispatch({ type: "stop" });
              setSettingsOpen(true);
            }}
            boardControls={
              <>
              <BoardMenu state={boards} dispatch={dispatchBoards} fileActions={boardFiles.menuItems} />
              <AddWidget
                onAdd={(type) => {
                  const result = addWidget(board, type);
                  if (result.ok) setBoard(result.board);
                  else setNotice(result.message);
                }}
              />
              <button
                type="button"
                aria-label="How to use the board"
                title="How to use the board"
                className={menuButton}
                onClick={guide.reopen}
              >
                ?
              </button>
              </>
            }
          />
        </header>
        {banner}
        {storageNotice && <Notice testId="storage-notice" text={storageNotice} onDismiss={dismissStorageNotice} />}
        {notice && <Notice text={notice} onDismiss={() => setNotice(null)} />}
        {boardFiles.fileInput}
        <main className="min-h-0 flex-1">
          <Board key={board.id} board={board} onChange={setBoard} renderWidget={renderWidget} />
        </main>
      </div>
      {guide.open && <Guide onClose={guide.close} />}
      <WrappedOverlay state={wrapped.state} onClose={wrapped.close} teamColors={teamColors} />
      {settingsOpen && (
        <SettingsSheet
          onClose={() => setSettingsOpen(false)}
          onSaved={() => {
            setSettingsOpen(false);
            // Re-fetch the current lap (and the chart's predictions) from the newly served model.
            setLapReload((n) => n + 1);
          }}
        />
      )}
    </>
  );
}
