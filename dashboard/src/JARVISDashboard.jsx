import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence, useMotionValue, useTransform, animate } from "framer-motion";

/* ═══════════════════════════════════════════════════════════════
   JARVIS HUD — Inter + JetBrains Mono — Aixor-inspired
   Pure black · white text · animated gradient shimmer
═══════════════════════════════════════════════════════════════ */

const MOCK = {
  leds:      { green: false, white: true, red: false },
  awake:     false,
  listening: false,
  agents: [
    { name: "Brain",    sub: "llama3.2:3b",      status: "idle",   calls: 47 },
    { name: "Coder",    sub: "qwen2.5-coder:3b", status: "idle",   calls: 12 },
    { name: "IoT",      sub: "MQTT",             status: "active", calls: 8  },
    { name: "Gmail",    sub: "IMAP",             status: "active", calls: 3  },
    { name: "Slack",    sub: "API",              status: "active", calls: 1  },
    { name: "Telegram", sub: "MTProto",          status: "active", calls: 5  },
    { name: "Memory",   sub: "JSON + Ollama",    status: "idle",   calls: 59 },
    { name: "Search",   sub: "DuckDuckGo",       status: "idle",   calls: 6  },
    { name: "Camera",   sub: "MOG2 / OpenCV",    status: "idle",   calls: 2  },
  ],
  stats:    { total_calls: 141, motion_events: 2, emails_read: 3, slack_dms: 1 },
  command:  "check my emails",
  response: "You have 3 unread emails sir. One from Hack Club is marked urgent.",
  activity: [
    { time: "12:31", type: "Telegram", msg: "Missed call from Rahul — auto-replied" },
    { time: "12:18", type: "Gmail",    msg: "Hack Club submission deadline reminder" },
    { time: "11:55", type: "IoT",      msg: "Room lights turned on via voice" },
    { time: "11:30", type: "Camera",   msg: "Motion detected — snapshot saved" },
    { time: "06:00", type: "Tea",      msg: "Morning tea reminder triggered" },
  ],
  mqtt:   { connected: true, broker: "localhost:1883" },
  esp32:  { connected: true, ip: "192.168.1.8" },
  camera: { active: false, motionEvents: 2 },
  memory: { name: "Shivank", project: "JARVIS", location: "Lucknow, IN", sessions: 12 },
};

/* ── Fonts & global styles ───────────────────────────────────── */
const STYLES = `
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body { background: #000; color: #fff; -webkit-font-smoothing: antialiased; overflow-x: hidden; }
::-webkit-scrollbar { width: 2px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #1f1f1f; border-radius: 2px; }

@keyframes shimmer {
  0%   { background-position: -200% center; }
  100% { background-position:  200% center; }
}
@keyframes pulse-ring {
  0%   { transform: scale(1);   opacity: 0.6; }
  50%  { transform: scale(1.4); opacity: 0;   }
  100% { transform: scale(1);   opacity: 0;   }
}
@keyframes scan {
  0%   { transform: translateY(-100%); }
  100% { transform: translateY(100vh); }
}
@keyframes float {
  0%, 100% { transform: translateY(0px); }
  50%       { transform: translateY(-4px); }
}
@keyframes border-flow {
  0%   { background-position: 0% 50%; }
  50%  { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

.shimmer-text {
  background: linear-gradient(90deg, #fff 0%, #888 30%, #fff 50%, #aaa 70%, #fff 100%);
  background-size: 200% auto;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: shimmer 4s linear infinite;
}
.shimmer-slow {
  background: linear-gradient(90deg, #555 0%, #fff 30%, #888 50%, #fff 70%, #555 100%);
  background-size: 200% auto;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: shimmer 7s linear infinite;
}
.float { animation: float 4s ease-in-out infinite; }
`;

/* ── Primitives ──────────────────────────────────────────────── */
const mono = { fontFamily: "'JetBrains Mono', monospace" };
const sans = { fontFamily: "'Inter', sans-serif" };

function Mono({ children, style = {}, ...props }) {
  return <span style={{ ...mono, ...style }} {...props}>{children}</span>;
}

function divStyle() {
  return { height: 1, background: "#111", margin: "0" };
}

