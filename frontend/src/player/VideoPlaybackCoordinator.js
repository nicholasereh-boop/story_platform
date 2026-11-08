// One video at a time, across the whole ResourceBoard app (stories, marketplace previews and Academy lessons).
//
// HOW IT WORKS
//  * Every YouTube player registers itself here with a stable id and a pause() function, and unregisters when its component
//    goes away.
//  * When a player reports that it started PLAYING it calls notifyPlaying(id). The coordinator pauses every OTHER registered
//    player, and tells other tabs of the same browser (same origin) through a BroadcastChannel, which pause theirs.
//  * The coordinator only ever PAUSES. It never starts or resumes a video, so browser autoplay rules cannot get in its way.
//  * Only "started playing" is broadcast, never "paused", so a pause that the coordinator itself caused cannot bounce back
//    and forth between tabs.
//  * If two tabs start a video at almost the same moment, the later start wins in both tabs (ties go to the larger tab id).
//
// WHAT IT DOES NOT PROMISE
//  * Same browser, same origin only. A BroadcastChannel is not shared between different devices, different browsers, private
//    windows, or a different sub-domain. Stopping a video on ANOTHER DEVICE would need a server-side heartbeat/lease and
//    could still not be instant when that device is offline.
//  * Browsers without BroadcastChannel (Safari before 15.4) still coordinate every player inside one tab.
//  * Nothing is written to localStorage, sessionStorage or cookies, so there is nothing to add to the privacy tables.
const CHANNEL_NAME = "resourceboard-video-playback";
const MESSAGE_VERSION = 1;

const defaultChannelFactory = () => {
  if (typeof BroadcastChannel !== "function") return null;
  const channel = new BroadcastChannel(CHANNEL_NAME);
  channel.unref?.(); // Node-based test runners: an open channel must not keep the process alive
  return channel;
};

const randomTabId = () => {
  try {
    if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  } catch { /* fall through */ }
  return `tab-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
};

export function createCoordinator({ channelFactory = defaultChannelFactory, now = () => Date.now(), tabId = randomTabId() } = {}) {
  const players = new Map(); // player id -> { pause }
  let activeId = null; // the player this tab last saw start playing (and has not seen stop)
  let lastPlayAt = 0;
  let channel = null;
  let counter = 0;

  const pauseSafely = (entry) => {
    try { entry.pause(); } catch { /* the player is already gone or not ready; nothing to pause */ }
  };
  const pauseAllExcept = (keepId) => {
    for (const [id, entry] of [...players]) if (id !== keepId) pauseSafely(entry);
  };

  function onMessage(event) {
    const data = event?.data;
    if (!data || data.v !== MESSAGE_VERSION || data.type !== "playing") return;
    if (typeof data.tabId !== "string" || data.tabId === tabId || !Number.isFinite(data.at)) return;
    // A video started here AFTER the other tab's one (or at the same instant, with the larger tab id): this tab keeps playing
    // and the other tab will pause itself when it receives our message.
    const localWins = activeId !== null && (lastPlayAt > data.at || (lastPlayAt === data.at && tabId > data.tabId));
    if (localWins) return;
    activeId = null;
    pauseAllExcept(null);
  }

  function openChannel() {
    if (channel) return;
    try {
      channel = channelFactory?.() || null;
      if (channel) channel.onmessage = onMessage;
    } catch {
      channel = null; // no cross-tab coordination here; players in this tab are still coordinated
    }
  }

  function closeChannel() {
    if (!channel) return;
    try { channel.onmessage = null; channel.close?.(); } catch { /* already closed */ }
    channel = null;
  }

  return {
    tabId,

    /** A fresh, unique player id, e.g. "story-3". */
    createId: (prefix = "player") => `${prefix}-${++counter}`,

    /**
     * Start coordinating one player. `pause` must pause it (and must be safe to call at any time).
     * Returns the function that stops coordinating it; call that when the component unmounts.
     */
    register(id, { pause }) {
      const entry = { pause };
      players.set(id, entry);
      openChannel();
      return () => {
        // Only remove our own entry: a newer player may have re-used the id in the meantime.
        if (players.get(id) === entry) {
          players.delete(id);
          if (activeId === id) activeId = null;
        }
        if (players.size === 0) closeChannel();
      };
    },

    /** The player started playing: pause every other player here and in other tabs. */
    notifyPlaying(id) {
      if (!players.has(id)) return false;
      activeId = id;
      lastPlayAt = now();
      pauseAllExcept(id);
      try {
        channel?.postMessage({ v: MESSAGE_VERSION, type: "playing", tabId, playerId: id, at: lastPlayAt });
      } catch { /* the channel closed under us; local coordination already happened */ }
      return true;
    },

    /** The player paused or ended (by the viewer or by the coordinator). Nothing is broadcast. */
    notifyStopped(id) {
      if (activeId === id) activeId = null;
    },

    getActiveId: () => activeId,
    playerCount: () => players.size,
  };
}

/** The one coordinator the whole app shares. */
export const coordinator = createCoordinator();