function SectionLabel({ children }) {
  return (
    <div style={{ ...sans, fontWeight: 500, fontSize: 10, letterSpacing: "0.14em", color: "#333", textTransform: "uppercase", marginBottom: 14 }}>
      {children}
    </div>
  );
}

/* ── Scan line overlay ───────────────────────────────────────── */
function ScanLine() {
  return (
    <div style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 100, overflow: "hidden" }}>
      <motion.div
        style={{ position: "absolute", left: 0, right: 0, height: 2, background: "linear-gradient(180deg, transparent, rgba(255,255,255,0.015), transparent)" }}
        animate={{ y: ["0vh", "100vh"] }}
        transition={{ duration: 8, repeat: Infinity, ease: "linear", repeatDelay: 3 }}
      />
    </div>
  );
}

/* ── Animated border card ────────────────────────────────────── */
function Card({ children, style = {}, delay = 0, animate: doAnim = true }) {
  return (
    <motion.div
      initial={doAnim ? { opacity: 0, y: 12 } : false}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: [0.16, 1, 0.3, 1] }}
      style={{
        background: "#080808",
        border: "1px solid #141414",
        borderRadius: 12,
        padding: 18,
        position: "relative",
        overflow: "hidden",
        ...style,
      }}
    >
      {/* top shimmer line */}
      <div style={{ position: "absolute", top: 0, left: "15%", right: "15%", height: 1, background: "linear-gradient(90deg, transparent, #222, transparent)", pointerEvents: "none" }} />
      {children}
    </motion.div>
  );
}

/* ── Live clock ──────────────────────────────────────────────── */
function Clock() {
  const [t, setT] = useState(new Date());
  useEffect(() => { const id = setInterval(() => setT(new Date()), 1000); return () => clearInterval(id); }, []);
  return (
    <div>
      <div style={{ ...mono, fontSize: 13, color: "#fff", letterSpacing: "0.08em" }}>
        {t.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
      </div>
      <div style={{ ...mono, fontSize: 10, color: "#2a2a2a", marginTop: 2, letterSpacing: "0.06em" }}>
        {t.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", year: "numeric" }).toUpperCase()}
      </div>
    </div>
  );
}

/* ── Animated counter ────────────────────────────────────────── */
function Counter({ to, duration = 1.5, delay = 0 }) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    let start = 0;
    const step = Math.ceil(to / (duration * 60));
    const id = setTimeout(() => {
      const interval = setInterval(() => {
        start += step;
        if (start >= to) { setVal(to); clearInterval(interval); }
        else setVal(start);
      }, 1000 / 60);
    }, delay * 1000);
    return () => clearTimeout(id);
  }, [to]);
  return <span>{val}</span>;
}

/* ── Uptime ──────────────────────────────────────────────────── */
function Uptime() {
  const [s, setS] = useState(0);
  useEffect(() => { const id = setInterval(() => setS(x => x + 1), 1000); return () => clearInterval(id); }, []);
  const h = String(Math.floor(s / 3600)).padStart(2, "0");
  const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const sc = String(s % 60).padStart(2, "0");
  return <span style={{ ...mono, fontSize: 11, color: "#888" }}>{h}:{m}:{sc}</span>;
}

/* ── Status dot ──────────────────────────────────────────────── */
function Dot({ active, size = 6 }) {
  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
      {active && (
        <motion.div
          style={{ position: "absolute", inset: -2, borderRadius: "50%", background: "rgba(255,255,255,0.15)" }}
          animate={{ scale: [1, 2, 1], opacity: [0.4, 0, 0.4] }}
          transition={{ duration: 2, repeat: Infinity }}
        />
      )}
      <div style={{ width: size, height: size, borderRadius: "50%", background: active ? "#fff" : "#1e1e1e", boxShadow: active ? "0 0 6px rgba(255,255,255,0.6)" : "none", transition: "all 0.4s" }} />
    </div>
  );
}

/* ── Waveform ────────────────────────────────────────────────── */
function Waveform({ active }) {
  const bars = 22;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 2, height: 20 }}>
      {Array.from({ length: bars }).map((_, i) => (
        <motion.div key={i}
          style={{ width: 2, borderRadius: 2, background: active ? "#fff" : "#1a1a1a", flexShrink: 0 }}
          animate={active ? { height: [2, (Math.sin(i * 0.7) + 1) * 7 + 3, 2] } : { height: 2 }}
          transition={{ duration: 0.4 + i * 0.02, repeat: Infinity, ease: "easeInOut" }}
        />
      ))}
    </div>
  );
}

/* ── Spinning conic ring logo ────────────────────────────────── */
function LogoRing() {
  return (
    <div className="float" style={{ position: "relative", width: 50, height: 50, flexShrink: 0 }}>
      <motion.div
        style={{
          position: "absolute", inset: 0, borderRadius: "50%",
          background: "conic-gradient(from 0deg, #ffffff 0%, #333 35%, #888 55%, #ffffff 80%, #444 100%)",
        }}
        animate={{ rotate: 360 }}
        transition={{ duration: 5, repeat: Infinity, ease: "linear" }}
      />
      {/* dashes */}
      <motion.div
        style={{
          position: "absolute", inset: 3, borderRadius: "50%",
          background: "conic-gradient(from 180deg, transparent 0deg, transparent 20deg, #fff 20deg, #fff 25deg, transparent 25deg)",
          opacity: 0.3,
        }}
        animate={{ rotate: -360 }}
        transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
      />
      <div style={{ position: "absolute", inset: 4, borderRadius: "50%", background: "#000", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <motion.div
          style={{ width: 14, height: 14, borderRadius: "50%", background: "radial-gradient(circle, #fff 0%, #777 100%)" }}
          animate={{ opacity: [0.7, 1, 0.7], scale: [0.95, 1.05, 0.95] }}
          transition={{ duration: 2.5, repeat: Infinity }}
        />
      </div>
    </div>
  );
}

/* ── LED button ──────────────────────────────────────────────── */
function LED({ label, sublabel, active, onClick }) {
  return (
    <motion.button onClick={onClick} whileTap={{ scale: 0.9 }}
      style={{ background: "none", border: "none", cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "center", gap: 9, padding: "10px 12px", borderRadius: 10 }}
      whileHover={{ background: "rgba(255,255,255,0.03)" }}
    >
      <div style={{ position: "relative" }}>
        {active && (
          <motion.div
            style={{ position: "absolute", inset: -5, borderRadius: "50%", border: "1px solid rgba(255,255,255,0.15)" }}
            animate={{ scale: [1, 1.8], opacity: [0.5, 0] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
        )}
        <motion.div style={{
          width: 10, height: 10, borderRadius: "50%",
          background: active ? "#fff" : "#1a1a1a",
          boxShadow: active ? "0 0 0 3px #1a1a1a, 0 0 20px rgba(255,255,255,0.6), 0 0 40px rgba(255,255,255,0.2)" : "0 0 0 1px #222",
          transition: "all 0.35s",
        }} />
      </div>
      <div style={{ textAlign: "center" }}>
        <div style={{ ...sans, fontWeight: 500, fontSize: 11, color: active ? "#fff" : "#2a2a2a", letterSpacing: "0.04em", transition: "color 0.3s" }}>{label}</div>
        <div style={{ ...mono, fontSize: 9, color: "#1a1a1a", marginTop: 1 }}>{sublabel}</div>
      </div>
    </motion.button>
  );
}

/* ── Typed text ──────────────────────────────────────────────── */
function TypedText({ text }) {
  const [shown, setShown] = useState("");
  const [i, setI] = useState(0);
  useEffect(() => { setShown(""); setI(0); }, [text]);
  useEffect(() => {
    if (i < text.length) {
      const t = setTimeout(() => { setShown(p => p + text[i]); setI(x => x + 1); }, 18);
      return () => clearTimeout(t);
    }
  }, [i, text]);
  return (
    <span>
      {shown}
      {i < text.length && (
        <motion.span animate={{ opacity: [1, 0, 1] }} transition={{ duration: 0.8, repeat: Infinity }} style={{ color: "#333" }}>|</motion.span>
      )}
    </span>
  );
}

/* ── Notification row ────────────────────────────────────────── */
function ActivityRow({ item, index }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -12, height: 0 }}
      animate={{ opacity: 1, x: 0, height: "auto" }}
      exit={{ opacity: 0, x: 12, height: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3 }}
      style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "8px 0", borderBottom: "1px solid #0d0d0d" }}
    >
      <span style={{ ...mono, fontSize: 10, color: "#2a2a2a", flexShrink: 0, paddingTop: 1 }}>{item.time}</span>
      <span style={{ ...mono, fontSize: 9, color: "#444", background: "#0d0d0d", border: "1px solid #1a1a1a", borderRadius: 4, padding: "1px 6px 2px", flexShrink: 0, letterSpacing: "0.05em" }}>
        {item.type.toUpperCase()}
      </span>
      <span style={{ ...sans, fontSize: 12, color: "#555", lineHeight: 1.5 }}>{item.msg}</span>
    </motion.div>
  );
}

/* ── Stat box with animated number ──────────────────────────── */
function StatBox({ label, val, delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.88 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay, duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
      style={{ background: "#060606", border: "1px solid #111", borderRadius: 10, padding: "14px 10px", textAlign: "center" }}
    >
      <div style={{ ...mono, fontWeight: 700, fontSize: 22, color: "#fff", lineHeight: 1 }}>
        <Counter to={val} delay={delay} />
      </div>
      <div style={{ ...sans, fontSize: 10, color: "#2a2a2a", marginTop: 6, letterSpacing: "0.1em", textTransform: "uppercase" }}>{label}</div>
    </motion.div>
  );
}

/* ── Page entry animation wrapper ────────────────────────────── */
function FadeIn({ children, delay = 0 }) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay, duration: 0.6 }}>
      {children}
    </motion.div>
  );
}

/* ══════════════════════════════════════════════════════════════
   MAIN DASHBOARD
══════════════════════════════════════════════════════════════ */
export default function JARVISDashboard() {
  const [leds,      setLeds]      = useState(MOCK.leds);
  const [awake,     setAwake]     = useState(MOCK.awake);
  const [listening, setListening] = useState(MOCK.listening);
  const [agents,    setAgents]    = useState(MOCK.agents);
  const [stats,     setStats]     = useState(MOCK.stats);
  const [command,   setCommand]   = useState(MOCK.command);
  const [response,  setResponse]  = useState(MOCK.response);
  const [activity,  setActivity]  = useState(MOCK.activity);
  const [camera,    setCamera]    = useState(MOCK.camera);
  const [wsStatus,  setWsStatus]  = useState("offline");
  const ws = useRef(null);

  useEffect(() => {
    const connect = () => {
      try {
        ws.current = new WebSocket("ws://localhost:8765");
        ws.current.onopen = () => setWsStatus("online");
        ws.current.onclose = () => { setWsStatus("offline"); setTimeout(connect, 4000); };
        ws.current.onerror = () => setWsStatus("offline");
        ws.current.onmessage = (e) => {
          try {
            const m = JSON.parse(e.data);
            if (m.type === "init") {
              setLeds(m.leds); setAgents(m.agents); setStats(m.stats); setCamera(m.camera);
              setAwake(m.awake); setListening(m.listening);
            }
            if (m.type === "leds")      setLeds(m.data);
            if (m.type === "listening") setListening(m.active);
            if (m.type === "awake")     setAwake(m.active);
            if (m.type === "command")   setCommand(m.text);
            if (m.type === "response")  setResponse(m.text);
            if (m.type === "activity")  setActivity(p => [m.data, ...p.slice(0, 19)]);
            if (m.type === "stats")     setStats(m.data);
            if (m.type === "camera")    setCamera(m.data);
            if (m.type === "agents")    setAgents(m.data);
          } catch {}
        };
      } catch {}
    };
    connect();
    return () => ws.current?.close();
  }, []);

  const toggleLED = (led) => {
    const next = { ...leds, [led]: !leds[led] };
    setLeds(next);
    ws.current?.send(JSON.stringify({ type: "led_toggle", led, state: next[led] }));
  };

  return (
    <>
      <style>{STYLES}</style>
      <ScanLine />

      <div style={{ minHeight: "100vh", background: "#000", padding: "20px 22px", ...sans }}>

        {/* ── HEADER ───────────────────────────────────────── */}
        <motion.header
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
          style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18, paddingBottom: 16, borderBottom: "1px solid #0f0f0f" }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <LogoRing />
            <div>
              <h1 className="shimmer-text" style={{ ...sans, fontWeight: 700, fontSize: 19, letterSpacing: "-0.02em", lineHeight: 1 }}>
                J.A.R.V.I.S
              </h1>
              <p style={{ ...sans, fontWeight: 400, fontSize: 11, color: "#252525", marginTop: 4, letterSpacing: "0.03em" }}>
                Just A Rather Very Intelligent System
              </p>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 32 }}>
            {/* Awake indicator */}
            <AnimatePresence mode="wait">
              <motion.div key={awake ? "awake" : "standby"}
                initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
                style={{ display: "flex", alignItems: "center", gap: 7 }}
              >
                <Dot active={awake} />
                <span style={{ ...sans, fontSize: 11, color: awake ? "#888" : "#2a2a2a", fontWeight: 500, letterSpacing: "0.05em" }}>
                  {awake ? "Awake" : "Standby"}
                </span>
              </motion.div>
            </AnimatePresence>

            {/* WS status */}
            <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <Dot active={wsStatus === "online"} size={5} />
              <span style={{ ...sans, fontSize: 11, color: "#2a2a2a", fontWeight: 400 }}>
                {wsStatus === "online" ? "Connected" : "Standalone"}
              </span>
            </div>

            <Clock />
          </div>
        </motion.header>

        {/* ── MAIN GRID ────────────────────────────────────── */}
        <div style={{ display: "grid", gridTemplateColumns: "260px 1fr 260px", gap: 12 }}>

          {/* ── LEFT ─────────────────────────────────────── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

            {/* System status */}
            <Card delay={0.05} glow>
              <SectionLabel>System</SectionLabel>
              {[
                { k: "JARVIS",    v: awake ? "Awake" : "Standby",              a: awake },
                { k: "Ollama",    v: "Running",                                 a: true  },
                { k: "MQTT",      v: MOCK.mqtt.broker,                          a: MOCK.mqtt.connected },
                { k: "ESP32",     v: MOCK.esp32.ip,                             a: MOCK.esp32.connected },
                { k: "Camera",    v: camera.active ? "Active" : "Standby",      a: camera.active },
                { k: "Uptime",    v: <Uptime />,                                a: true },
              ].map(({ k, v, a }, i, arr) => (
                <div key={k}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 0" }}>
                    <span style={{ ...sans, fontSize: 12, color: "#333", fontWeight: 400 }}>{k}</span>
                    <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                      <Dot active={a} size={5} />
                      {typeof v === "string"
                        ? <span style={{ ...mono, fontSize: 11, color: "#666" }}>{v}</span>
                        : v}
                    </div>
                  </div>
                  {i < arr.length - 1 && <div style={divStyle()} />}
                </div>
              ))}
            </Card>

            {/* IoT */}
            <Card delay={0.1}>
              <SectionLabel>IoT — ESP32-CAM</SectionLabel>
              <div style={{ display: "flex", justifyContent: "space-around", padding: "4px 0 2px" }}>
                <LED label="Tea"    sublabel="GPIO 12" active={leds.green} onClick={() => toggleLED("green")} />
                <LED label="Lights" sublabel="GPIO 2"  active={leds.white} onClick={() => toggleLED("white")} />
                <LED label="Alert"  sublabel="GPIO 13" active={leds.red}   onClick={() => toggleLED("red")}   />
              </div>
            </Card>

            {/* Memory */}
            <Card delay={0.15}>
              <SectionLabel>Memory Core</SectionLabel>
              {Object.entries(MOCK.memory).map(([k, v], i, arr) => (
                <div key={k}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "7px 0" }}>
                    <span style={{ ...sans, fontSize: 11, color: "#252525", textTransform: "uppercase", letterSpacing: "0.09em" }}>{k}</span>
                    <span style={{ ...mono, fontSize: 11, color: "#666" }}>{v}</span>
                  </div>
                  {i < arr.length - 1 && <div style={divStyle()} />}
                </div>
              ))}
            </Card>
          </div>

          {/* ── CENTER ───────────────────────────────────── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

            {/* Voice */}
            <Card delay={0.07}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
                <SectionLabel>Voice Interface</SectionLabel>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
                  <Waveform active={listening} />
                  <motion.div
                    animate={listening ? { boxShadow: ["0 0 0 1px #222", "0 0 0 1px #444", "0 0 0 1px #222"] } : {}}
                    transition={{ duration: 1.5, repeat: Infinity }}
                    style={{ ...sans, fontWeight: 500, fontSize: 10, color: listening ? "#fff" : "#1f1f1f", letterSpacing: "0.12em", textTransform: "uppercase", padding: "4px 12px", borderRadius: 20, border: `1px solid ${listening ? "#222" : "#0f0f0f"}`, transition: "all 0.3s" }}
                  >
                    {listening ? "Listening" : "Standby"}
                  </motion.div>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <div>
                  <div style={{ ...sans, fontSize: 10, color: "#1e1e1e", marginBottom: 6, letterSpacing: "0.1em", textTransform: "uppercase" }}>Input</div>
                  <div style={{ background: "#050505", border: "1px solid #0f0f0f", borderRadius: 8, padding: "10px 12px", ...mono, fontSize: 11, color: "#444", minHeight: 46, lineHeight: 1.5 }}>
                    "{command}"
                  </div>
                </div>
                <div>
                  <div style={{ ...sans, fontSize: 10, color: "#1e1e1e", marginBottom: 6, letterSpacing: "0.1em", textTransform: "uppercase" }}>Response</div>
                  <div style={{ background: "#050505", border: "1px solid #0f0f0f", borderRadius: 8, padding: "10px 12px", ...sans, fontWeight: 300, fontSize: 12, color: "#888", lineHeight: 1.6, minHeight: 46 }}>
                    <TypedText text={response} />
                  </div>
                </div>
              </div>
            </Card>

            {/* Models */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              {[
                { label: "Brain Model",  val: "llama3.2:3b",      desc: "General reasoning & conversation" },
                { label: "Coder Model",  val: "qwen2.5-coder:3b", desc: "Code generation & debugging"      },
              ].map((m, i) => (
                <Card key={m.label} delay={0.12 + i * 0.05} style={{ padding: 16 }}>
                  <div style={{ ...sans, fontSize: 10, color: "#252525", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>{m.label}</div>
                  <div className="shimmer-slow" style={{ ...mono, fontWeight: 700, fontSize: 13, marginBottom: 5 }}>{m.val}</div>
                  <div style={{ ...sans, fontSize: 11, color: "#1e1e1e", fontWeight: 300 }}>{m.desc}</div>
                </Card>
              ))}
            </div>

            {/* Agents */}
            <Card delay={0.18}>
              <SectionLabel>Agent Network</SectionLabel>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                {agents.map((a, i) => (
                  <motion.div key={a.name}
                    initial={{ opacity: 0, scale: 0.92 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.3 + i * 0.04, duration: 0.35 }}
                    style={{ background: "#050505", border: `1px solid ${a.status === "active" ? "#1a1a1a" : "#0d0d0d"}`, borderRadius: 8, padding: "10px 12px" }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 5 }}>
                      <Dot active={a.status === "active"} size={5} />
                      <span style={{ ...sans, fontWeight: 600, fontSize: 12, color: a.status === "active" ? "#fff" : "#444" }}>{a.name}</span>
                    </div>
                    <div style={{ ...mono, fontSize: 9, color: "#1e1e1e", marginBottom: 4, lineHeight: 1.4 }}>{a.sub}</div>
                    <div style={{ ...mono, fontSize: 10, color: "#2a2a2a" }}>{a.calls} calls</div>
                  </motion.div>
                ))}
              </div>
            </Card>

            {/* Stats */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 10 }}>
              <StatBox label="Total Calls"  val={stats.total_calls}    delay={0.35} />
              <StatBox label="Motion"       val={stats.motion_events}  delay={0.4}  />
              <StatBox label="Emails"       val={stats.emails_read}    delay={0.45} />
              <StatBox label="Slack DMs"    val={stats.slack_dms}      delay={0.5}  />
            </div>
          </div>

          {/* ── RIGHT ────────────────────────────────────── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

            {/* Camera */}
            <Card delay={0.1}>
              <SectionLabel>Security Camera</SectionLabel>
              <div style={{ aspectRatio: "16/9", background: "#040404", border: "1px solid #0d0d0d", borderRadius: 8, position: "relative", overflow: "hidden", marginBottom: 12, display: "flex", alignItems: "center", justifyContent: "center" }}>
                {/* grid */}
                <div style={{ position: "absolute", inset: 0, opacity: 0.04, backgroundImage: "linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)", backgroundSize: "18px 18px" }} />
                {/* crosshair */}
                <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", opacity: 0.05 }}>
                  <div style={{ width: "50%", height: 1, background: "#fff", position: "absolute" }} />
                  <div style={{ height: "50%", width: 1, background: "#fff", position: "absolute" }} />
                  <motion.div style={{ width: 28, height: 28, border: "1px solid #fff", borderRadius: "50%", position: "absolute" }}
                    animate={{ scale: [1, 1.3, 1], opacity: [0.4, 0.8, 0.4] }}
                    transition={{ duration: 3, repeat: Infinity }}
                  />
                </div>
                <span style={{ ...sans, fontSize: 11, color: "#111", letterSpacing: "0.14em", zIndex: 1 }}>
                  {camera.active ? "FEED ACTIVE" : "STANDBY"}
                </span>
                {/* rec */}
                <div style={{ position: "absolute", top: 8, right: 10, display: "flex", alignItems: "center", gap: 5 }}>
                  <motion.div style={{ width: 5, height: 5, borderRadius: "50%", background: camera.active ? "#fff" : "#181818" }}
                    animate={camera.active ? { opacity: [1, 0.2, 1] } : {}}
                    transition={{ duration: 1, repeat: Infinity }}
                  />
                  <span style={{ ...mono, fontSize: 9, color: "#181818" }}>{camera.active ? "REC" : "OFF"}</span>
                </div>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ ...sans, fontSize: 11, color: "#222" }}>MOG2 Algorithm</span>
                <span style={{ ...mono, fontSize: 11, color: "#444" }}>{camera.motionEvents} events</span>
              </div>
            </Card>

            {/* Activity log */}
            <Card delay={0.15} style={{ flex: 1 }}>
              <SectionLabel>Activity Log</SectionLabel>
              <div style={{ overflowY: "auto", maxHeight: 270 }}>
                <AnimatePresence>
                  {activity.map((item, i) => (
                    <ActivityRow key={`${item.time}-${item.type}-${i}`} item={item} index={i} />
                  ))}
                </AnimatePresence>
              </div>
            </Card>

            {/* Connections */}
            <Card delay={0.2}>
              <SectionLabel>Connections</SectionLabel>
              {[
                { k: "DuckDuckGo", v: "Web Search"  },
                { k: "Telethon",   v: "MTProto"      },
                { k: "Gmail IMAP", v: "App Password" },
                { k: "Slack API",  v: "User Token"   },
              ].map(({ k, v }, i, arr) => (
                <div key={k}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "7px 0" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                      <Dot active size={5} />
                      <span style={{ ...sans, fontSize: 12, color: "#3a3a3a" }}>{k}</span>
                    </div>
                    <span style={{ ...mono, fontSize: 10, color: "#1e1e1e" }}>{v}</span>
                  </div>
                  {i < arr.length - 1 && <div style={divStyle()} />}
                </div>
              ))}
            </Card>
          </div>
        </div>

        {/* ── FOOTER ──────────────────────────────────────── */}
        <motion.footer
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1 }}
          style={{ marginTop: 18, paddingTop: 14, borderTop: "1px solid #0a0a0a", display: "flex", justifyContent: "space-between", alignItems: "center" }}
        >
          <span style={{ ...sans, fontSize: 11, color: "#1a1a1a" }}>
            JARVIS v1.0 — Built by <span style={{ color: "#333" }}>Shivank Pandey</span> · Hack Club Manifesto · 2026
          </span>
          <span style={{ ...mono, fontSize: 10, color: "#161616" }}>
            100% OFFLINE · 100% PRIVATE · LUCKNOW, IN
          </span>
        </motion.footer>
      </div>
    </>
  );
}